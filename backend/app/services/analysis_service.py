"""Highlight analysis service orchestrating segmentation, LLM extraction, audio energy, visual motion, and multimodal scoring."""

import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Any

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.models.candidate import CandidateClip, CandidateList
from backend.app.models.facecam import FacecamRegion
from backend.app.models.audio import ReactionCategory
from backend.app.models.project import ProjectStatus
from backend.app.services.storage_service import storage_service
from backend.app.services.transcription_service import transcription_service
from backend.app.services.segmentation_service import segmentation_service
from backend.app.services.llm_provider import ollama_provider
from backend.app.services.scoring_service import scoring_service
from backend.app.services.audio_energy_service import audio_energy_service
from backend.app.services.visual_reaction_service import visual_reaction_service
from backend.app.services.causal_sequence_service import causal_sequence_service


class AnalysisService:
    """Discovers and scores top candidate highlight clips from project transcript."""

    def get_candidates_path(self, project_id: str) -> Path:
        """Returns canonical candidates.json file path."""
        dirs = storage_service.init_project_workspace(project_id)
        return dirs["analysis"] / "candidates.json"

    def load_cached_candidates(self, project_id: str) -> Optional[CandidateList]:
        """Loads candidates from disk if previously computed."""
        c_path = self.get_candidates_path(project_id)
        if c_path.exists() and c_path.stat().st_size > 0:
            try:
                with open(c_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return CandidateList(**data)
            except Exception as e:
                logger.warning(f"Error reading cached candidates for {project_id}: {e}")
        return None

    def suppress_duplicate_candidates(
        self,
        candidates: List[CandidateClip],
        overlap_threshold: float = 0.40,
        min_distance_sec: float = 15.0
    ) -> List[CandidateClip]:
        """
        Suppresses redundant candidate highlight cuts via temporal Non-Maximum Suppression (NMS).
        - Candidates are sorted by total_score descending.
        - Suppresses a candidate if it overlaps with an accepted candidate by > overlap_threshold
          (temporal IoU = intersection / union > 0.40) or if their centers are closer than min_distance_sec.
        """
        if not candidates:
            return []

        sorted_c = sorted(candidates, key=lambda c: c.score.total_score, reverse=True)
        accepted: List[CandidateClip] = []

        for c in sorted_c:
            should_suppress = False
            c_center = (c.start_time + c.end_time) / 2.0
            c_duration = c.end_time - c.start_time

            for acc in accepted:
                acc_center = (acc.start_time + acc.end_time) / 2.0
                acc_duration = acc.end_time - acc.start_time

                # Check center distance
                if abs(c_center - acc_center) < min_distance_sec:
                    should_suppress = True
                    break

                # Check temporal IoU
                inter_start = max(c.start_time, acc.start_time)
                inter_end = min(c.end_time, acc.end_time)
                intersection = max(0.0, inter_end - inter_start)
                union = (c_duration + acc_duration) - intersection

                if union > 0.0 and (intersection / union) > overlap_threshold:
                    should_suppress = True
                    break

            if not should_suppress:
                accepted.append(c)

        return accepted

    async def analyze_project_highlights(
        self,
        project_id: str,
        llm_model: Optional[str] = None,
        max_candidates: Optional[int] = None,
        force_recompute: bool = False
    ) -> CandidateList:
        """
        Orchestrates staged multimodal highlight detection:
        1. Audio screening via audio_energy_service (O(N) cumsum RMS & speech corroboration)
        2. Reaction hotspots clustering via causal_sequence_service
        3. Transcript LLM extraction via ollama_provider
        4. Causal window expansion (Setup -> Event -> Reaction -> Payoff) with 20s-60s bounds
        5. Targeted visual analysis via visual_reaction_service on shortlisted windows
        6. Multimodal score fusion and anti-saturation calibration
        7. Temporal NMS deduplication
        """
        model_name = llm_model or settings.DEFAULT_LLM_MODEL
        target_count = max_candidates or settings.DEFAULT_CANDIDATE_COUNT

        if not force_recompute:
            cached = self.load_cached_candidates(project_id)
            if cached:
                logger.info(f"Returning cached candidates for project '{project_id}' ({len(cached.candidates)} clips).")
                return cached

        # Load or generate transcript
        transcript = transcription_service.transcribe_project(project_id)
        if not transcript.segments:
            raise ValueError(f"Project '{project_id}' transcript is empty. Cannot extract highlights.")

        # Flatten all word timings for speech corroboration and audio energy profiling
        all_words = []
        for seg in transcript.segments:
            if seg.words:
                all_words.extend(seg.words)

        # 1. Audio Energy Screening & Surge Hotspot Identification
        surge_timestamps: List[float] = []
        try:
            audio_profile_summary = audio_energy_service.analyze_project_audio_energy(
                project_id=project_id,
                whisper_words=all_words
            )
            if audio_profile_summary and "surge_windows" in audio_profile_summary:
                surge_timestamps = audio_profile_summary["surge_windows"]
        except Exception as e:
            logger.warning(f"Audio energy screening encountered non-fatal error for {project_id}: {e}")

        reaction_hotspots = causal_sequence_service.identify_reaction_hotspots(
            surge_timestamps=surge_timestamps,
            min_gap_sec=12.0
        )
        logger.info(f"Identified {len(reaction_hotspots)} reaction hotspots from {len(surge_timestamps)} audio surges.")

        # 2. Segment transcript into windows and extract LLM candidates
        windows = segmentation_service.create_analysis_windows(
            transcript=transcript,
            min_window_duration=float(settings.DEFAULT_MIN_CLIP_DURATION),
            max_window_duration=float(settings.DEFAULT_MAX_CLIP_DURATION) * 1.5,
            overlap_seconds=10.0
        )

        logger.info(f"Analyzing {len(windows)} transcript windows for highlights using {model_name}...")
        raw_candidates: List[Dict[str, Any]] = []
        for win in windows:
            extracted = await ollama_provider.analyze_transcript_window(
                window_text=win["text"],
                start_time=win["start_time"],
                end_time=win["end_time"],
                model_name=model_name
            )
            raw_candidates.extend(extracted)
            if len(raw_candidates) >= max(target_count * 2, 8):
                logger.info(f"Collected sufficient candidates ({len(raw_candidates)}) to rank top {target_count}.")
                break

        # 3. Add audio reaction hotspot candidates if not already covered by LLM candidates
        for hotspot_t in reaction_hotspots:
            is_covered = any(
                abs(((c["start_time"] + c["end_time"]) / 2.0) - hotspot_t) < 10.0
                for c in raw_candidates
            )
            if not is_covered:
                m = int(hotspot_t // 60)
                s = int(hotspot_t % 60)
                raw_candidates.append({
                    "title": f"Streamer Reaction @ {m:02d}:{s:02d}",
                    "start_time": max(0.0, hotspot_t - 8.0),
                    "end_time": hotspot_t + 15.0,
                    "peak_time": hotspot_t,
                    "hook_assessment": "Immediate reaction peak grab",
                    "standalone_context": "Vocal reaction with gameplay payoff",
                    "reasoning": f"High-energy reaction surge detected at {hotspot_t:.1f}s",
                    "category": ReactionCategory.SURPRISE
                })

        # Load project source path & facecam metadata
        project = storage_service.load_project_metadata(project_id)
        source_video_path = Path(project.source_path) if project and project.source_path else None

        facecam_data = storage_service.load_stage_checkpoint(project_id, "facecam")
        facecam = FacecamRegion(**facecam_data) if facecam_data else None

        # 4. Expand into Causal Sequences & Run Multimodal Evaluation
        unfiltered_candidates: List[CandidateClip] = []

        for c in raw_candidates:
            peak_t = c.get("peak_time") or ((c["start_time"] + c["end_time"]) / 2.0)

            # Expand into Setup -> Event -> Reaction -> Payoff (enforcing 20s-60s bounds)
            start_t, end_t = causal_sequence_service.expand_causal_window(
                peak_time=peak_t,
                transcript=transcript,
                min_duration=20.0,
                pref_duration=35.0,
                max_duration=60.0,
                video_duration=transcript.duration
            )
            duration = round(end_t - start_t, 2)
            if duration < 18.0:
                continue

            # Query Audio Profile for this window
            audio_profile = audio_energy_service.get_clip_audio_profile(project_id, start_t, end_t)

            # Query Visual Motion Profile (staged 2 fps on candidate window only)
            visual_profile = None
            if source_video_path and source_video_path.exists():
                visual_profile = visual_reaction_service.analyze_candidate_visuals(
                    source_video_path=source_video_path,
                    start_sec=start_t,
                    end_sec=end_t,
                    facecam=facecam,
                    sample_fps=2.0,
                    peak_sec=peak_t
                )

            # Find matching transcript text excerpt
            excerpt_segments = [
                seg.text for seg in transcript.segments
                if seg.start >= start_t - 0.5 and seg.end <= end_t + 0.5
            ]
            transcript_excerpt = " ".join(excerpt_segments) or c.get("reasoning", "")

            # Compute multimodal score
            c_data = dict(c)
            c_data["duration"] = duration
            c_data["start_time"] = start_t
            c_data["end_time"] = end_t
            c_data["peak_time"] = peak_t
            c_data["transcript_excerpt"] = transcript_excerpt

            score_breakdown = scoring_service.compute_multimodal_candidate_score(
                candidate_data=c_data,
                audio_profile=audio_profile,
                visual_profile=visual_profile
            )

            clip_id = f"clip_{uuid.uuid4().hex[:8]}"
            unfiltered_candidates.append(CandidateClip(
                id=clip_id,
                project_id=project_id,
                title=c["title"],
                start_time=start_t,
                end_time=end_t,
                duration=duration,
                transcript_excerpt=transcript_excerpt,
                hook_assessment=c["hook_assessment"],
                standalone_context=c["standalone_context"],
                reasoning=c["reasoning"],
                score=score_breakdown,
                selected_for_rendering=True
            ))

        # 5. Apply Temporal Non-Maximum Suppression (NMS)
        deduplicated = self.suppress_duplicate_candidates(
            candidates=unfiltered_candidates,
            overlap_threshold=0.40,
            min_distance_sec=15.0
        )
        final_candidates = deduplicated[:target_count]

        candidate_list = CandidateList(
            project_id=project_id,
            candidates=final_candidates,
            model_used=model_name
        )

        # Persist to disk
        c_path = self.get_candidates_path(project_id)
        with open(c_path, "w", encoding="utf-8") as f:
            f.write(candidate_list.model_dump_json(indent=2))

        # Update project status
        if project:
            project.status = ProjectStatus.READY_FOR_REVIEW
            storage_service.save_project_metadata(project)

        storage_service.save_stage_checkpoint(project_id, "analysis", {
            "candidate_count": len(final_candidates),
            "candidates_path": str(c_path),
            "top_score": final_candidates[0].score.total_score if final_candidates else 0,
            "categories": [c.score.category.value for c in final_candidates]
        })

        logger.info(f"Discovered {len(final_candidates)} multimodal candidates for project '{project_id}'.")
        return candidate_list


analysis_service = AnalysisService()
