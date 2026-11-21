"""Unit tests for Phase 13: Causal Sequence Framing & Visual Reaction Analysis."""

import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

from backend.app.models.facecam import FacecamRegion
from backend.app.models.transcript import FullTranscript, TranscriptSegment, WordTiming
from backend.app.services.causal_sequence_service import CausalSequenceService
from backend.app.services.visual_reaction_service import VisualReactionService


class TestCausalSequence(unittest.TestCase):
    def setUp(self):
        self.causal_svc = CausalSequenceService()
        self.visual_svc = VisualReactionService()

        # Synthetic transcript with 8 segments
        self.transcript = FullTranscript(
            project_id="test_proj",
            language="en",
            duration=120.0,
            text="Full transcript text",
            segments=[
                TranscriptSegment(id=0, seek=0, start=10.0, end=15.0, text="We are preparing for the heist.", words=[]),
                TranscriptSegment(id=1, seek=0, start=16.0, end=21.0, text="The police are right behind us.", words=[]),
                TranscriptSegment(id=2, seek=0, start=22.0, end=27.0, text="Watch out for that helicopter!", words=[]),
                TranscriptSegment(id=3, seek=0, start=28.0, end=32.0, text="OH NO HE JUST CRASHED!", words=[]), # Peak around 30s
                TranscriptSegment(id=4, seek=0, start=33.0, end=38.0, text="WHAT IS HE DOING BRO?!", words=[]),
                TranscriptSegment(id=5, seek=0, start=39.0, end=45.0, text="I can't believe we survived that.", words=[]),
                TranscriptSegment(id=6, seek=0, start=46.0, end=52.0, text="Get in the getaway car now.", words=[]),
                TranscriptSegment(id=7, seek=0, start=53.0, end=60.0, text="We made it to the safehouse.", words=[]),
            ]
        )

    def test_identify_reaction_hotspots(self):
        """Nearby audio surges within 12s cluster into distinct peak events."""
        # Surges at 28s, 29s, 31s (cluster 1) and at 75s, 76s (cluster 2)
        surges = [28.0, 29.0, 31.0, 75.0, 76.0]
        hotspots = self.causal_svc.identify_reaction_hotspots(surges, min_gap_sec=12.0)
        self.assertEqual(len(hotspots), 2)
        self.assertAlmostEqual(hotspots[0], 29.0, places=1)
        self.assertAlmostEqual(hotspots[1], 75.5, places=1)

    def test_causal_window_expansion_around_reaction_peak(self):
        """Reaction peak at 30s expands to Setup (~20s), Reaction (30s), and Payoff (~45s)."""
        peak_t = 30.0
        start_t, end_t = self.causal_svc.expand_causal_window(
            peak_time=peak_t,
            transcript=self.transcript,
            min_duration=20.0,
            pref_duration=30.0,
            max_duration=60.0
        )
        duration = end_t - start_t
        self.assertGreaterEqual(duration, 20.0)
        self.assertLessEqual(duration, 60.0)

        # Setup must start before the peak
        self.assertLess(start_t, peak_t - 5.0)
        # Payoff must extend beyond the peak
        self.assertGreater(end_t, peak_t + 10.0)

        # Must snap to sentence endpoints (16.0 or 22.0 at start, 45.0 or 52.0 at end)
        starts = [seg.start for seg in self.transcript.segments]
        ends = [seg.end for seg in self.transcript.segments]
        self.assertTrue(start_t in starts or any(abs(start_t - s) < 0.1 for s in starts))
        self.assertTrue(end_t in ends or any(abs(end_t - e) < 0.1 for e in ends))

    def test_minimum_duration_enforcement_20s(self):
        """Even with narrow sentence boundaries, clip duration strictly satisfies >= 20.0s."""
        # Short transcript segment: 10s to 15s (5s duration)
        short_transcript = FullTranscript(
            project_id="short_proj",
            language="en",
            duration=30.0,
            text="Short",
            segments=[TranscriptSegment(id=0, seek=0, start=10.0, end=15.0, text="Boom", words=[])]
        )
        start_t, end_t = self.causal_svc.expand_causal_window(
            peak_time=12.0,
            transcript=short_transcript,
            min_duration=20.0,
            pref_duration=25.0,
            max_duration=60.0
        )
        duration = round(end_t - start_t, 2)
        self.assertGreaterEqual(duration, 20.0, "Hard minimum duration of 20s must be enforced")

    def test_maximum_duration_enforcement_60s(self):
        """Clip duration strictly obeys <= 60.0s hard platform maximum."""
        start_t, end_t = self.causal_svc.expand_causal_window(
            peak_time=50.0,
            transcript=self.transcript,
            min_duration=20.0,
            pref_duration=75.0, # Excessive preferred duration
            max_duration=60.0
        )
        duration = round(end_t - start_t, 2)
        self.assertLessEqual(duration, 60.0, "Hard maximum duration of 60s must not be exceeded")

    @patch("backend.app.services.visual_reaction_service.cv2.VideoCapture")
    def test_visual_reaction_scoring_on_mock_frames(self, mock_cap_cls):
        """Visual motion in facecam and gameplay accurately maps to 0-100 scores."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tf:
            temp_video_path = Path(tf.name)

        try:
            mock_cap = MagicMock()
            mock_cap_cls.return_value = mock_cap
            mock_cap.isOpened.return_value = True
            mock_cap.get.side_effect = lambda prop: {3: 1920, 4: 1080, 5: 30.0, 7: 600}.get(prop, 0.0)

            # Generate 20 frames with jumping facecam motion in the middle
            frames = []
            for i in range(20):
                f = np.zeros((1080, 1920, 3), dtype=np.uint8)
                # Streamer box at (100, 100, 300, 200)
                if 8 <= i <= 12:
                    # Big motion spike
                    f[100:300, 100:400] = 255
                else:
                    f[100:300, 100:400] = 50
                frames.append(f)

            frame_iter = iter(frames)
            def read_side_effect():
                try:
                    return True, next(frame_iter)
                except StopIteration:
                    return False, None
            mock_cap.read.side_effect = read_side_effect

            facecam = FacecamRegion(
                is_detected=True,
                x=100,
                y=100,
                width=300,
                height=200,
                confidence=0.95
            )

            scores = self.visual_svc.analyze_candidate_visuals(
                source_video_path=temp_video_path,
                start_sec=0.0,
                end_sec=10.0,
                facecam=facecam,
                sample_fps=2.0
            )
            self.assertIn("streamer_visual_reaction_score", scores)
            self.assertIn("gameplay_activity_score", scores)
            # Facecam motion had a big spike -> score should be elevated
            self.assertGreaterEqual(scores["streamer_visual_reaction_score"], 65.0)
        finally:
            if temp_video_path.exists():
                temp_video_path.unlink()


if __name__ == "__main__":
    unittest.main()
