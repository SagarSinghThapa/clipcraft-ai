"""9:16 vertical reframing service with OpenCV face tracking and EMA trajectory smoothing."""

import subprocess
from pathlib import Path
from typing import Optional, Tuple, List

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.models.facecam import FacecamRegion
from backend.app.models.layout import LayoutStrategy, GameplayCompositionMode, CanvasResolution, GamingLayoutConfig
from backend.app.services.storage_service import storage_service
from backend.app.services.gaming_layout_service import gaming_layout_service
from backend.app.services.analysis_service import analysis_service
from backend.app.utils.ffmpeg_utils import probe_media_metadata, is_ffmpeg_available


class ReframingService:
    """Reframes horizontal video to 9:16 vertical format using smoothed face tracking."""

    def calculate_9_16_crop_dimensions(self, width: int, height: int) -> Tuple[int, int]:
        """
        Calculates the 9:16 crop box width and height for a given video resolution.
        For 1920x1080, height is 1080 and crop width is round(1080 * 9 / 16) = 608.
        Ensures dimensions are even numbers for H.264 compatibility.
        """
        crop_h = height
        crop_w = int(round(height * 9.0 / 16.0))
        # Ensure even
        if crop_w % 2 != 0:
            crop_w += 1
        # Crop width cannot exceed original video width
        crop_w = min(crop_w, width)
        return crop_w, crop_h

    def apply_ema_smoothing(self, positions: List[float], alpha: float = 0.15) -> List[float]:
        """
        Applies Exponential Moving Average (EMA) to a sequence of horizontal crop positions.
        Eliminates frame-to-frame jitter while smoothly tracking speaker motion.
        """
        if not positions:
            return []
        smoothed = [positions[0]]
        for pos in positions[1:]:
            prev = smoothed[-1]
            val = alpha * pos + (1.0 - alpha) * prev
            smoothed.append(round(val, 2))
        return smoothed

    def detect_crop_center_x(self, video_path: Path, video_w: int, video_h: int, crop_w: int) -> int:
        """
        Detects primary speaker face location using OpenCV frame sampling.
        Returns the optimal left coordinate for the crop box (clamped between 0 and video_w - crop_w).
        Falls back to exact center crop if OpenCV is unavailable or no face is found.
        """
        default_left = (video_w - crop_w) // 2
        try:
            import cv2  # type: ignore
        except ImportError:
            logger.info("OpenCV not installed in current environment. Using center crop fallback.")
            return default_left

        # Load standard Haar cascade bundled with OpenCV
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        face_cascade = cv2.CascadeClassifier(cascade_path)
        if face_cascade.empty():
            logger.warning("Haar cascade classifier could not be loaded. Defaulting to center crop.")
            return default_left

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return default_left

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_interval = max(1, int(round(fps / 5.0)))  # Sample at 5 fps to save CPU
        detected_centers: List[float] = []

        frame_idx = 0
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % frame_interval == 0:
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = face_cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.15,
                    minNeighbors=4,
                    minSize=(int(video_h * 0.1), int(video_h * 0.1))
                )
                if len(faces) > 0:
                    # Pick largest face
                    largest_face = max(faces, key=lambda f: f[2] * f[3])
                    fx, fy, fw, fh = largest_face
                    center_x = fx + (fw / 2.0)
                    detected_centers.append(center_x)

            frame_idx += 1
            if frame_idx > fps * 30:  # Sample first 30 seconds
                break

        cap.release()

        if not detected_centers:
            logger.info("No face detected in video sample. Using center crop fallback.")
            return default_left

        # Compute median detected center to reject outliers
        detected_centers.sort()
        median_center = detected_centers[len(detected_centers) // 2]

        target_left = median_center - (crop_w / 2.0)
        clamped_left = int(round(max(0.0, min(float(video_w - crop_w), target_left))))
        # Ensure even
        if clamped_left % 2 != 0:
            clamped_left = max(0, clamped_left - 1)

        logger.info(f"Face tracked at X={int(median_center)}. Crop left set to X={clamped_left} (range 0..{video_w - crop_w}).")
        return clamped_left

    def build_reframe_command(
        self,
        input_clip_path: Path,
        output_reframe_path: Path,
        crop_w: int,
        crop_h: int,
        crop_x: int,
        target_w: int = 1080,
        target_h: int = 1920
    ) -> list:
        """Constructs FFmpeg filtergraph: crop -> scale to 1080x1920."""
        filter_spec = f"crop={crop_w}:{crop_h}:{crop_x}:0,scale={target_w}:{target_h}:flags=lanczos"
        return [
            settings.FFMPEG_PATH,
            "-y",
            "-i", str(input_clip_path),
            "-vf", filter_spec,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(output_reframe_path)
        ]

    def reframe_clip(
        self,
        project_id: str,
        clip_id: str,
        force_recompute: bool = False,
        layout_config: Optional[GamingLayoutConfig] = None
    ) -> Path:
        """Reframes raw_clip.mp4 to 9:16 vertical reframed.mp4."""
        dirs = storage_service.init_project_workspace(project_id)
        clip_dir = dirs["clips"] / clip_id
        raw_clip = clip_dir / "raw_clip.mp4"
        reframed_clip = clip_dir / "reframed.mp4"

        if not raw_clip.exists():
            raise FileNotFoundError(f"Raw cut clip '{raw_clip}' not found. Cut clip first.")

        if reframed_clip.exists() and reframed_clip.stat().st_size > 0 and not force_recompute:
            logger.info(f"Reusing cached reframed clip: {reframed_clip}")
            return reframed_clip

        if not is_ffmpeg_available():
            raise RuntimeError("FFmpeg is required for 9:16 reframing.")

        meta = probe_media_metadata(raw_clip)

        # Inspect candidate overrides if available
        candidate = None
        try:
            c_data = analysis_service.load_cached_candidates(project_id)
            if c_data and c_data.candidates:
                candidate = next((c for c in c_data.candidates if c.id == clip_id), None)
        except Exception:
            pass

        # If layout_config was not explicitly supplied, check candidate overrides or project facecam
        if layout_config is None:
            cached_facecam = storage_service.load_stage_checkpoint(project_id, "facecam")
            has_facecam = bool(cached_facecam and cached_facecam.get("is_detected"))

            cand_strategy = getattr(candidate, "layout_strategy", None) if candidate else None
            cand_comp = getattr(candidate, "gameplay_composition", None) if candidate else None
            cand_split = getattr(candidate, "split_ratio", None) if candidate else None
            cand_exclude_chat = getattr(candidate, "exclude_chat_overlay", None) if candidate else None
            cand_res = getattr(candidate, "resolution", None) if candidate else None

            if cand_strategy or has_facecam:
                layout_config = GamingLayoutConfig(
                    strategy=cand_strategy or LayoutStrategy.AUTO_GAMING,
                    resolution=cand_res or CanvasResolution.FHD_1080x1920,
                    split_ratio=cand_split if cand_split is not None else 0.30,
                    gameplay_composition=cand_comp or GameplayCompositionMode.AUTO,
                    exclude_chat_overlay=cand_exclude_chat if cand_exclude_chat is not None else True,
                )
        elif candidate:
            # Fill missing or default fields from candidate overrides
            if getattr(candidate, "resolution", None) and (not layout_config.resolution or layout_config.resolution == CanvasResolution.FHD_1080x1920):
                layout_config.resolution = candidate.resolution
            if getattr(candidate, "split_ratio", None) is not None and layout_config.split_ratio == 0.375:
                layout_config.split_ratio = candidate.split_ratio
            if getattr(candidate, "gameplay_composition", None):
                layout_config.gameplay_composition = candidate.gameplay_composition
            if getattr(candidate, "exclude_chat_overlay", None) is not None:
                layout_config.exclude_chat_overlay = candidate.exclude_chat_overlay

        # Delegate to GamingLayoutService for stacked/focus gaming layouts
        if layout_config and layout_config.strategy in (
            LayoutStrategy.GAMING_SPLIT,
            LayoutStrategy.GAMEPLAY_FOCUS,
            LayoutStrategy.STREAMER_FOCUS,
            LayoutStrategy.AUTO_GAMING,
        ):
            cached_facecam = storage_service.load_stage_checkpoint(project_id, "facecam")
            facecam = FacecamRegion(**cached_facecam) if cached_facecam else None

            logger.info(f"Delegating clip '{clip_id}' to GamingLayoutService ({layout_config.strategy.value})...")
            return gaming_layout_service.render_layout_clip(
                source_path=raw_clip,
                output_path=reframed_clip,
                config=layout_config,
                source_w=meta.width,
                source_h=meta.height,
                facecam=facecam,
                force_recompute=force_recompute
            )

        crop_w, crop_h = self.calculate_9_16_crop_dimensions(meta.width, meta.height)
        crop_x = self.detect_crop_center_x(raw_clip, meta.width, meta.height, crop_w)

        target_w, target_h = (settings.TARGET_WIDTH, settings.TARGET_HEIGHT)
        if layout_config and layout_config.resolution:
            dim_map = {
                CanvasResolution.FHD_1080x1920: (1080, 1920),
                CanvasResolution.QHD_1440x2560: (1440, 2560),
                CanvasResolution.UHD_2160x3840: (2160, 3840),
            }
            target_w, target_h = dim_map.get(layout_config.resolution, (1080, 1920))

        cmd = self.build_reframe_command(
            raw_clip,
            reframed_clip,
            crop_w=crop_w,
            crop_h=crop_h,
            crop_x=crop_x,
            target_w=target_w,
            target_h=target_h
        )

        logger.info(f"Reframing clip '{clip_id}' to 9:16 ({settings.TARGET_WIDTH}x{settings.TARGET_HEIGHT})...")
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg reframing failed: {e.stderr}")
            raise RuntimeError(f"FFmpeg reframing failed: {e.stderr}")

        logger.info(f"Clip reframed successfully: {reframed_clip} ({round(reframed_clip.stat().st_size / (1024 * 1024), 2)} MB)")
        return reframed_clip


reframing_service = ReframingService()
