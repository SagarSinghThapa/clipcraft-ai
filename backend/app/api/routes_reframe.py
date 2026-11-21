"""API routes for 9:16 vertical video reframing and gaming layout compositing."""

from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.models.layout import LayoutStrategy, CanvasResolution, GameplayCompositionMode, GamingLayoutConfig
from backend.app.services.reframing_service import reframing_service
from backend.app.services.analysis_service import analysis_service

router = APIRouter(prefix="/api/projects/{project_id}/reframe", tags=["Reframing"])


class ReframeRequest(BaseModel):
    clip_id: Optional[str] = None
    force_recompute: bool = False
    layout_strategy: Optional[LayoutStrategy] = None
    resolution: Optional[CanvasResolution] = None
    split_ratio: Optional[float] = None
    gameplay_composition: Optional[GameplayCompositionMode] = None
    exclude_chat_overlay: Optional[bool] = None


@router.post("")
def reframe_project_clips(project_id: str, payload: ReframeRequest):
    """Executes 9:16 vertical reframing with face tracking or gaming split compositing."""
    try:
        layout_config: Optional[GamingLayoutConfig] = None
        if (
            payload.layout_strategy
            or payload.resolution
            or payload.split_ratio is not None
            or payload.gameplay_composition
            or payload.exclude_chat_overlay is not None
        ):
            layout_config = GamingLayoutConfig(
                strategy=payload.layout_strategy or LayoutStrategy.AUTO_GAMING,
                resolution=payload.resolution or CanvasResolution.FHD_1080x1920,
                split_ratio=payload.split_ratio if payload.split_ratio is not None else 0.30,
                gameplay_composition=payload.gameplay_composition or GameplayCompositionMode.AUTO,
                exclude_chat_overlay=payload.exclude_chat_overlay if payload.exclude_chat_overlay is not None else True,
            )

        if payload.clip_id:
            path = reframing_service.reframe_clip(
                project_id,
                payload.clip_id,
                force_recompute=payload.force_recompute,
                layout_config=layout_config
            )
            return {"status": "success", "reframed_clips": [str(path)]}
        else:
            candidates_data = analysis_service.load_cached_candidates(project_id)
            if not candidates_data or not candidates_data.candidates:
                raise HTTPException(status_code=404, detail="No candidate clips found.")

            paths = []
            for c in candidates_data.candidates:
                if c.selected_for_rendering:
                    p = reframing_service.reframe_clip(
                        project_id,
                        c.id,
                        force_recompute=payload.force_recompute,
                        layout_config=layout_config
                    )
                    paths.append(str(p))

            return {"status": "success", "reframed_clips": paths}
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Reframing failed: {e}")
