"""API routes for cutting video clips."""

from typing import Optional, List
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.services.clipping_service import clipping_service
from backend.app.services.analysis_service import analysis_service

router = APIRouter(prefix="/api/projects/{project_id}/clips", tags=["Clipping"])


class CutRequest(BaseModel):
    clip_id: Optional[str] = None
    force_recompute: bool = False


@router.post("/cut")
async def cut_project_clips(project_id: str, payload: CutRequest):
    """Executes frame-accurate FFmpeg cuts for selected candidates."""
    try:
        if payload.clip_id:
            candidates_data = analysis_service.load_cached_candidates(project_id)
            if not candidates_data:
                raise HTTPException(status_code=404, detail="No candidates found.")
            target = next((c for c in candidates_data.candidates if c.id == payload.clip_id), None)
            if not target:
                raise HTTPException(status_code=404, detail=f"Clip '{payload.clip_id}' not found.")
            path = clipping_service.cut_candidate_clip(project_id, target, force_recompute=payload.force_recompute)
            return {"status": "success", "cut_clips": [str(path)]}
        else:
            paths = clipping_service.cut_all_selected_clips(project_id, force_recompute=payload.force_recompute)
            return {"status": "success", "cut_clips": [str(p) for p in paths]}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Clipping failed: {e}")
