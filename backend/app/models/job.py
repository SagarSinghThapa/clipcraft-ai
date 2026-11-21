"""Data models for background pipeline jobs and real-time stage progress."""

from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


class PipelineStage(str, Enum):
    IDLE = "idle"
    IMPORTING = "importing"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    FINDING_CLIPS = "finding_clips"
    REFRAMING = "reframing"
    CAPTIONING = "captioning"
    RENDERING = "rendering"
    COMPLETED = "completed"
    FAILED = "failed"


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"


class Job(BaseModel):
    id: str
    project_id: str
    status: JobStatus = JobStatus.QUEUED
    current_stage: PipelineStage = PipelineStage.IDLE
    progress_percentage: int = 0
    stage_message: str = "Initialized"
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    error: Optional[str] = None
    details: Dict[str, Any] = Field(default_factory=dict)
