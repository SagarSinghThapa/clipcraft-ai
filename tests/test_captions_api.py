"""Integration tests for dynamic seam-aware caption placement, style caching, and REST API routes."""

import json
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from backend.app.models.candidate import CandidateClip, CandidateList, ScoreBreakdown
from backend.app.models.caption import CaptionPreset, CaptionPlacement, CaptionStyleConfig
from backend.app.models.transcript import FullTranscript, TranscriptSegment, WordTiming
from backend.app.services.caption_service import CaptionService
from backend.app.api.routes_captions import CaptionRequest, burn_project_captions


class TestCaptionsAPI(unittest.TestCase):
    def setUp(self):
        self.svc = CaptionService()
        self.project_id = "test_captions_proj"
        self.clip_id = "clip_test_123"

        self.candidate = CandidateClip(
            id=self.clip_id,
            project_id=self.project_id,
            start_time=10.0,
            end_time=15.0,
            duration=5.0,
            title="Epic Win",
            transcript_excerpt="What is happening right now",
            hook_assessment="High energy opening hook",
            standalone_context="Streamer reaction during gaming",
            reasoning="Intense reaction",
            score=ScoreBreakdown(total_score=95),
            selected_for_rendering=True
        )

        self.transcript = FullTranscript(
            project_id=self.project_id,
            language="en",
            duration=30.0,
            text="What is happening right now",
            segments=[
                TranscriptSegment(
                    id=0,
                    seek=0,
                    start=10.0,
                    end=14.0,
                    text="What is happening right now",
                    words=[
                        WordTiming(word="What", start=10.0, end=10.4),
                        WordTiming(word="is", start=10.5, end=10.8),
                        WordTiming(word="happening", start=10.9, end=11.6),
                        WordTiming(word="right", start=11.7, end=12.0),
                        WordTiming(word="now", start=12.1, end=12.5),
                    ]
                )
            ]
        )

    def test_auto_placement_adapts_to_gaming_split_geometry(self):
        """When top_height is provided (e.g. 720 on 1080p), AUTO placement positions subtitles in the seam."""
        cfg = CaptionStyleConfig(preset=CaptionPreset.GAMING_KARAOKE, placement=CaptionPlacement.AUTO)
        margin_v, alignment = cfg.get_placement_geometry(canvas_h=1920, top_height=720)

        # Seam offset = 720 + round(35 * 1.0) = 755
        self.assertEqual(margin_v, 755)
        self.assertEqual(alignment, 8)  # Top-Center alignment

        # At 1440p (top_height = 960, scale = 1.3333)
        margin_v_1440, alignment_1440 = cfg.get_placement_geometry(canvas_h=2560, top_height=960)
        self.assertEqual(margin_v_1440, 960 + round(35 * (2560 / 1920)))
        self.assertEqual(alignment_1440, 8)

    def test_auto_placement_defaults_to_bottom_for_standard_layouts(self):
        """When top_height is None (single-stream or no facecam), AUTO placement defaults to safe bottom zone."""
        cfg = CaptionStyleConfig(preset=CaptionPreset.GAMING_KARAOKE, placement=CaptionPlacement.AUTO)
        margin_v, alignment = cfg.get_placement_geometry(canvas_h=1920, top_height=None)

        self.assertEqual(margin_v, 320)
        self.assertEqual(alignment, 2)  # Bottom-Center alignment

    @patch("backend.app.services.caption_service.probe_media_metadata")
    @patch("backend.app.services.caption_service.is_ffmpeg_available", return_value=True)
    @patch("backend.app.services.caption_service.subprocess.run")
    @patch("backend.app.services.storage_service.storage_service.init_project_workspace")
    @patch("backend.app.services.storage_service.storage_service.load_stage_checkpoint")
    @patch("backend.app.services.storage_service.storage_service.save_stage_checkpoint")
    @patch("backend.app.services.transcription_service.transcription_service.load_cached_transcript")
    def test_caption_style_caching_does_not_recompute_prior_stages(
        self,
        mock_load_transcript,
        mock_save_checkpoint,
        mock_load_checkpoint,
        mock_init_workspace,
        mock_subproc,
        mock_ffmpeg,
        mock_probe_meta
    ):
        """Switching presets invalidates final_clip.mp4 and burns new subtitles without touching earlier stages."""
        from backend.app.models.project import MediaMetadata
        mock_probe_meta.return_value = MediaMetadata(
            width=1080,
            height=1920,
            duration=5.0,
            fps=30.0,
            format_name="mp4"
        )
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            clip_dir = tmppath / "clips" / self.clip_id
            clip_dir.mkdir(parents=True, exist_ok=True)

            reframed_mp4 = clip_dir / "reframed.mp4"
            reframed_mp4.write_text("fake video content")

            mock_init_workspace.return_value = {
                "clips": tmppath / "clips",
                "metadata": tmppath / "metadata"
            }
            mock_load_transcript.return_value = self.transcript
            mock_load_checkpoint.return_value = {"is_detected": True}

            # Create final_clip fake file after burn
            final_mp4 = clip_dir / "final_clip.mp4"
            def fake_burn(*args, **kwargs):
                final_mp4.write_text("fake burned video")
                return MagicMock(returncode=0)
            mock_subproc.side_effect = fake_burn

            # 1. Burn with default GAMING_KARAOKE
            cfg_karaoke = CaptionStyleConfig.from_preset(CaptionPreset.GAMING_KARAOKE)
            res1 = self.svc.burn_captions_for_clip(
                self.project_id,
                self.candidate,
                force_recompute=False,
                style_config=cfg_karaoke
            )
            self.assertEqual(res1, final_mp4)
            self.assertEqual(mock_subproc.call_count, 1)

            # Check ASS contents generated
            ass_file = clip_dir / "captions.ass"
            self.assertTrue(ass_file.exists())
            ass_content = ass_file.read_text(encoding="utf-8")
            self.assertIn("&H0000E6FF&", ass_content)  # Gold highlight tag present

            # 2. Call again with same config without force_recompute -> should reuse cached without calling FFmpeg
            res2 = self.svc.burn_captions_for_clip(
                self.project_id,
                self.candidate,
                force_recompute=False,
                style_config=cfg_karaoke
            )
            self.assertEqual(res2, final_mp4)
            self.assertEqual(mock_subproc.call_count, 1)  # No extra FFmpeg call!

            # 3. Switch preset to CLEAN -> style changed, must burn new ASS
            cfg_clean = CaptionStyleConfig.from_preset(CaptionPreset.CLEAN)
            res3 = self.svc.burn_captions_for_clip(
                self.project_id,
                self.candidate,
                force_recompute=False,
                style_config=cfg_clean
            )
            self.assertEqual(res3, final_mp4)
            self.assertEqual(mock_subproc.call_count, 2)  # Re-burned with clean style!

            clean_ass = ass_file.read_text(encoding="utf-8")
            self.assertNotIn("&H0000E6FF&", clean_ass)  # Karaoke gold tag absent in CLEAN

    @patch("backend.app.api.routes_captions.caption_service.burn_captions_for_clip")
    @patch("backend.app.api.routes_captions.analysis_service.load_cached_candidates")
    def test_caption_route_with_preset_and_placement(self, mock_load_candidates, mock_burn_clip):
        """API route accepts preset, placement, karaoke toggle, and passes configured style to service."""
        mock_load_candidates.return_value = CandidateList(
            project_id=self.project_id,
            candidates=[self.candidate]
        )
        mock_burn_clip.return_value = Path("projects/test/clips/clip_test_123/final_clip.mp4")

        payload = CaptionRequest(
            clip_id=self.clip_id,
            preset=CaptionPreset.MINIMAL,
            placement=CaptionPlacement.LOWER_CENTER,
            karaoke_enabled=False,
            words_per_chunk=4
        )

        resp = burn_project_captions(self.project_id, payload)
        self.assertEqual(resp["status"], "success")
        self.assertEqual(resp["preset"], "MINIMAL")
        self.assertEqual(resp["placement"], "LOWER_CENTER")

        # Verify style_config passed to service
        mock_burn_clip.assert_called_once()
        _, kwargs = mock_burn_clip.call_args
        passed_cfg = kwargs.get("style_config")
        self.assertIsNotNone(passed_cfg)
        self.assertEqual(passed_cfg.preset, CaptionPreset.MINIMAL)
        self.assertEqual(passed_cfg.placement, CaptionPlacement.LOWER_CENTER)
        self.assertFalse(passed_cfg.karaoke_enabled)
        self.assertEqual(passed_cfg.words_per_chunk, 4)


if __name__ == "__main__":
    unittest.main()
