"""API routes for subtitle generation, styling presets, and caption burning."""

from typing import Optional
from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from backend.app.models.caption import CaptionPreset, CaptionPlacement, CaptionStyleConfig
from backend.app.services.caption_service import caption_service
from backend.app.services.analysis_service import analysis_service
from backend.app.services.storage_service import storage_service

router = APIRouter(prefix="/api/projects/{project_id}/captions", tags=["Captions"])


class CaptionRequest(BaseModel):
    clip_id: Optional[str] = None
    force_recompute: bool = False
    preset: Optional[CaptionPreset] = Field(default=None, description="Styling preset (GAMING_KARAOKE, CLEAN, MINIMAL)")
    placement: Optional[CaptionPlacement] = Field(default=None, description="Safe-zone placement (AUTO, TOP, CENTER, LOWER_CENTER, BOTTOM)")
    karaoke_enabled: Optional[bool] = Field(default=None, description="Enable word-level gold highlighting")
    highlight_color: Optional[str] = Field(default=None, description="ASS BGR hex color for active word")
    words_per_chunk: Optional[int] = Field(default=None, ge=1, le=6, description="Words per subtitle chunk")
    font_size: Optional[int] = Field(default=None, ge=24, le=160, description="Base font size for 1080p")


@router.post("")
def burn_project_captions(project_id: str, payload: CaptionRequest):
    """Burns synchronized subtitles into candidate video clips with preset styling."""
    try:
        # Determine base style configuration
        base_preset = payload.preset or CaptionPreset.GAMING_KARAOKE
        style_config = CaptionStyleConfig.from_preset(base_preset)

        # Apply specific overrides from request
        updates = {}
        if payload.placement is not None:
            updates["placement"] = payload.placement
        if payload.karaoke_enabled is not None:
            updates["karaoke_enabled"] = payload.karaoke_enabled
        if payload.highlight_color is not None:
            updates["highlight_color"] = payload.highlight_color
        if payload.words_per_chunk is not None:
            updates["words_per_chunk"] = payload.words_per_chunk
        if payload.font_size is not None:
            updates["font_size"] = payload.font_size
        if updates:
            style_config = style_config.model_copy(update=updates)

        if payload.clip_id:
            candidates_data = analysis_service.load_cached_candidates(project_id)
            if not candidates_data:
                raise HTTPException(status_code=404, detail="No candidates found.")
            target = next((c for c in candidates_data.candidates if c.id == payload.clip_id), None)
            if not target:
                raise HTTPException(status_code=404, detail=f"Clip '{payload.clip_id}' not found.")

            # Inherit per-clip overrides if not explicitly passed in payload
            if payload.preset is None and target.caption_preset is not None:
                style_config = CaptionStyleConfig.from_preset(target.caption_preset)
            if payload.placement is None and target.caption_placement is not None:
                style_config = style_config.model_copy(update={"placement": target.caption_placement})

            path = caption_service.burn_captions_for_clip(
                project_id,
                target,
                force_recompute=payload.force_recompute,
                style_config=style_config
            )
            return {
                "status": "success",
                "final_clips": [str(path)],
                "preset": style_config.preset.value,
                "placement": style_config.placement.value
            }
        else:
            paths = caption_service.burn_all_selected_clips(
                project_id,
                force_recompute=payload.force_recompute,
                style_config=style_config
            )
            return {
                "status": "success",
                "final_clips": [str(p) for p in paths],
                "preset": style_config.preset.value,
                "placement": style_config.placement.value
            }
    except HTTPException:
        raise
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Captioning failed: {e}")


@router.get("/{clip_id}/srt")
async def download_clip_srt(project_id: str, clip_id: str):
    """Downloads standalone .srt subtitle file for a clip."""
    dirs = storage_service.init_project_workspace(project_id)
    srt_file = dirs["clips"] / clip_id / "captions.srt"
    if not srt_file.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="SRT subtitle file not found for this clip.")
    return FileResponse(path=str(srt_file), filename=f"{clip_id}_captions.srt", media_type="text/plain")
