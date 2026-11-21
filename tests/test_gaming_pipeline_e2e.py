"""End-to-end integration test validating the complete Milestone v2.0 gaming reframing and captioning pipeline."""

import shutil
import tempfile
import unittest
from pathlib import Path

from backend.app.models.project import Project, SourceType, ProjectStatus
from backend.app.models.candidate import CandidateClip, ScoreBreakdown
from backend.app.models.facecam import FacecamRegion
from backend.app.models.layout import (
    LayoutStrategy,
    GameplayCompositionMode,
    CanvasResolution,
    GamingLayoutConfig,
)
from backend.app.models.caption import (
    CaptionPreset,
    CaptionPlacement,
    CaptionStyleConfig,
    WordEmphasis,
)
from backend.app.models.transcript import WordTiming, TranscriptSegment, FullTranscript
from backend.app.models.audio import ReactionCategory
from backend.app.services.storage_service import ProjectStorageService
from backend.app.services.facecam_service import FacecamService
from backend.app.services.gaming_layout_service import GamingLayoutService
from backend.app.services.caption_service import CaptionService
from backend.app.services.audio_energy_service import AudioEnergyService
from backend.app.services.scoring_service import ScoringService


class TestGamingPipelineE2E(unittest.TestCase):
    """Validates complete v2.0 stacked vertical gaming reframing, composition, captions, and non-destructive caching."""

    def setUp(self):
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_gaming_e2e_"))
        self.storage = ProjectStorageService(base_dir=self.temp_dir)
        self.facecam_svc = FacecamService()
        self.layout_svc = GamingLayoutService()
        self.caption_svc = CaptionService()
        self.audio_svc = AudioEnergyService()
        self.scoring_svc = ScoringService()

    def tearDown(self):
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_complete_gaming_pipeline_flow(self):
        """Simulates full Milestone v2.0 workflow from facecam detection to 30% split, FIT_WITH_BLUR, and karaoke captions."""
        project_id = "proj_gaming_e2e"

        # 1. Workspace & Source Metadata
        dirs = self.storage.init_project_workspace(project_id)
        self.assertTrue(dirs["root"].exists())

        project = Project(
            id=project_id,
            title="GTA VI Trailer Reaction Stream",
            source_type=SourceType.LOCAL_FILE,
            source_path=str(dirs["source"] / "stream_1080p60.mp4"),
            status=ProjectStatus.CREATED
        )
        self.storage.save_project_metadata(project)

        # 2. Facecam Detection & Checkpointing
        facecam = FacecamRegion(
            is_detected=True,
            x=20,
            y=20,
            width=360,
            height=270,
            confidence=0.96,
            quadrant="TOP_LEFT"
        )
        self.storage.save_stage_checkpoint(project_id, "facecam", facecam.model_dump())
        cached_facecam = self.storage.load_stage_checkpoint(project_id, "facecam")
        self.assertIsNotNone(cached_facecam)
        self.assertTrue(cached_facecam["is_detected"])

        # 3. Audio Energy & Multimodal Scoring
        words = [
            WordTiming(word="LOOK", start=12.0, end=12.3, probability=0.99),
            WordTiming(word="AT", start=12.35, end=12.5, probability=0.98),
            WordTiming(word="THIS", start=12.55, end=12.8, probability=0.99),
            WordTiming(word="GRAPHICS!", start=12.85, end=13.6, probability=0.99),
            WordTiming(word="NO", start=14.0, end=14.3, probability=0.97),
            WordTiming(word="WAY!", start=14.35, end=15.0, probability=0.99),
        ]
        segments = [
            TranscriptSegment(
                id=0,
                start=12.0,
                end=15.0,
                text="LOOK AT THIS GRAPHICS! NO WAY!",
                words=words
            )
        ]
        transcript = FullTranscript(
            project_id=project_id,
            language="en",
            duration=30.0,
            full_text="LOOK AT THIS GRAPHICS! NO WAY!",
            segments=segments
        )
        t_path = dirs["transcript"] / "transcript.json"
        with open(t_path, "w", encoding="utf-8") as f:
            f.write(transcript.model_dump_json(indent=2))

        # Checkpoint audio energy
        audio_profile = {
            "stats": {"mean_rms": 0.12, "std_rms": 0.05, "step_sec": 0.25},
            "surge_windows": [[12.5, 14.5]],
            "rms_series": [0.10, 0.11, 0.35, 0.40, 0.38, 0.12],
            "timestamps": [11.5, 12.0, 12.5, 13.0, 13.5, 14.0]
        }
        self.storage.save_stage_checkpoint(project_id, "audio_energy", audio_profile)

        # 4. Multimodal Candidate with Custom Overrides
        score_breakdown = ScoreBreakdown(
            category=ReactionCategory.SURPRISE,
            transcript_context_score=85.0,
            audio_reaction_score=92.0,
            streamer_visual_reaction_score=88.0,
            gameplay_activity_score=80.0,
            hook_score=90.0,
            payoff_score=85.0,
            peak_z_score=3.85,
            reaction_density=2.4,
            total_score=88,
            explanation="Extreme vocal surge corroborating visual facecam shock."
        )

        candidate = CandidateClip(
            id="clip_gaming_01",
            project_id=project_id,
            title="Speed Shocked by GTA VI Graphics",
            start_time=10.0,
            end_time=35.0,
            duration=25.0,
            transcript_excerpt=transcript.full_text,
            hook_assessment="Instant vocal scream within 2.5s",
            standalone_context="Streamer reaction to game trailer",
            reasoning="Surprise reaction",
            score=score_breakdown,
            selected_for_rendering=True,
            # Phase 14 Overrides:
            layout_strategy=LayoutStrategy.GAMING_SPLIT,
            gameplay_composition=GameplayCompositionMode.FIT_WITH_BLUR,
            split_ratio=0.30,
            exclude_chat_overlay=True,
            caption_preset=CaptionPreset.GAMING_KARAOKE,
            caption_placement=CaptionPlacement.AUTO,
            resolution=CanvasResolution.FHD_1080x1920
        )

        # Save candidate to analysis folder
        cand_dir = dirs["analysis"]
        cand_dir.mkdir(parents=True, exist_ok=True)
        with open(cand_dir / "candidates.json", "w", encoding="utf-8") as f:
            f.write(f'{{"project_id": "{project_id}", "candidates": [{candidate.model_dump_json()}], "model_used": "llama3.2:3b"}}')

        # 5. Gaming Layout Dimensions & 30% Split Verification
        config = GamingLayoutConfig(
            strategy=candidate.layout_strategy,
            resolution=candidate.resolution,
            split_ratio=candidate.split_ratio,
            gameplay_composition=candidate.gameplay_composition,
            exclude_chat_overlay=candidate.exclude_chat_overlay
        )
        dims = config.get_dimensions()
        self.assertEqual(dims.width, 1080)
        self.assertEqual(dims.height, 1920)
        self.assertEqual(dims.top_height, 576)     # Exactly 30% of 1920
        self.assertEqual(dims.bottom_height, 1344) # Exactly 70% of 1920

        # 6. Dual/Triple-Stream Filtergraph Generation with FIT_WITH_BLUR & Chat Masking
        filtergraph = self.layout_svc.build_filtergraph(
            config=config,
            source_w=1920,
            source_h=1080,
            facecam=facecam
        )
        # Verify 3-split for blurred ambient gameplay background
        self.assertIn("split=3[cam_in][game_bg_in][game_fg_in]", filtergraph)
        self.assertIn("boxblur=25:5", filtergraph)
        # Verify chat overlay exclusion (crop width clamped to clean gameplay area)
        self.assertIn("crop=1700:1080:0:0", filtergraph)
        # Verify vstack composites top streamer and bottom gameplay
        self.assertIn("vstack=inputs=2[v_out]", filtergraph)

        # 7. Word-Level ASS Karaoke Generation with Dynamic Seam Placement
        chunks = self.caption_svc.chunk_words_for_clip(
            words=words,
            clip_start=candidate.start_time,
            clip_end=candidate.end_time,
            confirmed_surge_windows=audio_profile["surge_windows"]
        )
        self.assertTrue(len(chunks) >= 1)

        style_config = CaptionStyleConfig.from_preset(candidate.caption_preset)
        ass_content = self.caption_svc.generate_ass_content(
            chunks=chunks,
            style_config=style_config,
            canvas_w=dims.width,
            canvas_h=dims.height,
            top_height=dims.top_height
        )

        # Verify active word gold highlight (&H0000E6FF&) and pop animation tags
        self.assertIn(style_config.highlight_color, ass_content)
        self.assertIn(r"\fscx112\fscy112", ass_content)
        # Dynamic seam placement: top_height (576) + 35 = 611 in ASS style definition
        expected_seam_margin_v = dims.top_height + 35
        self.assertIn(f",8,40,40,{expected_seam_margin_v},1", ass_content)

        # 8. Source-Aware Quality Labeling Verification
        source_max_dim = max(1920, 1080) # 1920
        # When exporting to 1080p (height 1920), should be native (1920 <= 1920)
        self.assertFalse(dims.height > source_max_dim)

        # When exporting to 4K UHD (3840), should detect upscaled status (3840 > 1920)
        config_4k = GamingLayoutConfig(resolution=CanvasResolution.UHD_2160x3840)
        dims_4k = config_4k.get_dimensions()
        self.assertTrue(dims_4k.height > source_max_dim)

        # 9. Non-Destructive Caching Verification
        # Upstream checkpoints (facecam, audio_energy, transcript) must remain cached and unmodified
        reloaded_facecam = self.storage.load_stage_checkpoint(project_id, "facecam")
        reloaded_audio = self.storage.load_stage_checkpoint(project_id, "audio_energy")
        self.assertEqual(reloaded_facecam["confidence"], 0.96)
        self.assertEqual(len(reloaded_audio["surge_windows"]), 1)


if __name__ == "__main__":
    unittest.main()
