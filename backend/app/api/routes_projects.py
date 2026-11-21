"""API routes for project management and hardware capabilities."""

import uuid
from typing import List
from fastapi import APIRouter, HTTPException, status

from backend.app.core.hardware import detect_hardware
from backend.app.models.project import Project, ProjectCreate, ProjectStatus
from backend.app.services.storage_service import storage_service

router = APIRouter(prefix="/api", tags=["Projects"])


@router.get("/hardware")
async def get_hardware_capabilities():
    """Returns detected hardware acceleration capabilities (CPU / CUDA)."""
    return detect_hardware()


@router.post("/projects", response_model=Project, status_code=status.HTTP_201_CREATED)
async def create_project(payload: ProjectCreate):
    """Initializes a new project workspace and saves metadata."""
    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    title = payload.title or f"Clip Project {datetime_tag()}"

    project = Project(
        id=project_id,
        title=title,
        source_type=payload.source_type,
        source_url=payload.source_url,
        status=ProjectStatus.CREATED,
        settings={
            "min_clip_duration": payload.min_clip_duration,
            "max_clip_duration": payload.max_clip_duration,
            "candidate_count": payload.candidate_count,
            "whisper_model": payload.whisper_model,
            "llm_model": payload.llm_model,
        }
    )

    storage_service.init_project_workspace(project.id)
    storage_service.save_project_metadata(project)
    return project


@router.get("/projects", response_model=List[Project])
async def list_projects():
    """Lists all stored projects sorted by newest first."""
    return storage_service.list_projects()


@router.get("/projects/{project_id}", response_model=Project)
async def get_project(project_id: str):
    """Retrieves a single project's current metadata."""
    project = storage_service.load_project_metadata(project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found."
        )
    return project


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(project_id: str):
    """Deletes a project and its entire directory workspace."""
    success = storage_service.delete_project(project_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project '{project_id}' not found."
        )
    return None


def datetime_tag() -> str:
    from datetime import datetime
    return datetime.utcnow().strftime("%Y%m%d_%H%M")
