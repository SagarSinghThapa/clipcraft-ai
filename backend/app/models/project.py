"""Data models for Project definitions and metadata."""

from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

from backend.app.models.facecam import FacecamRegion


class SourceType(str, Enum):
    LOCAL_FILE = "local_file"
    YOUTUBE = "youtube"


class ProjectStatus(str, Enum):
    CREATED = "created"
    INGESTED = "ingested"
    PROCESSING = "processing"
    READY_FOR_REVIEW = "ready_for_review"
    COMPLETED = "completed"
    FAILED = "failed"


class MediaMetadata(BaseModel):
    """Probed metadata of source video media."""
    duration: float = 0.0
    width: int = 0
    height: int = 0
    aspect_ratio: str = "16:9"
    fps: float = 30.0
    video_codec: str = "unknown"
    audio_codec: str = "unknown"
    has_audio: bool = True
    file_size_bytes: int = 0
    facecam_region: Optional[FacecamRegion] = None


class ProjectCreate(BaseModel):
    title: Optional[str] = None
    source_type: SourceType
    source_url: Optional[str] = None
    min_clip_duration: int = 15
    max_clip_duration: int = 60
    candidate_count: int = 5
    whisper_model: str = "base"
    llm_model: str = "llama3.2:3b"


class Project(BaseModel):
    id: str
    title: str
    source_type: SourceType
    source_path: Optional[str] = None
    source_url: Optional[str] = None
    status: ProjectStatus = ProjectStatus.CREATED
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    metadata: Optional[MediaMetadata] = None
    error: Optional[str] = None
    settings: Dict[str, Any] = Field(default_factory=dict)
