"""Audio extraction service using FFmpeg to produce normalized 16kHz WAV."""

import subprocess
from pathlib import Path
from typing import Optional

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.services.storage_service import storage_service
from backend.app.utils.ffmpeg_utils import is_ffmpeg_available


class AudioService:
    """Extracts clean 16kHz 16-bit mono PCM audio from video files for transcription."""

    def get_audio_extraction_command(self, video_path: Path, output_audio_path: Path) -> list:
        """Constructs safe FFmpeg command array for 16kHz mono WAV extraction."""
        return [
            settings.FFMPEG_PATH,
            "-y",  # overwrite output
            "-i", str(video_path),
            "-vn",  # no video
            "-acodec", "pcm_s16le",  # 16-bit PCM
            "-ar", "16000",  # 16kHz sample rate optimal for Whisper
            "-ac", "1",  # mono
            str(output_audio_path)
        ]

    def extract_audio(self, project_id: str, force_recompute: bool = False) -> Path:
        """
        Extracts audio from project source video into projects/<id>/audio/audio.wav.
        Returns the path to the extracted WAV file.
        """
        project = storage_service.load_project_metadata(project_id)
        if not project or not project.source_path:
            raise ValueError(f"Project '{project_id}' does not have an ingested source video.")

        video_path = Path(project.source_path)
        if not video_path.exists():
            raise FileNotFoundError(f"Source video file not found at: {video_path}")

        dirs = storage_service.init_project_workspace(project_id)
        audio_path = dirs["audio"] / "audio.wav"

        # Check cache
        if audio_path.exists() and audio_path.stat().st_size > 0 and not force_recompute:
            logger.info(f"Reusing cached extracted audio at: {audio_path}")
            return audio_path

        if not is_ffmpeg_available():
            raise RuntimeError(
                f"FFmpeg executable ('{settings.FFMPEG_PATH}') not found in system PATH. "
                "FFmpeg is required for audio extraction."
            )

        cmd = self.get_audio_extraction_command(video_path, audio_path)
        logger.info(f"Extracting 16kHz mono audio for project '{project_id}'...")

        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg audio extraction failed: {e.stderr}")
            raise RuntimeError(f"Failed to extract audio from video: {e.stderr}")

        if not audio_path.exists() or audio_path.stat().st_size == 0:
            raise RuntimeError("Audio extraction completed but generated output file is empty or missing.")

        logger.info(f"Audio extracted successfully: {audio_path} ({round(audio_path.stat().st_size / (1024 * 1024), 2)} MB)")
        storage_service.save_stage_checkpoint(project_id, "audio_extraction", {
            "audio_path": str(audio_path),
            "size_bytes": audio_path.stat().st_size
        })
        return audio_path


audio_service = AudioService()
