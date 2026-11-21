"""Data models for reaction-aware audio energy analysis, surge detection, and categories."""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class ReactionCategory(str, Enum):
    """Semantic gaming and streamer reaction categories."""
    FUNNY_REACTION = "FUNNY_REACTION"      # Laughter, mockery, hilarious fails
    SURPRISE = "SURPRISE"                  # Jumpscares, sudden unexpected events
    CHAOTIC_MOMENT = "CHAOTIC_MOMENT"      # Multi-vehicle pileups, madness, glitch
    FAIL = "FAIL"                          # Player death, mission failed, blown up
    RAGE = "RAGE"                          # Desk slam, shouting in frustration, anger
    EPIC_MOMENT = "EPIC_MOMENT"            # Insane clutch, miracle escape, stunt
    WIN = "WIN"                            # Mission passed, high-stakes victory
    FUNNY_DIALOGUE = "FUNNY_DIALOGUE"      # Witty banter, absurd NPC conversation
    STORY_MOMENT = "STORY_MOMENT"          # Cinematic plot twist, dramatic cutscene
    GENERAL_HIGHLIGHT = "GENERAL_HIGHLIGHT"# Standard notable engagement


def calculate_audio_reaction_score(
    peak_z: float,
    local_contrast: float,
    density: float,
    speech_confirmed: bool = True
) -> float:
    """
    Computes a bounded 0-100 audio reaction score based on peak Z-score,
    local baseline contrast, reaction surge density, and speech corroboration.
    """
    # Raw weighted reaction composite
    raw_score = 45.0 + (12.0 * max(0.0, peak_z)) + (6.0 * max(0.0, local_contrast)) + (25.0 * max(0.0, density))
    score = max(0.0, min(100.0, raw_score))

    # Apply penalty if the loudness spike is non-speech (e.g. game explosion or loud music)
    if not speech_confirmed:
        score *= 0.60

    return float(round(max(0.0, min(100.0, score)), 2))


class AudioEnergyWindow(BaseModel):
    """Telemetry for an individual 500ms sliding audio analysis window."""
    index: int
    timestamp_sec: float
    rms: float
    z_global: float
    delta_local: float
    is_surge: bool = False
    speech_confirmed: bool = False


class GlobalAudioStats(BaseModel):
    """Track-wide audio baseline metrics used for statistical normalization."""
    duration_sec: float
    mean_rms: float
    std_rms: float
    max_rms: float
    median_rms: float
    window_count: int
    step_sec: float = 0.25


class ClipAudioProfile(BaseModel):
    """Aggregated reaction audio energy metrics for a specific candidate highlight window."""
    start_time: float
    end_time: float
    peak_rms: float
    mean_rms: float
    peak_z_score: float
    local_contrast_peak: float
    surge_count: int
    reaction_density: float
    has_speech_corroboration: bool = True
    audio_reaction_score: float = Field(..., ge=0.0, le=100.0)
    category: ReactionCategory = Field(default=ReactionCategory.GENERAL_HIGHLIGHT)
