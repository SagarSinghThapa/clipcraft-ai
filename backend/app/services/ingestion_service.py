"""Media ingestion service supporting local files and authorized YouTube downloads."""

import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse

from backend.app.core.logger import logger
from backend.app.models.project import Project, ProjectStatus, SourceType, MediaMetadata
from backend.app.services.storage_service import storage_service
from backend.app.utils.ffmpeg_utils import probe_media_metadata


SUPPORTED_LOCAL_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv"}


class IngestionService:
    """Handles local video imports and yt-dlp media extraction."""

    def validate_youtube_url(self, url: str) -> bool:
        """Validates that a URL is a legitimate YouTube link."""
        if not url:
            return False
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            return False
        netloc = parsed.netloc.lower()
        if netloc in ("youtube.com", "www.youtube.com", "m.youtube.com"):
            return bool(parsed.query and "v=" in parsed.query) or parsed.path.startswith("/shorts/")
        if netloc in ("youtu.be", "www.youtu.be"):
            return len(parsed.path.strip("/")) > 0
        return False

    def ingest_local_file(self, project_id: str, file_path_str: str) -> Project:
        """
        Validates and copies a local video file into the project source workspace.
        Probes stream metadata and updates project status.
        """
        source_file = Path(file_path_str).resolve()
        if not source_file.exists() or not source_file.is_file():
            raise FileNotFoundError(f"Local file does not exist or is not a regular file: {file_path_str}")

        ext = source_file.suffix.lower()
        if ext not in SUPPORTED_LOCAL_EXTENSIONS:
            allowed = ", ".join(sorted(SUPPORTED_LOCAL_EXTENSIONS))
            raise ValueError(f"Unsupported video format '{ext}'. Supported formats: {allowed}")

        project = storage_service.load_project_metadata(project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found.")

        dirs = storage_service.init_project_workspace(project_id)
        dest_filename = f"source{ext}"
        dest_path = dirs["source"] / dest_filename

        # Copy source video into isolated project workspace
        logger.info(f"Ingesting local video '{source_file}' into project '{project_id}'...")
        shutil.copy2(source_file, dest_path)

        # Probe metadata
        metadata = probe_media_metadata(dest_path)

        project.source_path = str(dest_path)
        project.metadata = metadata
        project.status = ProjectStatus.INGESTED
        project.error = None
        storage_service.save_project_metadata(project)
        storage_service.save_stage_checkpoint(project_id, "ingestion", {
            "source_path": str(dest_path),
            "metadata": metadata.model_dump(),
        })

        logger.info(f"Local file ingested successfully for project '{project_id}'. Duration: {metadata.duration}s")
        return project

    def ingest_youtube_url(self, project_id: str, url: str) -> Project:
        """
        Downloads authorized YouTube video via yt-dlp into the project source workspace.
        Never bypasses DRM, paywalls, or authentication locks.
        """
        if not self.validate_youtube_url(url):
            raise ValueError("Invalid YouTube URL. Please provide a standard public YouTube watch or shorts URL.")

        project = storage_service.load_project_metadata(project_id)
        if not project:
            raise ValueError(f"Project '{project_id}' not found.")

        dirs = storage_service.init_project_workspace(project_id)
        output_template = str(dirs["source"] / "source.%(ext)s")

        logger.info(f"Downloading authorized YouTube video '{url}' for project '{project_id}'...")

        # yt-dlp invocation using safe argument array
        # Resolve yt-dlp binary (executable on PATH or active Python virtual environment module)
        ytdlp_bin = shutil.which("yt-dlp")
        if ytdlp_bin:
            cmd = [ytdlp_bin]
        else:
            cmd = [sys.executable, "-m", "yt_dlp"]

        # Target standard MP4 container with max 1080p to balance speed and quality
        cmd.extend([
            "--no-playlist",
            "--format", "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/best[ext=mp4]/best",
            "--merge-output-format", "mp4",
            "-o", output_template,
            url
        ])

        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
            logger.info("yt-dlp download completed.")
        except FileNotFoundError:
            raise RuntimeError(
                "yt-dlp executable not found on system PATH. "
                "Please ensure yt-dlp is installed (`pip install yt-dlp` or install via winget)."
            )
        except subprocess.CalledProcessError as e:
            err_msg = e.stderr or e.stdout
            logger.error(f"yt-dlp failed: {err_msg}")
            if "DRM" in err_msg or "protected" in err_msg.lower():
                raise PermissionError("Video is DRM protected or restricted and cannot be downloaded.")
            if "private" in err_msg.lower():
                raise PermissionError("Video is marked as Private and cannot be accessed.")
            if "sign in" in err_msg.lower() or "bot" in err_msg.lower():
                raise PermissionError("YouTube requested authentication or bot verification. Cannot proceed.")
            raise RuntimeError(f"YouTube ingestion failed: {err_msg.strip().splitlines()[-1] if err_msg else 'Unknown error'}")

        # Locate downloaded file in source directory
        source_files = list(dirs["source"].glob("source.*"))
        if not source_files:
            raise RuntimeError("Downloaded media file not found in project source directory.")

        downloaded_file = source_files[0]
        metadata = probe_media_metadata(downloaded_file)

        project.source_path = str(downloaded_file)
        project.source_url = url
        project.metadata = metadata
        project.status = ProjectStatus.INGESTED
        project.error = None
        storage_service.save_project_metadata(project)
        storage_service.save_stage_checkpoint(project_id, "ingestion", {
            "source_path": str(downloaded_file),
            "source_url": url,
            "metadata": metadata.model_dump(),
        })

        logger.info(f"YouTube ingestion completed for project '{project_id}'. File: {downloaded_file.name}")
        return project


ingestion_service = IngestionService()
