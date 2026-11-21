"""Unit and integration tests for multimodal score fusion, anti-saturation, temporal NMS, and reaction caption hooks."""

import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
import numpy as np

from backend.app.models.candidate import CandidateClip, ScoreBreakdown
from backend.app.models.audio import (
    ReactionCategory,
    ClipAudioProfile,
    GlobalAudioStats
)
from backend.app.models.transcript import WordTiming
from backend.app.models.caption import WordEmphasis
from backend.app.services.scoring_service import scoring_service
from backend.app.services.analysis_service import analysis_service
from backend.app.services.caption_service import caption_service


class TestMultimodalScoring(unittest.TestCase):
    """Test suite covering Phase 13 multimodal scoring, NMS, and caption reaction integration."""

    def test_calibrated_scoring_eliminates_saturation(self):
        """High-performing candidates show meaningful score differentiation, avoiding 100/100/100 ties."""
        # Candidate 1: Exceptional multimodal reaction peak (95 raw)
        c1_audio = ClipAudioProfile(
            start_time=10.0,
            end_time=40.0,
            peak_rms=0.25,
            mean_rms=0.08,
            peak_z_score=3.5,
            local_contrast_peak=3.2,
            surge_count=5,
            reaction_density=2.0,
            has_speech_corroboration=True,
            audio_reaction_score=95.0,
            category=ReactionCategory.FUNNY_REACTION
        )
        c1_visual = {"streamer_visual_reaction_score": 90.0, "gameplay_activity_score": 85.0}
        c1_data = {
            "transcript_context_score": 95.0,
            "hook_score": 95.0,
            "payoff_score": 90.0,
            "start_time": 10.0,
            "end_time": 40.0,
            "peak_time": 22.0,
            "duration": 30.0,
            "category": ReactionCategory.FUNNY_REACTION
        }
        score1 = scoring_service.compute_multimodal_candidate_score(c1_data, c1_audio, c1_visual)

        # Candidate 2: Strong candidate (85 raw)
        c2_audio = ClipAudioProfile(
            start_time=50.0,
            end_time=80.0,
            peak_rms=0.18,
            mean_rms=0.06,
            peak_z_score=2.2,
            local_contrast_peak=2.5,
            surge_count=3,
            reaction_density=1.0,
            has_speech_corroboration=True,
            audio_reaction_score=80.0,
            category=ReactionCategory.CHAOTIC_MOMENT
        )
        c2_visual = {"streamer_visual_reaction_score": 75.0, "gameplay_activity_score": 70.0}
        c2_data = {
            "transcript_context_score": 80.0,
            "hook_score": 80.0,
            "payoff_score": 75.0,
            "start_time": 50.0,
            "end_time": 80.0,
            "peak_time": 62.0,
            "duration": 30.0,
            "category": ReactionCategory.CHAOTIC_MOMENT
        }
        score2 = scoring_service.compute_multimodal_candidate_score(c2_data, c2_audio, c2_visual)

        # Candidate 3: Moderate candidate (72 raw)
        c3_audio = ClipAudioProfile(
            start_time=100.0,
            end_time=130.0,
            peak_rms=0.12,
            mean_rms=0.05,
            peak_z_score=1.5,
            local_contrast_peak=1.8,
            surge_count=1,
            reaction_density=0.5,
            has_speech_corroboration=True,
            audio_reaction_score=65.0,
            category=ReactionCategory.GENERAL_HIGHLIGHT
        )
        c3_visual = {"streamer_visual_reaction_score": 60.0, "gameplay_activity_score": 60.0}
        c3_data = {
            "transcript_context_score": 70.0,
            "hook_score": 70.0,
            "payoff_score": 65.0,
            "start_time": 100.0,
            "end_time": 130.0,
            "peak_time": 112.0,
            "duration": 30.0,
            "category": ReactionCategory.GENERAL_HIGHLIGHT
        }
        score3 = scoring_service.compute_multimodal_candidate_score(c3_data, c3_audio, c3_visual)

        # Distinct scores, strictly descending, non-saturating
        self.assertGreater(score1.total_score, score2.total_score)
        self.assertGreater(score2.total_score, score3.total_score)
        self.assertNotEqual(score1.total_score, 100, "100 should not saturate exceptional candidates")
        self.assertGreaterEqual(score1.total_score, 88)
        self.assertLessEqual(score1.total_score, 94)

    def test_penalty_deductions_for_dead_air_and_missing_setup(self):
        """Penalties for missing setup and dead air deduct cleanly from total score."""
        audio_profile = ClipAudioProfile(
            start_time=10.0,
            end_time=35.0,
            peak_rms=0.15,
            mean_rms=0.05,
            peak_z_score=2.8,
            local_contrast_peak=2.5,
            surge_count=2,
            reaction_density=1.0,
            has_speech_corroboration=True,
            audio_reaction_score=85.0,
            category=ReactionCategory.GENERAL_HIGHLIGHT
        )
        visual_profile = {"streamer_visual_reaction_score": 75.0, "gameplay_activity_score": 75.0}

        # Perfect setup (peak at 20.0s, start at 10.0s -> 10s of setup)
        clean_data = {
            "transcript_context_score": 80.0,
            "hook_score": 80.0,
            "payoff_score": 80.0,
            "start_time": 10.0,
            "end_time": 35.0,
            "peak_time": 20.0,
            "duration": 25.0
        }
        clean_score = scoring_service.compute_multimodal_candidate_score(clean_data, audio_profile, visual_profile)
        self.assertEqual(clean_score.penalties, 0.0)

        # Missing setup (peak at 11.0s, start at 10.0s -> only 1.0s of setup)
        no_setup_data = dict(clean_data)
        no_setup_data["peak_time"] = 11.0
        penalized_setup = scoring_service.compute_multimodal_candidate_score(no_setup_data, audio_profile, visual_profile)
        self.assertGreaterEqual(penalized_setup.penalties, 15.0)
        self.assertLess(penalized_setup.total_score, clean_score.total_score)

        # Dead air penalty
        dead_air_data = dict(clean_data)
        dead_air_data["has_dead_air"] = True
        penalized_dead_air = scoring_service.compute_multimodal_candidate_score(dead_air_data, audio_profile, visual_profile)
        self.assertGreaterEqual(penalized_dead_air.penalties, 10.0)
        self.assertLess(penalized_dead_air.total_score, clean_score.total_score)

    def test_explainable_summary_details_multimodal_drivers(self):
        """Explanation explicitly details vocal reaction surge, facecam motion, and setup."""
        audio_profile = ClipAudioProfile(
            start_time=10.0,
            end_time=40.0,
            peak_rms=0.20,
            mean_rms=0.06,
            peak_z_score=3.2,
            local_contrast_peak=2.8,
            surge_count=3,
            reaction_density=1.5,
            has_speech_corroboration=True,
            audio_reaction_score=92.0,
            category=ReactionCategory.SURPRISE
        )
        visual_profile = {"streamer_visual_reaction_score": 88.0, "gameplay_activity_score": 80.0}
        candidate_data = {
            "transcript_context_score": 85.0,
            "hook_score": 85.0,
            "payoff_score": 80.0,
            "start_time": 10.0,
            "end_time": 40.0,
            "peak_time": 22.0,
            "duration": 30.0,
            "category": ReactionCategory.SURPRISE
        }
        score = scoring_service.compute_multimodal_candidate_score(candidate_data, audio_profile, visual_profile)
        self.assertIn("audio reaction surge", score.explanation)
        self.assertIn("streamer facecam motion", score.explanation)
        self.assertIn("gameplay action", score.explanation)
        self.assertIn("Z=3.2", score.explanation)

    def test_backward_compatibility_with_legacy_candidates(self):
        """Legacy scoring inputs smoothly compute valid multimodal breakdowns."""
        legacy_data = {
            "hook_score": 22.0,
            "clarity_score": 20.0,
            "density_score": 21.0,
            "pacing_score": 20.0,
            "duration": 30.0
        }
        score = scoring_service.compute_candidate_score(legacy_data)
        self.assertIsInstance(score, ScoreBreakdown)
        self.assertGreaterEqual(score.total_score, 70)
        self.assertLessEqual(score.total_score, 100)
        self.assertIsInstance(score.category, ReactionCategory)

    def test_temporal_nms_suppresses_overlapping_candidates(self):
        """Temporal NMS suppresses candidates with > 40% overlap or center distance < 15s."""
        score_high = ScoreBreakdown(total_score=90)
        score_mid = ScoreBreakdown(total_score=82)
        score_low = ScoreBreakdown(total_score=75)

        # Candidate A: 10s to 40s (High score)
        cA = CandidateClip(
            id="c_A", project_id="p1", title="A",
            start_time=10.0, end_time=40.0, duration=30.0,
            transcript_excerpt="", hook_assessment="", standalone_context="", reasoning="",
            score=score_high
        )
        # Candidate B: 15s to 45s (Mid score, 25s overlap with A / 35s union = 71% overlap -> Suppressed)
        cB = CandidateClip(
            id="c_B", project_id="p1", title="B",
            start_time=15.0, end_time=45.0, duration=30.0,
            transcript_excerpt="", hook_assessment="", standalone_context="", reasoning="",
            score=score_mid
        )
        # Candidate C: 70s to 100s (Low score, independent window -> Kept)
        cC = CandidateClip(
            id="c_C", project_id="p1", title="C",
            start_time=70.0, end_time=100.0, duration=30.0,
            transcript_excerpt="", hook_assessment="", standalone_context="", reasoning="",
            score=score_low
        )

        deduped = analysis_service.suppress_duplicate_candidates([cA, cB, cC], overlap_threshold=0.40, min_distance_sec=15.0)
        self.assertEqual(len(deduped), 2)
        self.assertEqual(deduped[0].id, "c_A")
        self.assertEqual(deduped[1].id, "c_C")

    def test_caption_word_reaction_tagging_links_to_phase_12(self):
        """Confirmed reaction surge windows tag words with WordEmphasis.REACTION (112% pop)."""
        words = [
            WordTiming(word="Check", start=10.0, end=10.5, probability=0.99),
            WordTiming(word="this", start=10.6, end=11.0, probability=0.99),
            WordTiming(word="INSANE", start=12.0, end=12.8, probability=0.99),
            WordTiming(word="shot", start=12.9, end=13.4, probability=0.99),
            WordTiming(word="bro", start=13.5, end=14.0, probability=0.99),
        ]
        # Confirmed surge at 11.9s - 13.0s
        surge_windows = [(11.9, 13.0)]

        chunks = caption_service.chunk_words_for_clip(
            words=words,
            clip_start=10.0,
            clip_end=15.0,
            confirmed_surge_windows=surge_windows
        )

        # Find the word "INSANE"
        found_word = None
        for chunk in chunks:
            for w in chunk.words:
                if "INSANE" in w.word:
                    found_word = w
                    break
        self.assertIsNotNone(found_word)
        self.assertEqual(found_word.emphasis, WordEmphasis.REACTION)

    @patch("backend.app.api.routes_analysis.audio_energy_service.analyze_project_audio_energy")
    @patch("backend.app.api.routes_analysis.transcription_service.transcribe_project")
    def test_get_project_audio_energy_endpoint(self, mock_transcribe, mock_analyze):
        """GET /api/projects/{id}/audio-energy downsamples waveform to 1pt/sec and returns global stats."""
        from backend.app.api.routes_analysis import get_project_audio_energy

        mock_transcribe.return_value = MagicMock(segments=[])

        mock_stats = GlobalAudioStats(
            duration_sec=2.0,
            mean_rms=0.05,
            std_rms=0.02,
            max_rms=0.25,
            median_rms=0.04,
            window_count=8,
            step_sec=0.25
        )
        mock_analyze.return_value = {
            "stats": mock_stats,
            "rms_series": np.array([0.05] * 8, dtype=np.float32),
            "timestamps": np.array([i * 0.25 for i in range(8)], dtype=np.float32),
            "local_contrast": np.array([1.0] * 8, dtype=np.float32),
            "surge_windows": [0.5]
        }

        res = get_project_audio_energy("proj_test")
        self.assertIn("project_id", res)
        self.assertIn("global_stats", res)
        self.assertIn("energy_curve_downsampled", res)
        # 8 windows @ 0.25s step -> 2.0s -> downsampled to 2 points
        self.assertEqual(len(res["energy_curve_downsampled"]), 2)


if __name__ == "__main__":
    unittest.main()
