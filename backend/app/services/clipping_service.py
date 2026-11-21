"""Precision video cutting engine using FFmpeg with frame accuracy and sync preservation."""

import subprocess
from pathlib import Path
from typing import List, Optional

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.models.candidate import CandidateClip
from backend.app.services.storage_service import storage_service
from backend.app.services.analysis_service import analysis_service
from backend.app.utils.ffmpeg_utils import is_ffmpeg_available


class ClippingService:
    """Cuts source video files at candidate timestamps without frozen frames or audio drift."""

    def build_cut_command(self, source_path: Path, output_path: Path, start_time: float, end_time: float) -> list:
        """
        Builds frame-accurate FFmpeg command.
        Uses -ss and -to with libx264 re-encoding and -avoid_negative_ts make_zero
        to prevent frozen I-frame delays or audio desync at the clip start.
        """
        return [
            settings.FFMPEG_PATH,
            "-y",
            "-ss", f"{start_time:.3f}",
            "-to", f"{end_time:.3f}",
            "-i", str(source_path),
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "aac",
            "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            "-movflags", "+faststart",  # Web-optimized MP4 header
            str(output_path)
        ]

    def cut_candidate_clip(self, project_id: str, candidate: CandidateClip, force_recompute: bool = False) -> Path:
        """Cuts a single candidate clip from project source video into raw_clip.mp4."""
        project = storage_service.load_project_metadata(project_id)
        if not project or not project.source_path:
            raise ValueError(f"Project '{project_id}' does not have an ingested source video.")

        source_path = Path(project.source_path)
        if not source_path.exists():
            raise FileNotFoundError(f"Source video not found: {source_path}")

        dirs = storage_service.init_project_workspace(project_id)
        clip_dir = dirs["clips"] / candidate.id
        clip_dir.mkdir(parents=True, exist_ok=True)
        raw_clip_path = clip_dir / "raw_clip.mp4"

        # Check cache
        if raw_clip_path.exists() and raw_clip_path.stat().st_size > 0 and not force_recompute:
            logger.info(f"Reusing existing raw cut clip: {raw_clip_path}")
            return raw_clip_path

        if not is_ffmpeg_available():
            raise RuntimeError(f"FFmpeg executable ('{settings.FFMPEG_PATH}') is required for video cutting.")

        cmd = self.build_cut_command(source_path, raw_clip_path, candidate.start_time, candidate.end_time)
        logger.info(f"Cutting clip '{candidate.title}' ({candidate.start_time:.1f}s to {candidate.end_time:.1f}s)...")

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg cut failed for clip '{candidate.id}': {e.stderr}")
            raise RuntimeError(f"FFmpeg cut failed: {e.stderr}")

        if not raw_clip_path.exists() or raw_clip_path.stat().st_size == 0:
            raise RuntimeError(f"Cut failed: Output clip '{raw_clip_path}' is empty or missing.")

        logger.info(f"Clip cut successfully: {raw_clip_path} ({round(raw_clip_path.stat().st_size / (1024 * 1024), 2)} MB)")
        return raw_clip_path

    def cut_all_selected_clips(self, project_id: str, force_recompute: bool = False) -> List[Path]:
        """Cuts all candidates marked with selected_for_rendering=True."""
        candidate_list = analysis_service.load_cached_candidates(project_id)
        if not candidate_list or not candidate_list.candidates:
            raise ValueError(f"No candidate highlights available to cut for project '{project_id}'.")

        cut_paths: List[Path] = []
        for candidate in candidate_list.candidates:
            if candidate.selected_for_rendering:
                cut_path = self.cut_candidate_clip(project_id, candidate, force_recompute=force_recompute)
                cut_paths.append(cut_path)

        storage_service.save_stage_checkpoint(project_id, "clipping", {
            "cut_count": len(cut_paths),
            "clips": [str(p) for p in cut_paths]
        })
        return cut_paths


clipping_service = ClippingService()
