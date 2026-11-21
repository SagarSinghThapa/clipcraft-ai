"""Data models for speech-to-text transcripts and word-level timestamps."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class WordTiming(BaseModel):
    """Timestamp and confidence for an individual spoken word."""
    word: str
    start: float
    end: float
    probability: float = 1.0


class TranscriptSegment(BaseModel):
    """A natural sentence or utterance segment with associated words."""
    id: int
    start: float
    end: float
    text: str
    words: List[WordTiming] = Field(default_factory=list)


class FullTranscript(BaseModel):
    """Full transcript of the video audio with complete segment and word timing data."""
    project_id: str
    language: str = "en"
    duration: float = 0.0
    full_text: str = ""
    segments: List[TranscriptSegment] = Field(default_factory=list)
    model_name: str = "base"
    created_at: datetime = Field(default_factory=datetime.utcnow)
