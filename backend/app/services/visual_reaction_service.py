"""Lightweight staged visual reaction analysis for streamer facecam motion and gameplay activity."""

from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List
import cv2
import numpy as np

from backend.app.core.logger import logger
from backend.app.models.facecam import FacecamRegion
from backend.app.services.storage_service import storage_service


class VisualReactionService:
    """Targeted frame differencing within facecam and gameplay regions for shortlisted windows."""

    def __init__(self):
        # Cache keyed by (video_path_str, start_sec, end_sec)
        self._clip_cache: Dict[str, Dict[str, float]] = {}

    def analyze_candidate_visuals(
        self,
        source_video_path: Path,
        start_sec: float,
        end_sec: float,
        facecam: Optional[FacecamRegion] = None,
        sample_fps: float = 2.0,
        peak_sec: Optional[float] = None,
        max_sample_frames: int = 15
    ) -> Dict[str, float]:
        """
        Samples frames at low frequency (default 2 fps) across candidate window [start_sec, end_sec]
        and measures normalized visual motion inside the facecam region and gameplay region.
        When duration is long, centers sampling tightly around reaction peak to keep CPU analysis fast.
        Returns: {
            "streamer_visual_reaction_score": float (0-100),
            "gameplay_activity_score": float (0-100),
            "peak_facecam_motion": float,
            "peak_gameplay_motion": float
        }
        """
        cache_key = f"{source_video_path.name}_{round(start_sec, 2)}_{round(end_sec, 2)}"
        if cache_key in self._clip_cache:
            return self._clip_cache[cache_key]

        if not source_video_path.exists():
            logger.warning(f"Video file not found for visual reaction analysis: {source_video_path}")
            return {
                "streamer_visual_reaction_score": 50.0,
                "gameplay_activity_score": 50.0,
                "peak_facecam_motion": 0.0,
                "peak_gameplay_motion": 0.0
            }

        cap = cv2.VideoCapture(str(source_video_path), cv2.CAP_FFMPEG)
        if not cap.isOpened():
            logger.warning(f"Failed to open video file: {source_video_path}")
            return {
                "streamer_visual_reaction_score": 50.0,
                "gameplay_activity_score": 50.0,
                "peak_facecam_motion": 0.0,
                "peak_gameplay_motion": 0.0
            }

        fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        video_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 1920)
        video_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 1080)

        # Center frame sampling window around reaction peak when provided or when duration exceeds max_sample_frames
        if peak_sec is not None:
            sample_start = max(start_sec, peak_sec - 2.5)
            sample_end = min(end_sec, peak_sec + 5.5)
        elif (end_sec - start_sec) * sample_fps > max_sample_frames:
            mid = (start_sec + end_sec) / 2.0
            half_span = (max_sample_frames / sample_fps) / 2.0
            sample_start = max(start_sec, mid - half_span)
            sample_end = min(end_sec, mid + half_span)
        else:
            sample_start = start_sec
            sample_end = end_sec

        step_frames = max(1, int(round(fps / sample_fps)))
        target_sample_count = max(2, min(max_sample_frames, int(round((sample_end - sample_start) * sample_fps))))

        cap.set(cv2.CAP_PROP_POS_MSEC, float(sample_start * 1000.0))

        prev_cam_gray: Optional[np.ndarray] = None
        prev_game_gray: Optional[np.ndarray] = None

        cam_motion_series: List[float] = []
        game_motion_series: List[float] = []

        # Facecam coordinates
        fx, fy, fw, fh = 0, 0, 0, 0
        has_facecam = facecam is not None and facecam.is_detected
        if has_facecam:
            fx, fy, fw, fh = facecam.x, facecam.y, facecam.width, facecam.height

        curr_sample = 0
        while curr_sample < target_sample_count:
            ret, frame = cap.read()
            if not ret or frame is None:
                break
            curr_sample += 1

            # 1. Streamer Facecam motion differencing
            if has_facecam and fw > 0 and fh > 0:
                cam_crop = frame[fy:fy + fh, fx:fx + fw]
                if cam_crop.size > 0:
                    cam_gray = cv2.cvtColor(cam_crop, cv2.COLOR_BGR2GRAY)
                    cam_small = cv2.resize(cam_gray, (160, 90), interpolation=cv2.INTER_AREA)

                    if prev_cam_gray is not None:
                        diff = cv2.absdiff(cam_small, prev_cam_gray)
                        motion_val = float(np.mean(diff) / 255.0)
                        cam_motion_series.append(motion_val)
                    prev_cam_gray = cam_small

            # 2. Gameplay region motion differencing (outside facecam)
            game_crop = frame.copy()
            if has_facecam and fw > 0 and fh > 0:
                # Black out facecam region so streamer movement does not count as game motion
                game_crop[fy:fy + fh, fx:fx + fw] = 0

            game_gray = cv2.cvtColor(game_crop, cv2.COLOR_BGR2GRAY)
            game_small = cv2.resize(game_gray, (180, 100), interpolation=cv2.INTER_AREA)

            if prev_game_gray is not None:
                diff_game = cv2.absdiff(game_small, prev_game_gray)
                motion_game_val = float(np.mean(diff_game) / 255.0)
                game_motion_series.append(motion_game_val)
            prev_game_gray = game_small

            # Skip ahead by step_frames quickly using cap.grab()
            for _ in range(step_frames - 1):
                if not cap.grab():
                    break

        cap.release()

        # Score calculations
        peak_cam = float(np.max(cam_motion_series)) if cam_motion_series else 0.0
        std_cam = float(np.std(cam_motion_series)) if cam_motion_series else 0.0

        peak_game = float(np.max(game_motion_series)) if game_motion_series else 0.0
        std_game = float(np.std(game_motion_series)) if game_motion_series else 0.0

        # Streamer visual reaction score mapping
        if has_facecam and cam_motion_series:
            # Baseline speaking motion is ~0.03; major head turn / jump / laugh is >= 0.15
            cam_score = 40.0 + (160.0 * min(0.35, peak_cam)) + (80.0 * min(0.20, std_cam))
            streamer_score = float(round(max(0.0, min(100.0, cam_score)), 2))
        else:
            # Neutral default if no facecam present
            streamer_score = 50.0

        # Gameplay activity score mapping
        if game_motion_series:
            # Normal gameplay is ~0.04; explosion / chase / quick turn is >= 0.20
            game_score = 35.0 + (150.0 * min(0.35, peak_game)) + (75.0 * min(0.20, std_game))
            gameplay_score = float(round(max(0.0, min(100.0, game_score)), 2))
        else:
            gameplay_score = 50.0

        result = {
            "streamer_visual_reaction_score": streamer_score,
            "gameplay_activity_score": gameplay_score,
            "peak_facecam_motion": round(peak_cam, 4),
            "peak_gameplay_motion": round(peak_game, 4)
        }
        self._clip_cache[cache_key] = result
        return result


visual_reaction_service = VisualReactionService()
