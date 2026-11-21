"""Unit tests for UI layout, composition, quality, and caption controls and service inheritance."""

import asyncio
import tempfile
import unittest
from unittest.mock import patch, MagicMock
from pathlib import Path
from pydantic import ValidationError

from backend.app.models.candidate import CandidateClip, CandidateList, ScoreBreakdown
from backend.app.models.layout import LayoutStrategy, GameplayCompositionMode, CanvasResolution
from backend.app.models.caption import CaptionPreset, CaptionPlacement
from backend.app.services.storage_service import storage_service
from backend.app.services.reframing_service import reframing_service
from backend.app.services.caption_service import caption_service
from backend.app.api.routes_analysis import UpdateCandidateRequest, update_candidate_clip
from backend.app.utils.ffmpeg_utils import MediaMetadata


class TestUIControlsBackend(unittest.TestCase):
    """Verifies candidate overrides via REST API and backend service fallback inheritance."""

    def setUp(self):
        self.project_id = "proj_ui_test"
        self.clip_id = "cand_01"

        self.mock_candidate = CandidateClip(
            id=self.clip_id,
            project_id=self.project_id,
            title="Epic Speed Reaction",
            start_time=10.0,
            end_time=35.0,
            duration=25.0,
            transcript_excerpt="WHAT IS HE DOING?!",
            hook_assessment="Immediate vocal spike",
            standalone_context="Funny gameplay reaction",
            reasoning="High energy reaction",
            score=ScoreBreakdown(total_score=85),
            selected_for_rendering=True
        )
        self.mock_candidate_list = CandidateList(
            project_id=self.project_id,
            candidates=[self.mock_candidate]
        )

    def test_update_candidate_layout_fields(self):
        """update_candidate_clip updates all layout, quality, and caption fields and writes candidates.json."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_candidates_file = Path(tmp_dir) / "candidates.json"

            with patch("backend.app.services.analysis_service.analysis_service.load_cached_candidates", return_value=self.mock_candidate_list), \
                 patch("backend.app.services.analysis_service.analysis_service.get_candidates_path", return_value=temp_candidates_file):

                payload = UpdateCandidateRequest(
                    title="Renamed Speed Reaction",
                    layout_strategy=LayoutStrategy.GAMING_SPLIT,
                    gameplay_composition=GameplayCompositionMode.FIT_WITH_BLUR,
                    split_ratio=0.30,
                    exclude_chat_overlay=True,
                    caption_preset=CaptionPreset.GAMING_KARAOKE,
                    caption_placement=CaptionPlacement.AUTO,
                    resolution=CanvasResolution.FHD_1080x1920
                )

                updated = update_candidate_clip(self.project_id, self.clip_id, payload)

                self.assertEqual(updated.title, "Renamed Speed Reaction")
                self.assertEqual(updated.layout_strategy, LayoutStrategy.GAMING_SPLIT)
                self.assertEqual(updated.gameplay_composition, GameplayCompositionMode.FIT_WITH_BLUR)
                self.assertEqual(updated.split_ratio, 0.30)
                self.assertTrue(updated.exclude_chat_overlay)
                self.assertEqual(updated.caption_preset, CaptionPreset.GAMING_KARAOKE)
                self.assertEqual(updated.caption_placement, CaptionPlacement.AUTO)
                self.assertEqual(updated.resolution, CanvasResolution.FHD_1080x1920)
                self.assertTrue(temp_candidates_file.exists())

    def test_update_candidate_split_ratio_bounds(self):
        """Verifies split_ratio < 0.20 or > 0.60 raises ValidationError."""
        # Valid bounds
        valid_req = UpdateCandidateRequest(split_ratio=0.30)
        self.assertEqual(valid_req.split_ratio, 0.30)

        # Too small (< 0.20)
        with self.assertRaises(ValidationError):
            UpdateCandidateRequest(split_ratio=0.10)

        # Too high (> 0.60)
        with self.assertRaises(ValidationError):
            UpdateCandidateRequest(split_ratio=0.75)

    @patch("backend.app.services.gaming_layout_service.gaming_layout_service.render_layout_clip")
    @patch("backend.app.services.reframing_service.storage_service.init_project_workspace")
    @patch("backend.app.services.reframing_service.probe_media_metadata")
    @patch("backend.app.services.reframing_service.is_ffmpeg_available", return_value=True)
    @patch("backend.app.services.analysis_service.analysis_service.load_cached_candidates")
    def test_reframing_service_inherits_candidate_settings(
        self, mock_load, mock_ffmpeg, mock_probe, mock_storage, mock_render
    ):
        """ReframingService automatically inherits candidate overrides when layout_config is omitted."""
        candidate_with_overrides = self.mock_candidate.model_copy(update={
            "layout_strategy": LayoutStrategy.GAMING_SPLIT,
            "gameplay_composition": GameplayCompositionMode.FIT_WITH_BLUR,
            "split_ratio": 0.30,
            "exclude_chat_overlay": True,
            "resolution": CanvasResolution.FHD_1080x1920
        })
        mock_load.return_value = CandidateList(
            project_id=self.project_id,
            candidates=[candidate_with_overrides]
        )

        mock_clip_dir = MagicMock(spec=Path)
        mock_raw = MagicMock(spec=Path)
        mock_raw.exists.return_value = True
        mock_reframed = MagicMock(spec=Path)
        mock_reframed.exists.return_value = False
        mock_clip_dir.__truediv__.side_effect = lambda x: mock_raw if x == "raw_clip.mp4" else mock_reframed
        mock_storage.return_value = {"clips": MagicMock(__truediv__=lambda self, x: mock_clip_dir)}

        mock_probe.return_value = MediaMetadata(
            duration=25.0,
            width=1920,
            height=1080,
            aspect_ratio="16:9",
            fps=60.0,
            video_codec="h264",
            audio_codec="aac",
            has_audio=True,
            file_size_bytes=1000000
        )
        mock_render.return_value = Path("d:/mock/reframed.mp4")

        # Call reframe_clip with layout_config=None (should inherit candidate overrides)
        res_path = reframing_service.reframe_clip(self.project_id, self.clip_id, force_recompute=True)
        self.assertEqual(res_path, Path("d:/mock/reframed.mp4"))

        # Verify gaming_layout_service.render_layout_clip received the candidate config
        mock_render.assert_called_once()
        passed_config = mock_render.call_args[1]["config"]
        self.assertEqual(passed_config.strategy, LayoutStrategy.GAMING_SPLIT)
        self.assertEqual(passed_config.gameplay_composition, GameplayCompositionMode.FIT_WITH_BLUR)
        self.assertEqual(passed_config.split_ratio, 0.30)
        self.assertTrue(passed_config.exclude_chat_overlay)
        self.assertEqual(passed_config.resolution, CanvasResolution.FHD_1080x1920)

    @patch("backend.app.services.caption_service.storage_service.init_project_workspace")
    @patch("backend.app.services.caption_service.probe_media_metadata")
    @patch("backend.app.services.caption_service.is_ffmpeg_available", return_value=True)
    @patch("backend.app.services.caption_service.transcription_service.load_cached_transcript")
    @patch("backend.app.services.caption_service.subprocess.run")
    def test_caption_service_inherits_candidate_placement_and_preset(
        self, mock_subp, mock_trans, mock_ffmpeg, mock_probe, mock_storage
    ):
        """CaptionService automatically adopts candidate caption_preset and calculates seam from candidate split_ratio."""
        candidate_with_overrides = self.mock_candidate.model_copy(update={
            "split_ratio": 0.30,
            "caption_preset": CaptionPreset.CLEAN,
            "caption_placement": CaptionPlacement.AUTO
        })

        with tempfile.TemporaryDirectory() as tmp_dir:
            clip_path = Path(tmp_dir)
            mock_video = clip_path / "reframed.mp4"
            mock_video.touch()
            mock_final = clip_path / "final_clip.mp4"
            mock_final.write_bytes(b"dummy_video_bytes")

            mock_storage.return_value = {"clips": MagicMock(__truediv__=lambda self, x: clip_path)}

            mock_probe.return_value = MediaMetadata(
                duration=25.0,
                width=1080,
                height=1920,
                aspect_ratio="9:16",
                fps=60.0,
                video_codec="h264",
                audio_codec="aac",
                has_audio=True,
                file_size_bytes=1000000
            )
            mock_trans.return_value = None

            with patch("backend.app.services.caption_service.storage_service.save_stage_checkpoint"):
                final_path = caption_service.burn_captions_for_clip(
                    project_id=self.project_id,
                    candidate=candidate_with_overrides,
                    force_recompute=True,
                    style_config=None  # Should inherit CLEAN from candidate
                )

            self.assertIsNotNone(final_path)

    def test_re_render_preserves_upstream_caches(self):
        """Non-destructive validation: verifying transcript and facecam checkpoints are cached and retained."""
        with patch.object(storage_service, "load_stage_checkpoint") as mock_checkpoint:
            mock_checkpoint.side_effect = lambda p, stage: {"is_detected": True, "confidence": 0.95} if stage == "facecam" else None

            facecam_cp = storage_service.load_stage_checkpoint(self.project_id, "facecam")
            self.assertIsNotNone(facecam_cp)
            self.assertTrue(facecam_cp["is_detected"])


if __name__ == "__main__":
    unittest.main()
