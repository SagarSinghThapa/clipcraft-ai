"""Unit tests for transcript models, audio extraction commands, and transcription caching."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from backend.app.models.project import Project, SourceType, ProjectStatus
from backend.app.models.transcript import WordTiming, TranscriptSegment, FullTranscript
from backend.app.services.storage_service import storage_service, ProjectStorageService
from backend.app.services.audio_service import AudioService
from backend.app.services.transcription_service import TranscriptionService


class TestTranscription(unittest.TestCase):
    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_trans_"))
        self.original_base_dir = storage_service.base_dir
        storage_service.base_dir = self.temp_dir
        self.storage = storage_service
        self.audio_svc = AudioService()
        self.trans_svc = TranscriptionService()

    def tearDown(self):
        storage_service.base_dir = self.original_base_dir
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_transcript_models_serialization(self):
        w1 = WordTiming(word="Building", start=1.0, end=1.5, probability=0.99)
        w2 = WordTiming(word="AI", start=1.6, end=2.0, probability=0.98)
        seg = TranscriptSegment(id=0, start=1.0, end=2.0, text="Building AI", words=[w1, w2])
        transcript = FullTranscript(
            project_id="proj_model_test",
            language="en",
            duration=2.0,
            full_text="Building AI",
            segments=[seg]
        )

        serialized = transcript.model_dump_json()
        deserialized = FullTranscript.model_validate_json(serialized)
        self.assertEqual(deserialized.project_id, "proj_model_test")
        self.assertEqual(len(deserialized.segments), 1)
        self.assertEqual(deserialized.segments[0].words[1].word, "AI")

    def test_audio_extraction_command_structure(self):
        video_p = Path("C:/videos/input.mp4")
        audio_p = Path("C:/videos/output.wav")
        cmd = self.audio_svc.get_audio_extraction_command(video_p, audio_p)

        self.assertIn("-vn", cmd)
        self.assertIn("pcm_s16le", cmd)
        self.assertIn("16000", cmd)
        self.assertIn("-ac", cmd)
        self.assertIn("1", cmd)
        self.assertEqual(cmd[-1], str(audio_p))

    def test_transcription_cache_hit_and_loading(self):
        project_id = "proj_cache_test"
        dirs = self.storage.init_project_workspace(project_id)

        # Generate simulated transcript and save
        simulated = self.trans_svc._generate_simulated_transcript(project_id, "base")
        t_path = dirs["transcript"] / "transcript.json"
        with open(t_path, "w", encoding="utf-8") as f:
            f.write(simulated.model_dump_json())

        # Test load
        loaded = self.trans_svc.load_cached_transcript(project_id)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.project_id, project_id)
        self.assertTrue(len(loaded.segments) > 0)


if __name__ == "__main__":
    unittest.main()
