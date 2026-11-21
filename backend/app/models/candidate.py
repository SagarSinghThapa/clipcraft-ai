"""Data models for candidate highlight clips and multi-factor engagement scores."""

from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field

from backend.app.models.audio import ReactionCategory
from backend.app.models.layout import LayoutStrategy, GameplayCompositionMode, CanvasResolution
from backend.app.models.caption import CaptionPreset, CaptionPlacement


class ScoreBreakdown(BaseModel):
    """Detailed explainable sub-metrics contributing to the overall multimodal quality score."""
    # Legacy engagement factors (preserved for compatibility)
    hook_strength: float = Field(default=20.0, ge=0.0, le=25.0, description="Hook grab strength in first 3-5 seconds")
    standalone_clarity: float = Field(default=20.0, ge=0.0, le=25.0, description="Makes sense without prior context")
    information_density: float = Field(default=20.0, ge=0.0, le=25.0, description="Value per second without filler")
    pacing_and_flow: float = Field(default=20.0, ge=0.0, le=25.0, description="Rhythm, pauses, and cadence")

    # Multimodal Phase 13 factors (0-100 scale)
    category: ReactionCategory = Field(default=ReactionCategory.GENERAL_HIGHLIGHT, description="Detected streamer reaction category")
    transcript_context_score: float = Field(default=75.0, ge=0.0, le=100.0, description="Semantic narrative and reaction relevance from transcript")
    audio_reaction_score: float = Field(default=50.0, ge=0.0, le=100.0, description="Vocal surge energy and speech-corroborated audio score")
    streamer_visual_reaction_score: float = Field(default=50.0, ge=0.0, le=100.0, description="Streamer facecam visual motion and reaction score")
    gameplay_activity_score: float = Field(default=50.0, ge=0.0, le=100.0, description="In-game visual motion/action score")
    hook_score: float = Field(default=75.0, ge=0.0, le=100.0, description="Opening grab strength on 0-100 scale")
    payoff_score: float = Field(default=70.0, ge=0.0, le=100.0, description="Resolution and standalone climax delivery")
    penalties: float = Field(default=0.0, ge=0.0, le=100.0, description="Cumulative penalties deducted (dead air, cutoff, noise)")
    peak_z_score: float = Field(default=0.0, description="Max audio energy Z-score within clip")
    reaction_density: float = Field(default=0.0, description="Density of reaction surge events per minute")

    total_score: int = Field(default=80, ge=0, le=100, description="Overall calibrated engagement score from 0-100")
    explanation: str = "Strong initial hook with clear standalone message."


class CandidateClip(BaseModel):
    """A scored video highlight segment identified as suitable for short-form export."""
    id: str
    project_id: str
    title: str
    start_time: float
    end_time: float
    duration: float
    transcript_excerpt: str
    hook_assessment: str
    standalone_context: str
    reasoning: str
    score: ScoreBreakdown
    selected_for_rendering: bool = True
    rendered_clip_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Phase 14 Layout, Composition, Quality, and Caption Overrides:
    layout_strategy: Optional[LayoutStrategy] = None
    gameplay_composition: Optional[GameplayCompositionMode] = None
    split_ratio: Optional[float] = Field(default=None, ge=0.20, le=0.60)
    exclude_chat_overlay: Optional[bool] = None
    caption_preset: Optional[CaptionPreset] = None
    caption_placement: Optional[CaptionPlacement] = None
    resolution: Optional[CanvasResolution] = None


class CandidateList(BaseModel):
    """List of candidate clips generated for a project."""
    project_id: str
    candidates: List[CandidateClip] = Field(default_factory=list)
    model_used: str = "llama3.2:3b"
    created_at: datetime = Field(default_factory=datetime.utcnow)
