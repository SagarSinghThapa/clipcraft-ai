"""Data models for caption presets, placement zones, typography styling, and word-level karaoke timing."""

from enum import Enum
from typing import List, Optional, Tuple
from pydantic import BaseModel, Field


class CaptionPlacement(str, Enum):
    """Vertical placement zones for caption rendering."""
    AUTO = "AUTO"                  # Automatically picks safe zone based on layout geometry
    TOP = "TOP"                    # Below top bezel (Y ≈ 160)
    CENTER = "CENTER"              # Screen center (Y ≈ 960 on 1080p)
    LOWER_CENTER = "LOWER_CENTER"  # Seam position below streamer facecam (Y ≈ 760..840)
    BOTTOM = "BOTTOM"              # Bottom safe zone above mobile UI controls (Y ≈ 1520..1600)


class CaptionPreset(str, Enum):
    """Pre-configured caption styling presets."""
    GAMING_KARAOKE = "GAMING_KARAOKE"  # Bold uppercase, gold active-word highlight, seam-aware
    CLEAN = "CLEAN"                    # Professional static white text, black outline, bottom
    MINIMAL = "MINIMAL"                # Subtle, smaller typography, thin outline


class WordEmphasis(str, Enum):
    """Emphasis level for active or reactive words."""
    NORMAL = "normal"
    STRONG = "strong"      # Punctuation emphasis, exclamations, or capitalized shouts
    REACTION = "reaction"  # High audio reaction surge word (Phase 13 hook)


class StyledWordTiming(BaseModel):
    """Word-level timing information with emphasis styling metadata."""
    word: str
    start: float = Field(..., description="Clip-relative start time in seconds.")
    end: float = Field(..., description="Clip-relative end time in seconds.")
    emphasis: WordEmphasis = Field(default=WordEmphasis.NORMAL)
    probability: float = Field(default=1.0)


class CaptionChunk(BaseModel):
    """A short, readable group of words (2–5 words) displayed together."""
    text: str
    start: float
    end: float
    words: List[StyledWordTiming] = Field(default_factory=list)

    def __getitem__(self, item: str):
        """Allow dict-like subscripting for backward compatibility with existing tests/callers."""
        return getattr(self, item)


class CaptionStyleConfig(BaseModel):
    """Configuration options for subtitle typography, colors, animations, and placement."""
    preset: CaptionPreset = Field(default=CaptionPreset.GAMING_KARAOKE)
    placement: CaptionPlacement = Field(default=CaptionPlacement.AUTO)
    font_size: int = Field(default=64, ge=24, le=160, description="Base font size for 1080x1920 canvas.")
    font_name: str = Field(default="Arial", description="Font family name for ASS rendering.")
    highlight_color: str = Field(default="&H0000E6FF&", description="Vibrant Neon Gold/Yellow in ASS BGR hex.")
    primary_color: str = Field(default="&H00FFFFFF&", description="Crisp Solid White in ASS BGR hex.")
    outline_color: str = Field(default="&H00000000&", description="Solid Black stroke in ASS BGR hex.")
    outline_width: int = Field(default=5, ge=0, le=20)
    shadow_offset: int = Field(default=2, ge=0, le=10)
    karaoke_enabled: bool = Field(default=True, description="Whether to illuminate active spoken words in gold.")
    words_per_chunk: int = Field(default=3, ge=1, le=6, description="Target words per subtitle group.")
    uppercase: bool = Field(default=True, description="Force uppercase for energetic gaming readability.")
    active_pop_percent: int = Field(default=6, ge=0, le=25, description="Subtle scale percentage for active word (e.g. 6% = \\fscx106\\fscy106).")

    @classmethod
    def from_preset(cls, preset: CaptionPreset) -> "CaptionStyleConfig":
        """Factory constructor returning standard configurations for presets."""
        if preset == CaptionPreset.CLEAN:
            return cls(
                preset=CaptionPreset.CLEAN,
                placement=CaptionPlacement.BOTTOM,
                font_size=60,
                karaoke_enabled=False,
                uppercase=False,
                outline_width=4,
                shadow_offset=2,
                words_per_chunk=4
            )
        elif preset == CaptionPreset.MINIMAL:
            return cls(
                preset=CaptionPreset.MINIMAL,
                placement=CaptionPlacement.BOTTOM,
                font_size=48,
                karaoke_enabled=False,
                uppercase=False,
                outline_width=3,
                shadow_offset=0,
                words_per_chunk=4
            )
        else:
            # Default GAMING_KARAOKE
            return cls(
                preset=CaptionPreset.GAMING_KARAOKE,
                placement=CaptionPlacement.AUTO,
                font_size=64,
                karaoke_enabled=True,
                uppercase=True,
                outline_width=5,
                shadow_offset=2,
                words_per_chunk=3
            )

    def get_scaled_config(self, canvas_h: int = 1920) -> "CaptionStyleConfig":
        """Returns a copy with font size, outline, and shadow scaled proportionally for canvas resolution."""
        scale = canvas_h / 1920.0
        return self.model_copy(update={
            "font_size": max(20, int(round(self.font_size * scale))),
            "outline_width": max(1, int(round(self.outline_width * scale))),
            "shadow_offset": max(0, int(round(self.shadow_offset * scale)))
        })

    def get_placement_geometry(
        self,
        canvas_h: int = 1920,
        top_height: Optional[int] = None
    ) -> Tuple[int, int]:
        """
        Calculates exact (margin_v, alignment) in ASS coordinates.
        ASS Alignment: 2 = Bottom-Center, 5 = Mid-Center, 8 = Top-Center.
        """
        scale = canvas_h / 1920.0
        effective_placement = self.placement

        if effective_placement == CaptionPlacement.AUTO:
            if top_height is not None and top_height > 0:
                effective_placement = CaptionPlacement.LOWER_CENTER
            else:
                effective_placement = CaptionPlacement.BOTTOM

        if effective_placement == CaptionPlacement.TOP:
            # Alignment 8 (Top-Center), offset from top bezel
            margin_v = int(round(160 * scale))
            return margin_v, 8

        elif effective_placement == CaptionPlacement.CENTER:
            # Alignment 5 (Mid-Center)
            return 0, 5

        elif effective_placement == CaptionPlacement.LOWER_CENTER:
            # Anchor right below top streamer section in the seam
            if top_height is not None and top_height > 0:
                # Top-Center alignment below streamer box
                seam_offset = int(round(35 * scale))
                margin_v = top_height + seam_offset
                return margin_v, 8
            else:
                # Fallback to mid-lower region (Alignment 2, Bottom-Center)
                margin_v = int(round(1080 * scale))
                return margin_v, 2

        else:
            # BOTTOM (Default for single-stream shots, safe above mobile UI)
            margin_v = int(round(320 * scale))
            return margin_v, 2
