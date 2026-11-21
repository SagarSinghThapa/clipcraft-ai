"""Application configuration management for the AI Video Clipper."""

from pathlib import Path
from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings resolved from environment variables or defaults."""

    APP_NAME: str = "ClipCraft AI"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    HOST: str = "127.0.0.1"
    PORT: int = 8000

    # Project directories
    WORKSPACE_ROOT: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3])
    PROJECTS_DIR: Path = Field(default_factory=lambda: Path(__file__).resolve().parents[3] / "projects")

    # Hardware & Performance
    DEVICE: str = "auto"  # 'auto', 'cuda', or 'cpu'
    COMPUTE_TYPE: str = "auto"  # 'auto', 'float16', 'int8'
    MAX_CONCURRENT_JOBS: int = 2

    # External Tools
    FFMPEG_PATH: str = "ffmpeg"
    FFPROBE_PATH: str = "ffprobe"
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    DEFAULT_WHISPER_MODEL: str = "base"
    DEFAULT_LLM_MODEL: str = "llama3.2:3b"

    # Clipping Defaults
    DEFAULT_TARGET_ASPECT_RATIO: str = "9:16"
    TARGET_WIDTH: int = 1080
    TARGET_HEIGHT: int = 1920
    DEFAULT_MIN_CLIP_DURATION: int = 15
    DEFAULT_MAX_CLIP_DURATION: int = 60
    DEFAULT_CANDIDATE_COUNT: int = 5

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
