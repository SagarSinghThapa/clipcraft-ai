"""API routes for highlight detection, candidate scoring, and candidate adjustments."""

import numpy as np
from typing import Optional
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from backend.app.models.candidate import CandidateList, CandidateClip
from backend.app.models.layout import LayoutStrategy, GameplayCompositionMode, CanvasResolution
from backend.app.models.caption import CaptionPreset, CaptionPlacement
from backend.app.services.analysis_service import analysis_service
from backend.app.services.storage_service import storage_service
from backend.app.services.transcription_service import transcription_service
from backend.app.services.audio_energy_service import audio_energy_service

router = APIRouter(prefix="/api/projects/{project_id}", tags=["Analysis"])


class AnalyzeRequest(BaseModel):
    llm_model: Optional[str] = None
    max_candidates: Optional[int] = None
    force_recompute: bool = False


class UpdateCandidateRequest(BaseModel):
    title: Optional[str] = None
    start_time: Optional[float] = None
    end_time: Optional[float] = None
    selected_for_rendering: Optional[bool] = None
    layout_strategy: Optional[LayoutStrategy] = None
    gameplay_composition: Optional[GameplayCompositionMode] = None
    split_ratio: Optional[float] = Field(default=None, ge=0.20, le=0.60)
    exclude_chat_overlay: Optional[bool] = None
    caption_preset: Optional[CaptionPreset] = None
    caption_placement: Optional[CaptionPlacement] = None
    resolution: Optional[CanvasResolution] = None


@router.post("/analyze", response_model=CandidateList)
async def analyze_project_highlights(project_id: str, payload: AnalyzeRequest):
    """Triggers transcript highlight analysis and explainable candidate scoring."""
    try:
        return await analysis_service.analyze_project_highlights(
            project_id=project_id,
            llm_model=payload.llm_model,
            max_candidates=payload.max_candidates,
            force_recompute=payload.force_recompute
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Highlight analysis failed: {e}")


@router.get("/candidates", response_model=CandidateList)
async def get_project_candidates(project_id: str):
    """Retrieves discovered candidate clips for a project."""
    cached = analysis_service.load_cached_candidates(project_id)
    if not cached:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No candidate highlights found for project '{project_id}'. Run /analyze first."
        )
    return cached


@router.patch("/candidates/{clip_id}", response_model=CandidateClip)
def update_candidate_clip(project_id: str, clip_id: str, payload: UpdateCandidateRequest):
    """Allows user to fine-tune clip title, timestamps, or toggle rendering selection."""
    candidates_data = analysis_service.load_cached_candidates(project_id)
    if not candidates_data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No candidates found.")

    target = next((c for c in candidates_data.candidates if c.id == clip_id), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Candidate clip '{clip_id}' not found.")

    if payload.title is not None:
        target.title = payload.title.strip()
    if payload.start_time is not None:
        target.start_time = max(0.0, payload.start_time)
    if payload.end_time is not None:
        target.end_time = max(target.start_time + 1.0, payload.end_time)
    target.duration = round(target.end_time - target.start_time, 2)
    if payload.selected_for_rendering is not None:
        target.selected_for_rendering = payload.selected_for_rendering
    if payload.layout_strategy is not None:
        target.layout_strategy = payload.layout_strategy
    if payload.gameplay_composition is not None:
        target.gameplay_composition = payload.gameplay_composition
    if payload.split_ratio is not None:
        target.split_ratio = payload.split_ratio
    if payload.exclude_chat_overlay is not None:
        target.exclude_chat_overlay = payload.exclude_chat_overlay
    if payload.caption_preset is not None:
        target.caption_preset = payload.caption_preset
    if payload.caption_placement is not None:
        target.caption_placement = payload.caption_placement
    if payload.resolution is not None:
        target.resolution = payload.resolution

    # Save changes
    c_path = analysis_service.get_candidates_path(project_id)
    with open(c_path, "w", encoding="utf-8") as f:
        f.write(candidates_data.model_dump_json(indent=2))

    return target


@router.get("/audio-energy")
def get_project_audio_energy(project_id: str):
    """Retrieves computed audio energy profile, statistics, and downsampled waveform for a project."""
    transcript = transcription_service.transcribe_project(project_id)
    all_words = []
    if transcript and transcript.segments:
        for seg in transcript.segments:
            if seg.words:
                all_words.extend(seg.words)

    profile = audio_energy_service.analyze_project_audio_energy(project_id, whisper_words=all_words)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Audio energy profile could not be computed for project '{project_id}'."
        )

    stats = profile["stats"]
    rms_series = profile["rms_series"]
    timestamps = profile["timestamps"]
    surge_windows = profile.get("surge_windows", [])

    std_guard = max(0.001, stats.std_rms if hasattr(stats, "std_rms") else stats["std_rms"])
    mean_rms_val = stats.mean_rms if hasattr(stats, "mean_rms") else stats["mean_rms"]
    step_sec = stats.step_sec if hasattr(stats, "step_sec") else stats.get("step_sec", 0.25)
    samples_per_sec = max(1, int(round(1.0 / step_sec)))

    downsampled = []
    n_windows = len(rms_series)
    for i in range(0, n_windows, samples_per_sec):
        chunk_rms = rms_series[i:i + samples_per_sec]
        chunk_ts = timestamps[i:i + samples_per_sec]
        if len(chunk_rms) > 0:
            mean_chunk_rms = float(np.mean(chunk_rms))
            z_val = float((mean_chunk_rms - mean_rms_val) / std_guard)
            downsampled.append({
                "time_sec": round(float(chunk_ts[0]), 1),
                "rms": round(mean_chunk_rms, 4),
                "z_score": round(z_val, 2)
            })

    return {
        "project_id": project_id,
        "global_stats": stats,
        "surge_count": len(surge_windows),
        "surge_windows": surge_windows,
        "energy_curve_downsampled": downsampled
    }

