"""Streamer facecam detection service utilizing spatial persistence clustering over coarse frame samples."""

from pathlib import Path
from typing import List, Dict, Tuple, Optional
import numpy as np

from backend.app.core.logger import logger
from backend.app.models.facecam import FacecamRegion
from backend.app.services.storage_service import storage_service


class FacecamService:
    """Detects and localizes persistent streamer webcam boxes embedded within horizontal gameplay."""

    def __init__(self):
        self._cascade = None

    def _get_cascade(self):
        """Lazy loader for OpenCV Haar cascade classifier."""
        if self._cascade is None:
            try:
                import cv2
                cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
                cascade = cv2.CascadeClassifier(cascade_path)
                if not cascade.empty():
                    self._cascade = cascade
                else:
                    logger.warning("Failed to load OpenCV Haar cascade classifier.")
            except ImportError:
                logger.warning("OpenCV not installed in current environment.")
        return self._cascade

    def sample_video_frames(
        self,
        video_path: Path,
        sample_interval_sec: float = 2.5,
        max_samples: int = 150
    ) -> List[Tuple[float, np.ndarray]]:
        """
        Samples video frames evenly at low frequency across the video using timestamp seeking.
        Avoids decoding all video frames, keeping execution under a few seconds.
        """
        try:
            import cv2
        except ImportError:
            logger.error("OpenCV is required to sample video frames.")
            return []

        if not video_path.exists():
            raise FileNotFoundError(f"Source video file not found: {video_path}")

        cap = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
        if not cap.isOpened():
            logger.error(f"Cannot open video file: {video_path}")
            return []

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0
        duration_sec = frame_count / fps if fps > 0 else 0.0

        if duration_sec <= 0:
            cap.release()
            return []

        # Calculate sample timestamps
        num_samples = min(max_samples, max(5, int(duration_sec / sample_interval_sec)))
        timestamps = np.linspace(0.5, max(0.5, duration_sec - 1.0), num_samples)

        sampled_frames: List[Tuple[float, np.ndarray]] = []
        for t in timestamps:
            cap.set(cv2.CAP_PROP_POS_MSEC, float(t * 1000.0))
            ret, frame = cap.read()
            if ret and frame is not None:
                sampled_frames.append((float(t), frame))

        cap.release()
        logger.info(f"Sampled {len(sampled_frames)} frames across {duration_sec:.1f}s video ({video_path.name}).")
        return sampled_frames

    def detect_faces_in_frame(self, frame: np.ndarray) -> List[Tuple[int, int, int, int]]:
        """Detects faces in a single BGR frame. Returns list of (x, y, w, h)."""
        cascade = self._get_cascade()
        if cascade is None:
            return []

        try:
            import cv2
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            h, w = frame.shape[:2]
            # Facecam faces are typically between 5% and 35% of frame height
            min_size = (max(24, int(h * 0.05)), max(24, int(h * 0.05)))
            max_size = (int(h * 0.45), int(h * 0.45))
            faces = cascade.detectMultiScale(
                gray,
                scaleFactor=1.15,
                minNeighbors=4,
                minSize=min_size,
                maxSize=max_size
            )
            return [(int(x), int(y), int(bw), int(bh)) for (x, y, bw, bh) in faces]
        except Exception as e:
            logger.warning(f"Face detection failed on frame: {e}")
            return []

    def assign_quadrant(self, cx: float, cy: float) -> str:
        """Categorizes normalized coordinates (0.0 to 1.0) into screen quadrant."""
        if cx < 0.5 and cy < 0.5:
            return "TOP_LEFT"
        elif cx >= 0.5 and cy < 0.5:
            return "TOP_RIGHT"
        elif cx < 0.5 and cy >= 0.5:
            return "BOTTOM_LEFT"
        else:
            return "BOTTOM_RIGHT"

    def cluster_persistent_faces(
        self,
        frame_detections: List[Dict],
        total_samples: int,
        frame_w: int,
        frame_h: int
    ) -> Optional[Dict]:
        """
        Clusters face detections across frames to find a spatially persistent webcam box.
        Filters out transient gameplay faces (NPCs/cutscenes) by requiring consistent location
        and low spatial variance over time.
        """
        if not frame_detections or total_samples <= 0:
            return None

        # Group detections by quadrant
        quadrants: Dict[str, List[Dict]] = {
            "TOP_LEFT": [],
            "TOP_RIGHT": [],
            "BOTTOM_LEFT": [],
            "BOTTOM_RIGHT": []
        }

        for d in frame_detections:
            cx_norm = (d["x"] + d["w"] / 2.0) / frame_w
            cy_norm = (d["y"] + d["h"] / 2.0) / frame_h
            q = self.assign_quadrant(cx_norm, cy_norm)
            quadrants[q].append(d)

        best_cluster = None
        highest_score = -1.0

        for q_name, q_dets in quadrants.items():
            if not q_dets:
                continue

            # Calculate persistence ratio across all sampled frames
            unique_frames = len(set(d.get("frame_idx", idx) for idx, d in enumerate(q_dets)))
            persistence_ratio = unique_frames / float(total_samples)

            # Require facecam to be visible in at least 20% of sampled frames
            if persistence_ratio < 0.20:
                continue

            # Calculate spatial center and variance
            cxs = np.array([(d["x"] + d["w"] / 2.0) / frame_w for d in q_dets])
            cys = np.array([(d["y"] + d["h"] / 2.0) / frame_h for d in q_dets])
            std_x = float(np.std(cxs))
            std_y = float(np.std(cys))

            # Streamer facecams have tight spatial clustering (low std dev)
            # Transient faces moving across the screen have high std dev
            if std_x > 0.12 or std_y > 0.12:
                continue

            # Quality metric: persistence penalized by spatial variance
            cluster_score = persistence_ratio * (1.0 - (std_x + std_y))

            if cluster_score > highest_score:
                highest_score = cluster_score
                median_w = int(np.median([d["w"] for d in q_dets]))
                median_h = int(np.median([d["h"] for d in q_dets]))
                median_x = int(np.median([d["x"] for d in q_dets]))
                median_y = int(np.median([d["y"] for d in q_dets]))

                best_cluster = {
                    "quadrant": q_name,
                    "fx": median_x,
                    "fy": median_y,
                    "fw": median_w,
                    "fh": median_h,
                    "persistence_ratio": round(persistence_ratio, 2),
                    "confidence": round(min(1.0, cluster_score * 1.5), 2),
                    "detected_count": unique_frames
                }

        return best_cluster

    def calculate_facecam_crop_box(
        self,
        fx: int,
        fy: int,
        fw: int,
        fh: int,
        frame_w: int,
        frame_h: int,
        target_aspect: float = 16.0 / 9.0,
        padding_x: float = 2.0,
        padding_y: float = 2.2
    ) -> Tuple[int, int, int, int]:
        """
        Calculates expanded crop box centered around face to capture shoulders,
        torso, microphone, and headroom, formatted to target aspect ratio without distortion.
        Enforces even dimensions for encoder compatibility.
        """
        # Expand around face
        raw_w = int(round(fw * padding_x))
        raw_h = int(round(fh * padding_y))

        # Enforce target aspect ratio (e.g. 16:9 widescreen webcam box)
        if raw_w / raw_h < target_aspect:
            raw_w = int(round(raw_h * target_aspect))
        else:
            raw_h = int(round(raw_w / target_aspect))

        # Clamp max size to 50% of source frame
        box_w = min(raw_w, int(frame_w * 0.55))
        box_h = int(round(box_w / target_aspect))

        # Ensure even
        if box_w % 2 != 0:
            box_w += 1
        if box_h % 2 != 0:
            box_h += 1

        # Center on face with slight downward offset so headroom above hair is preserved
        center_x = fx + (fw / 2.0)
        center_y = fy + (fh / 2.0) + (fh * 0.15)

        target_left = int(round(center_x - (box_w / 2.0)))
        target_top = int(round(center_y - (box_h / 2.0)))

        # Clamp within frame boundaries
        clamped_x = max(0, min(frame_w - box_w, target_left))
        clamped_y = max(0, min(frame_h - box_h, target_top))

        # Ensure even coordinates
        if clamped_x % 2 != 0:
            clamped_x = max(0, clamped_x - 1)
        if clamped_y % 2 != 0:
            clamped_y = max(0, clamped_y - 1)

        return clamped_x, clamped_y, box_w, box_h

    def analyze_source_facecam(
        self,
        video_path: Path,
        sample_interval_sec: float = 2.5,
        max_samples: int = 150
    ) -> FacecamRegion:
        """
        Executes end-to-end facecam localization on a source video:
        samples frames -> detects faces -> clusters spatial persistence -> calculates expanded crop box.
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video file does not exist: {video_path}")

        try:
            import cv2
        except ImportError:
            logger.warning("OpenCV not available. Cannot perform facecam detection.")
            return FacecamRegion(is_detected=False)

        samples = self.sample_video_frames(video_path, sample_interval_sec, max_samples)
        if not samples:
            return FacecamRegion(is_detected=False)

        frame_h, frame_w = samples[0][1].shape[:2]
        all_detections: List[Dict] = []

        for idx, (t, frame) in enumerate(samples):
            faces = self.detect_faces_in_frame(frame)
            for (x, y, w, h) in faces:
                all_detections.append({
                    "frame_idx": idx,
                    "t": t,
                    "x": x,
                    "y": y,
                    "w": w,
                    "h": h
                })

        logger.info(f"Total face detections across {len(samples)} samples: {len(all_detections)}")

        cluster = self.cluster_persistent_faces(all_detections, len(samples), frame_w, frame_h)

        if not cluster:
            logger.info("No persistent streamer facecam cluster identified (gameplay-only or transient faces).")
            return FacecamRegion(
                is_detected=False,
                sample_count=len(samples),
                video_width=frame_w,
                video_height=frame_h
            )

        crop_x, crop_y, crop_w, crop_h = self.calculate_facecam_crop_box(
            fx=cluster["fx"],
            fy=cluster["fy"],
            fw=cluster["fw"],
            fh=cluster["fh"],
            frame_w=frame_w,
            frame_h=frame_h
        )

        region = FacecamRegion(
            is_detected=True,
            x=crop_x,
            y=crop_y,
            width=crop_w,
            height=crop_h,
            confidence=cluster["confidence"],
            quadrant=cluster["quadrant"],
            sample_count=len(samples),
            detected_count=cluster["detected_count"],
            detected_ratio=cluster["persistence_ratio"],
            video_width=frame_w,
            video_height=frame_h
        )

        logger.info(
            f"Detected streamer facecam in {region.quadrant}: "
            f"box=({region.x}, {region.y}, {region.width}x{region.height}), "
            f"confidence={region.confidence}, ratio={region.detected_ratio}"
        )
        return region

    def generate_debug_frame(
        self,
        video_path: Path,
        region: FacecamRegion,
        output_path: Path,
        timestamp_sec: float = 2.0
    ) -> Path:
        """Generates a visual debug frame JPEG with the facecam bounding box and info overlay."""
        try:
            import cv2
        except ImportError:
            raise RuntimeError("OpenCV is required to generate debug frame.")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        frame = None
        # Only attempt VideoCapture if file exists and is reasonably sized (> 10KB)
        if video_path.exists() and video_path.stat().st_size > 10240:
            try:
                cap = cv2.VideoCapture(str(video_path), cv2.CAP_FFMPEG)
                if cap.isOpened():
                    cap.set(cv2.CAP_PROP_POS_MSEC, float(timestamp_sec * 1000.0))
                    ret, frame = cap.read()
                    if not ret or frame is None:
                        cap.set(cv2.CAP_PROP_POS_MSEC, 0.0)
                        ret, frame = cap.read()
                    cap.release()
            except Exception as e:
                logger.warning(f"Failed to capture frame from video {video_path}: {e}")

        if frame is None:
            # Fallback canvas if video cannot be sampled
            w = region.video_width or 1920
            h = region.video_height or 1080
            frame = np.zeros((h, w, 3), dtype=np.uint8)

        # Draw overlays
        if region.is_detected:
            # Draw green bounding box (BGR: 0, 255, 0)
            cv2.rectangle(
                frame,
                (region.x, region.y),
                (region.x + region.width, region.y + region.height),
                (0, 255, 0),
                3
            )
            # Label banner
            label = f"Streamer Facecam [{region.quadrant}] Conf: {region.confidence:.2f} ({region.detected_ratio*100:.0f}%)"
            banner_y = max(30, region.y)
            cv2.rectangle(frame, (region.x, banner_y - 28), (region.x + min(region.width, 450), banner_y), (0, 200, 0), -1)
            cv2.putText(
                frame,
                label,
                (region.x + 5, banner_y - 8),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.55,
                (0, 0, 0),
                2,
                cv2.LINE_AA
            )
        else:
            # Draw warning overlay
            label = "No Persistent Streamer Facecam Detected (Gameplay Only)"
            cv2.rectangle(frame, (20, 20), (740, 70), (0, 0, 180), -1)
            cv2.putText(
                frame,
                label,
                (30, 55),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.75,
                (255, 255, 255),
                2,
                cv2.LINE_AA
            )

        cv2.imwrite(str(output_path), frame, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
        return output_path


facecam_service = FacecamService()

