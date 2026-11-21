"""Data models for gaming vertical layouts, resolution presets, and crop windows."""

from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, Field


class LayoutStrategy(str, Enum):
    """Supported vertical reframing and compositing strategies."""
    GAMING_SPLIT = "GAMING_SPLIT"            # Top: Streamer Facecam / Bottom: Gameplay
    GAMEPLAY_FOCUS = "GAMEPLAY_FOCUS"        # Gameplay occupies full canvas (smart crop or blurred extension)
    STREAMER_FOCUS = "STREAMER_FOCUS"        # Streamer reaction occupies main canvas with blurred context
    AUTO_GAMING = "AUTO_GAMING"              # Auto-selects GAMING_SPLIT if facecam is present, else GAMEPLAY_FOCUS
    STANDARD_FACE_TRACK = "STANDARD_FACE_TRACK"  # Standard single-speaker 9:16 face tracking (talking head)
    CENTER_CROP = "CENTER_CROP"              # Direct 9:16 center crop


class GameplayCompositionMode(str, Enum):
    """Gameplay presentation mode within the vertical gaming canvas."""
    CROP_FILL = "CROP_FILL"          # Crops a 9:10 window to fill the bottom region completely
    FIT_WITH_BLUR = "FIT_WITH_BLUR"  # Fits uncropped widescreen gameplay foreground over blurred background
    AUTO = "AUTO"                    # Chooses between CROP_FILL and FIT_WITH_BLUR based on content loss


class ExcludedRegion(BaseModel):
    """Region of source frame to exclude from gameplay analysis and composition (e.g. stream chat, webcam)."""
    x: int = Field(..., description="Top-left X coordinate.")
    y: int = Field(..., description="Top-left Y coordinate.")
    width: int = Field(..., description="Width of excluded region.")
    height: int = Field(..., description="Height of excluded region.")
    label: str = Field(default="overlay", description="Label for excluded area (e.g. chat_overlay, facecam).")


class CanvasResolution(str, Enum):
    """Standard vertical export resolution presets (9:16 canvas)."""
    FHD_1080x1920 = "1080x1920"  # Full HD (Standard vertical shorts/TikTok/Reels)
    QHD_1440x2560 = "1440x2560"  # 1440p / 2K vertical
    UHD_2160x3840 = "2160x3840"  # 4K UHD vertical


class CanvasDimensions(BaseModel):
    """Calculated pixel dimensions for stacked vertical regions."""
    width: int = Field(..., description="Total canvas width in pixels (e.g. 1080)")
    height: int = Field(..., description="Total canvas height in pixels (e.g. 1920)")
    top_height: int = Field(..., description="Top streamer facecam region height (e.g. 720)")
    bottom_height: int = Field(..., description="Bottom gameplay region height (e.g. 1200)")
    aspect_ratio: str = Field(default="9:16", description="Overall canvas aspect ratio")

    @property
    def top_aspect_ratio(self) -> float:
        return self.width / self.top_height if self.top_height > 0 else 1.5

    @property
    def bottom_aspect_ratio(self) -> float:
        return self.width / self.bottom_height if self.bottom_height > 0 else 0.9


class GameplayCropWindow(BaseModel):
    """Bounding box for the extracted gameplay region."""
    x: int = Field(default=0, description="Top-left X coordinate in source media.")
    y: int = Field(default=0, description="Top-left Y coordinate in source media.")
    width: int = Field(..., description="Crop window width.")
    height: int = Field(..., description="Crop window height.")
    aspect_ratio: str = Field(default="9:10", description="Aspect ratio of the cropped sub-rectangle.")


class GamingLayoutConfig(BaseModel):
    """Configuration options for gaming vertical composition."""
    strategy: LayoutStrategy = Field(
        default=LayoutStrategy.AUTO_GAMING,
        description="Layout compositing strategy to apply."
    )
    resolution: CanvasResolution = Field(
        default=CanvasResolution.FHD_1080x1920,
        description="Target vertical export resolution preset."
    )
    split_ratio: float = Field(
        default=0.375,
        ge=0.20,
        le=0.60,
        description="Proportion of vertical height allocated to the streamer facecam (default 0.375 = 720/1920)."
    )
    smooth_alpha: float = Field(
        default=0.10,
        ge=0.01,
        le=1.0,
        description="Exponential Moving Average (EMA) smoothing factor for horizontal gameplay tracking."
    )
    blur_background: bool = Field(
        default=True,
        description="Whether to use blurred background extension for aspect-mismatched focus layouts."
    )
    gameplay_composition: GameplayCompositionMode = Field(
        default=GameplayCompositionMode.AUTO,
        description="Gameplay presentation mode within bottom region: CROP_FILL, FIT_WITH_BLUR, or AUTO."
    )
    excluded_overlay_regions: Optional[List[ExcludedRegion]] = Field(
        default=None,
        description="List of bounding boxes to mask out from gameplay analysis and composition (e.g. stream chat)."
    )
    exclude_chat_overlay: bool = Field(
        default=True,
        description="Whether to automatically detect or exclude persistent side chat/comment overlays."
    )

    def get_dimensions(self) -> CanvasDimensions:
        """Computes exact even pixel dimensions for top and bottom regions based on resolution and split ratio."""
        dim_map = {
            CanvasResolution.FHD_1080x1920: (1080, 1920),
            CanvasResolution.QHD_1440x2560: (1440, 2560),
            CanvasResolution.UHD_2160x3840: (2160, 3840),
        }
        total_w, total_h = dim_map.get(self.resolution, (1080, 1920))

        # Calculate top height and force even integer pixels
        raw_top_h = int(round(total_h * self.split_ratio))
        top_h = raw_top_h if raw_top_h % 2 == 0 else raw_top_h + 1
        bottom_h = total_h - top_h

        return CanvasDimensions(
            width=total_w,
            height=total_h,
            top_height=top_h,
            bottom_height=bottom_h,
            aspect_ratio="9:16"
        )
