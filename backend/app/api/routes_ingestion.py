"""API routes for media ingestion (local files and authorized YouTube URLs)."""

from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.models.project import Project
from backend.app.services.ingestion_service import ingestion_service

router = APIRouter(prefix="/api/projects/{project_id}/ingest", tags=["Ingestion"])


class LocalFileInput(BaseModel):
    file_path: str


class YouTubeInput(BaseModel):
    url: str


@router.post("/file", response_model=Project)
async def ingest_local_file(project_id: str, payload: LocalFileInput):
    """Imports and validates a local video file from disk."""
    try:
        return ingestion_service.ingest_local_file(project_id, payload.file_path)
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Ingestion failed: {e}")


@router.post("/youtube", response_model=Project)
async def ingest_youtube_url(project_id: str, payload: YouTubeInput):
    """Downloads an authorized YouTube video via yt-dlp."""
    try:
        return ingestion_service.ingest_youtube_url(project_id, payload.url)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"YouTube ingestion failed: {e}")
