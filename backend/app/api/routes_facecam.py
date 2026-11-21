"""API routes for Streamer Facecam detection, inspection, and visual debug framing."""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, status, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel

from backend.app.core.logger import logger
from backend.app.models.facecam import FacecamRegion
from backend.app.models.project import MediaMetadata
from backend.app.services.storage_service import storage_service
from backend.app.services.facecam_service import facecam_service

router = APIRouter(prefix="/api/projects/{project_id}/facecam", tags=["Facecam"])


class FacecamDetectRequest(BaseModel):
    force_recompute: bool = False
    sample_interval_sec: float = 2.5
    max_samples: int = 150


@router.post("/detect", response_model=FacecamRegion)
def detect_facecam(
    project_id: str,
    payload: Optional[FacecamDetectRequest] = None,
):
    """
    Analyzes project source video to identify persistent streamer webcam regions.
    Saves detection result to checkpoint_facecam.json and project metadata.
    """
    payload = payload or FacecamDetectRequest()
    project = storage_service.load_project_metadata(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found."
        )

    dirs = storage_service.init_project_workspace(project_id)

    # Return cached result if already completed and recompute not requested
    if not payload.force_recompute:
        cached = storage_service.load_stage_checkpoint(project_id, "facecam")
        if cached:
            return FacecamRegion(**cached)

    # Resolve source video file
    source_path: Optional[Path] = None
    if project.source_path:
        p = Path(project.source_path)
        if p.exists():
            source_path = p

    if not source_path:
        source_files = [f for f in dirs["source"].iterdir() if f.is_file()]
        if source_files:
            source_path = source_files[0]

    if not source_path or not source_path.exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"No source video media found for project '{project_id}'."
        )

    try:
        region = facecam_service.analyze_source_facecam(
            video_path=source_path,
            sample_interval_sec=payload.sample_interval_sec,
            max_samples=payload.max_samples
        )

        # Save checkpoint
        storage_service.save_stage_checkpoint(project_id, "facecam", region.model_dump())

        # Update project metadata
        if project.metadata:
            project.metadata.facecam_region = region
        else:
            project.metadata = MediaMetadata(facecam_region=region)
        storage_service.save_project_metadata(project)

        # Generate debug frame preview image
        debug_frame_path = dirs["metadata"] / "facecam_debug.jpg"
        facecam_service.generate_debug_frame(source_path, region, debug_frame_path)

        return region

    except Exception as e:
        logger.error(f"Error during facecam detection for project '{project_id}': {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Facecam analysis failed: {str(e)}"
        )


@router.get("", response_model=FacecamRegion)
def get_facecam(project_id: str):
    """Retrieves cached streamer facecam detection region for a project."""
    project = storage_service.load_project_metadata(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found."
        )

    cached = storage_service.load_stage_checkpoint(project_id, "facecam")
    if cached:
        return FacecamRegion(**cached)

    if project.metadata and project.metadata.facecam_region:
        return project.metadata.facecam_region

    return FacecamRegion(is_detected=False)


@router.get("/debug_frame")
def get_facecam_debug_frame(project_id: str):
    """Returns a visual JPEG frame from the video with the facecam bounding box overlay drawn."""
    project = storage_service.load_project_metadata(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found."
        )

    dirs = storage_service.init_project_workspace(project_id)
    debug_frame_path = dirs["metadata"] / "facecam_debug.jpg"

    if not debug_frame_path.exists():
        # Retrieve or construct region
        cached = storage_service.load_stage_checkpoint(project_id, "facecam")
        region = FacecamRegion(**cached) if cached else (
            project.metadata.facecam_region if (project.metadata and project.metadata.facecam_region)
            else FacecamRegion(is_detected=False)
        )

        # Resolve source path
        source_path: Optional[Path] = None
        if project.source_path:
            p = Path(project.source_path)
            if p.exists():
                source_path = p
        if not source_path:
            source_files = [f for f in dirs["source"].iterdir() if f.is_file()]
            source_path = source_files[0] if source_files else dirs["source"] / "fallback.mp4"

        facecam_service.generate_debug_frame(source_path, region, debug_frame_path)

    return FileResponse(
        path=str(debug_frame_path),
        media_type="image/jpeg",
        filename=f"{project_id}_facecam_debug.jpg"
    )
