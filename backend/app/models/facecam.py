"""Data models for streamer facecam detection, bounding boxes, and spatial persistence."""

from pydantic import BaseModel, Field
from typing import Optional


class FacecamRegion(BaseModel):
    """Represents a localized streamer webcam region embedded within horizontal gameplay."""
    is_detected: bool = Field(default=False, description="Whether a persistent streamer facecam was detected.")
    x: int = Field(default=0, description="Top-left X pixel coordinate in source video.")
    y: int = Field(default=0, description="Top-left Y pixel coordinate in source video.")
    width: int = Field(default=0, description="Width in pixels of the extracted webcam bounding box.")
    height: int = Field(default=0, description="Height in pixels of the extracted webcam bounding box.")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0 based on spatial persistence.")
    quadrant: str = Field(default="NONE", description="Screen quadrant (TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT, CENTER, NONE).")
    sample_count: int = Field(default=0, description="Total sampled video frames inspected.")
    detected_count: int = Field(default=0, description="Number of sampled frames where the persistent facecam was detected.")
    detected_ratio: float = Field(default=0.0, description="Ratio of sampled frames containing persistent webcam face.")
    video_width: int = Field(default=1920, description="Original source video width.")
    video_height: int = Field(default=1080, description="Original source video height.")
