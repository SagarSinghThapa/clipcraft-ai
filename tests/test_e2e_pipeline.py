"""End-to-end integration test verifying the complete video clipping pipeline."""

import shutil
import tempfile
import unittest
from pathlib import Path

from backend.app.models.project import Project, SourceType, ProjectStatus
from backend.app.models.candidate import CandidateClip
from backend.app.models.transcript import WordTiming, TranscriptSegment, FullTranscript
from backend.app.services.storage_service import ProjectStorageService
from backend.app.services.segmentation_service import SegmentationService
from backend.app.services.llm_provider import OllamaProvider
from backend.app.services.scoring_service import ScoringService
from backend.app.services.reframing_service import ReframingService
from backend.app.services.caption_service import CaptionService


class TestEndToEndPipeline(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_e2e_"))
        self.storage = ProjectStorageService(base_dir=self.temp_dir)
        self.segmentation = SegmentationService()
        self.llm = OllamaProvider()
        self.scoring = ScoringService()
        self.reframing = ReframingService()
        self.captioning = CaptionService()

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_full_pipeline_flow_with_synthetic_media(self):
        """Simulates full pipeline execution: Project -> Transcript -> Highlight -> Reframe -> Captions."""
        project_id = "proj_e2e_test"

        # 1. Project Initialization
        dirs = self.storage.init_project_workspace(project_id)
        self.assertTrue(dirs["root"].exists())

        project = Project(
            id=project_id,
            title="Synthetic Test Project",
            source_type=SourceType.LOCAL_FILE,
            source_path=str(dirs["source"] / "test_video.mp4"),
            status=ProjectStatus.CREATED
        )
        self.storage.save_project_metadata(project)

        # 2. Synthetic Transcript Generation (Simulating Whisper output)
        words = [
            WordTiming(word="Building", start=1.0, end=1.5, probability=0.99),
            WordTiming(word="local", start=1.6, end=2.0, probability=0.98),
            WordTiming(word="AI", start=2.1, end=2.5, probability=0.99),
            WordTiming(word="tools", start=2.6, end=3.0, probability=0.98),
            WordTiming(word="is", start=3.1, end=3.4, probability=0.97),
            WordTiming(word="the", start=3.5, end=3.7, probability=0.99),
            WordTiming(word="future", start=3.8, end=4.5, probability=0.99),
        ]
        segments = [
            TranscriptSegment(
                id=0,
                start=1.0,
                end=4.5,
                text="Building local AI tools is the future.",
                words=words
            )
        ]
        transcript = FullTranscript(
            project_id=project_id,
            language="en",
            duration=5.0,
            full_text="Building local AI tools is the future.",
            segments=segments
        )

        t_path = dirs["transcript"] / "transcript.json"
        with open(t_path, "w", encoding="utf-8") as f:
            f.write(transcript.model_dump_json(indent=2))
        self.assertTrue(t_path.exists())

        # 3. Transcript Segmentation
        windows = self.segmentation.create_analysis_windows(transcript, min_window_duration=2.0, max_window_duration=10.0)
        self.assertTrue(len(windows) >= 1)

        # 4. Highlight Extraction & Scoring
        raw_candidates = self.llm._heuristic_highlight_discovery(
            window_text=windows[0]["text"],
            start_time=windows[0]["start_time"],
            end_time=windows[0]["end_time"]
        )
        self.assertTrue(len(raw_candidates) >= 1)

        candidate_data = raw_candidates[0]
        score_breakdown = self.scoring.compute_candidate_score(candidate_data)
        self.assertGreaterEqual(score_breakdown.total_score, 0)
        self.assertLessEqual(score_breakdown.total_score, 100)

        candidate = CandidateClip(
            id="clip_e2e_01",
            project_id=project_id,
            title=candidate_data["title"],
            start_time=candidate_data["start_time"],
            end_time=candidate_data["end_time"],
            duration=candidate_data["duration"],
            transcript_excerpt=transcript.full_text,
            hook_assessment=candidate_data["hook_assessment"],
            standalone_context=candidate_data["standalone_context"],
            reasoning=candidate_data["reasoning"],
            score=score_breakdown,
            selected_for_rendering=True
        )

        # 5. 9:16 Vertical Reframing Dimension Verification
        crop_w, crop_h = self.reframing.calculate_9_16_crop_dimensions(width=1920, height=1080)
        self.assertEqual(crop_h, 1080)
        self.assertEqual(crop_w, 608)

        # 6. Synchronized Subtitle Generation
        chunks = self.captioning.chunk_words_for_clip(
            words=words,
            clip_start=candidate.start_time,
            clip_end=candidate.end_time,
            words_per_chunk=3
        )
        self.assertTrue(len(chunks) >= 1)

        srt_text = self.captioning.generate_srt_content(chunks)
        self.assertIn("-->", srt_text)

        ass_text = self.captioning.generate_ass_content(chunks)
        self.assertIn("[Script Info]", ass_text)
        self.assertIn("PlayResX: 1080", ass_text)
        self.assertIn("Dialogue:", ass_text)

        # Write generated subtitle artifacts into clip folder
        clip_dir = dirs["clips"] / candidate.id
        clip_dir.mkdir(parents=True, exist_ok=True)

        srt_file = clip_dir / "captions.srt"
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt_text)

        ass_file = clip_dir / "captions.ass"
        with open(ass_file, "w", encoding="utf-8") as f:
            f.write(ass_text)

        self.assertTrue(srt_file.exists())
        self.assertTrue(ass_file.exists())


if __name__ == "__main__":
    unittest.main()
