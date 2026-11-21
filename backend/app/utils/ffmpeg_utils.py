"""FFmpeg and FFprobe execution utilities and metadata inspection."""

import json
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.models.project import MediaMetadata


def is_ffmpeg_available() -> bool:
    """Checks whether FFmpeg executable is installed and reachable in PATH."""
    return shutil.which(settings.FFMPEG_PATH) is not None


def is_ffprobe_available() -> bool:
    """Checks whether FFprobe executable is installed and reachable in PATH."""
    return shutil.which(settings.FFPROBE_PATH) is not None


def escape_ffmpeg_path(path: Path) -> str:
    """
    Escapes a filesystem path for safe use inside FFmpeg filtergraphs on Windows.
    Converts backslashes to forward slashes and escapes colons (e.g. C\\:/path/file.ass).
    """
    posix_path = path.as_posix()
    # In Windows drive letters like 'C:/...', colons must be escaped as 'C\:/...'
    if len(posix_path) > 1 and posix_path[1] == ":":
        return posix_path[0] + "\\:" + posix_path[2:]
    return posix_path


def probe_media_metadata(file_path: Path) -> MediaMetadata:
    """
    Runs ffprobe on a media file to inspect duration, resolution, codecs, and audio.
    Raises RuntimeError with descriptive explanation if ffprobe fails or file is invalid.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Media file does not exist: {file_path}")

    if not is_ffprobe_available():
        # If ffprobe is not installed on host, return estimated metadata based on file existence
        logger.warning("ffprobe executable not found in PATH. Returning fallback metadata.")
        return MediaMetadata(
            duration=0.0,
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            fps=30.0,
            video_codec="unknown",
            audio_codec="unknown",
            has_audio=True,
            file_size_bytes=file_path.stat().st_size
        )

    cmd = [
        settings.FFPROBE_PATH,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path)
    ]

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(proc.stdout)
    except subprocess.CalledProcessError as e:
        logger.error(f"FFprobe execution failed on {file_path}: {e.stderr}")
        raise RuntimeError(f"Unable to probe media file. It may be corrupted or unsupported: {e.stderr}")
    except json.JSONDecodeError as e:
        logger.error(f"FFprobe produced invalid JSON: {e}")
        raise RuntimeError("Failed to parse media probe metadata.")

    format_info = data.get("format", {})
    streams = data.get("streams", [])

    duration = float(format_info.get("duration", 0.0))
    file_size = int(format_info.get("size", file_path.stat().st_size))

    video_stream = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in streams if s.get("codec_type") == "audio"), None)

    width = int(video_stream.get("width", 0)) if video_stream else 0
    height = int(video_stream.get("height", 0)) if video_stream else 0
    video_codec = video_stream.get("codec_name", "none") if video_stream else "none"
    audio_codec = audio_stream.get("codec_name", "none") if audio_stream else "none"
    has_audio = audio_stream is not None

    # Calculate FPS
    fps = 30.0
    if video_stream and "r_frame_rate" in video_stream:
        r_rate = video_stream["r_frame_rate"]
        if "/" in r_rate:
            num, den = r_rate.split("/")
            if float(den) > 0:
                fps = round(float(num) / float(den), 2)
        else:
            try:
                fps = round(float(r_rate), 2)
            except ValueError:
                pass

    aspect_ratio = "16:9"
    if width > 0 and height > 0:
        ratio = round(width / height, 2)
        if ratio == 0.56:
            aspect_ratio = "9:16"
        elif ratio == 1.0:
            aspect_ratio = "1:1"
        elif ratio == 1.78:
            aspect_ratio = "16:9"
        else:
            aspect_ratio = f"{width}:{height}"

    return MediaMetadata(
        duration=duration,
        width=width,
        height=height,
        aspect_ratio=aspect_ratio,
        fps=fps,
        video_codec=video_codec,
        audio_codec=audio_codec,
        has_audio=has_audio,
        file_size_bytes=file_size
    )
