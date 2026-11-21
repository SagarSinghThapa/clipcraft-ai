"""Unit tests for transcript segmentation and candidate models."""

import unittest
from backend.app.models.candidate import CandidateClip, ScoreBreakdown
from backend.app.models.transcript import FullTranscript, TranscriptSegment, WordTiming
from backend.app.services.segmentation_service import SegmentationService


class TestAnalysis(unittest.TestCase):
    def setUp(self):
        self.seg_svc = SegmentationService()

    def test_candidate_models_validation(self):
        score = ScoreBreakdown(
            hook_strength=22.0,
            standalone_clarity=23.0,
            information_density=21.0,
            pacing_and_flow=22.0,
            total_score=88,
            explanation="High-impact hook with complete context."
        )
        clip = CandidateClip(
            id="clip_test01",
            project_id="proj_test",
            title="AI Revolution",
            start_time=10.0,
            end_time=35.0,
            duration=25.0,
            transcript_excerpt="The AI revolution is happening right now.",
            hook_assessment="Immediate hook",
            standalone_context="Clear concept",
            reasoning="High shareability",
            score=score
        )
        self.assertEqual(clip.duration, 25.0)
        self.assertEqual(clip.score.total_score, 88)

    def test_segmentation_windows_respect_sentence_boundaries(self):
        segments = [
            TranscriptSegment(id=0, start=0.0, end=15.0, text="First complete thought."),
            TranscriptSegment(id=1, start=15.2, end=35.0, text="Second detailed explanation with examples."),
            TranscriptSegment(id=2, start=35.5, end=60.0, text="Third conclusion and takeaways."),
            TranscriptSegment(id=3, start=60.5, end=85.0, text="Fourth closing statement."),
        ]
        transcript = FullTranscript(
            project_id="proj_seg_test",
            duration=85.0,
            segments=segments
        )

        windows = self.seg_svc.create_analysis_windows(
            transcript=transcript,
            min_window_duration=25.0,
            max_window_duration=60.0,
            overlap_seconds=10.0
        )

        self.assertTrue(len(windows) > 0)
        for win in windows:
            # Must start and end exactly on segment boundaries
            start = win["start_time"]
            end = win["end_time"]
            self.assertTrue(any(abs(s.start - start) < 0.01 for s in segments))
            self.assertTrue(any(abs(s.end - end) < 0.01 for s in segments))


if __name__ == "__main__":
    unittest.main()
