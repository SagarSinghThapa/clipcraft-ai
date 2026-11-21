"""API routes for audio extraction and local speech-to-text transcription."""

from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from backend.app.models.transcript import FullTranscript
from backend.app.services.transcription_service import transcription_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["Transcription"])


class TranscribeRequest(BaseModel):
    model_size: Optional[str] = "base"
    force_recompute: bool = False


@router.post("/transcribe", response_model=FullTranscript)
async def transcribe_project_audio(project_id: str, payload: TranscribeRequest):
    """Executes audio extraction and local Whisper transcription."""
    try:
        return transcription_service.transcribe_project(
            project_id=project_id,
            model_size=payload.model_size,
            force_recompute=payload.force_recompute
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Transcription failed: {e}")


@router.get("/transcript", response_model=FullTranscript)
async def get_project_transcript(project_id: str):
    """Fetches the cached transcript for a project."""
    cached = transcription_service.load_cached_transcript(project_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No transcript found for project '{project_id}'. Please run transcription first."
        )
    return cached
