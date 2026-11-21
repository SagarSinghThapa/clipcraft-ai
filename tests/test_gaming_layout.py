"""Unit and integration tests for gaming layout engine, dual-stream filtergraphs, and reframing API routing."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from backend.app.api.routes_reframe import reframe_project_clips, ReframeRequest
from backend.app.models.facecam import FacecamRegion
from backend.app.models.layout import (
    LayoutStrategy,
    CanvasResolution,
    GamingLayoutConfig,
    GameplayCompositionMode,
    ExcludedRegion,
)
from backend.app.services.gaming_layout_service import GamingLayoutService
from backend.app.services.storage_service import storage_service


class TestGamingLayout(unittest.TestCase):
    def setUp(self):
        self.layout_svc = GamingLayoutService()
        self.temp_dir = Path(tempfile.mkdtemp(prefix="test_layout_"))
        self.original_base_dir = storage_service.base_dir
        storage_service.base_dir = self.temp_dir

    def tearDown(self):
        storage_service.base_dir = self.original_base_dir
        if self.temp_dir.exists():
            shutil.rmtree(self.temp_dir)

    def test_strategy_resolution_auto_gaming(self):
        """Verifies AUTO_GAMING routes to GAMING_SPLIT when facecam is present and GAMEPLAY_FOCUS when absent."""
        active_facecam = FacecamRegion(is_detected=True, confidence=0.85, x=1400, y=50, width=480, height=270)
        weak_facecam = FacecamRegion(is_detected=True, confidence=0.25, x=1400, y=50, width=480, height=270)
        no_facecam = FacecamRegion(is_detected=False)

        # High confidence facecam -> GAMING_SPLIT
        self.assertEqual(
            self.layout_svc.resolve_strategy(LayoutStrategy.AUTO_GAMING, active_facecam),
            LayoutStrategy.GAMING_SPLIT
        )

        # Low confidence or missing facecam -> GAMEPLAY_FOCUS
        self.assertEqual(
            self.layout_svc.resolve_strategy(LayoutStrategy.AUTO_GAMING, weak_facecam),
            LayoutStrategy.GAMEPLAY_FOCUS
        )
        self.assertEqual(
            self.layout_svc.resolve_strategy(LayoutStrategy.AUTO_GAMING, no_facecam),
            LayoutStrategy.GAMEPLAY_FOCUS
        )
        self.assertEqual(
            self.layout_svc.resolve_strategy(LayoutStrategy.AUTO_GAMING, None),
            LayoutStrategy.GAMEPLAY_FOCUS
        )

        # Explicit strategy overrides
        self.assertEqual(
            self.layout_svc.resolve_strategy(LayoutStrategy.STREAMER_FOCUS, no_facecam),
            LayoutStrategy.STREAMER_FOCUS
        )

    def test_build_gaming_split_crop_fill(self):
        """Verifies dual-stream split, crop, scale, and vstack filtergraph generation with CROP_FILL."""
        cfg = GamingLayoutConfig(
            strategy=LayoutStrategy.GAMING_SPLIT,
            resolution=CanvasResolution.FHD_1080x1920,
            split_ratio=0.375,
            gameplay_composition=GameplayCompositionMode.CROP_FILL,
            exclude_chat_overlay=False
        )
        facecam = FacecamRegion(
            is_detected=True,
            x=1440,
            y=60,
            width=480,
            height=270,
            confidence=0.90
        )

        fg = self.layout_svc.build_filtergraph(
            config=cfg,
            source_w=1920,
            source_h=1080,
            facecam=facecam,
            gameplay_crop_x=450
        )

        # Verify key filter components
        self.assertIn("[0:v]split=2[cam_in][game_in]", fg)
        self.assertIn("crop=480:320", fg)
        self.assertIn("scale=1080:720:flags=lanczos[cam_out]", fg)
        self.assertIn("scale=1080:1200:flags=lanczos[game_out]", fg)
        self.assertIn("[cam_out][game_out]vstack=inputs=2[v_out]", fg)

    def test_build_gaming_split_fit_with_blur(self):
        """Verifies 3-split foreground fit over blurred background and vstack compositing."""
        cfg = GamingLayoutConfig(
            strategy=LayoutStrategy.GAMING_SPLIT,
            resolution=CanvasResolution.FHD_1080x1920,
            split_ratio=0.30,
            gameplay_composition=GameplayCompositionMode.FIT_WITH_BLUR,
            exclude_chat_overlay=True
        )
        facecam = FacecamRegion(
            is_detected=True,
            x=60,
            y=500,
            width=300,
            height=180,
            confidence=0.90
        )

        fg = self.layout_svc.build_filtergraph(
            config=cfg,
            source_w=1920,
            source_h=1080,
            facecam=facecam
        )

        # Verify 3-split and blurred composite
        self.assertIn("[0:v]split=3[cam_in][game_bg_in][game_fg_in]", fg)
        self.assertIn("boxblur=25:5[game_bg]", fg)
        self.assertIn("scale=1080:-2:flags=lanczos[game_fg]", fg)
        self.assertIn("overlay=(W-w)/2:(H-h)/2[game_out]", fg)
        self.assertIn("[cam_out][game_out]vstack=inputs=2[v_out]", fg)

    def test_chat_overlay_exclusion(self):
        """Verifies clean gameplay boundary calculation when chat overlay is excluded."""
        from backend.app.services.gameplay_crop_service import gameplay_crop_service
        chat_reg = gameplay_crop_service.detect_chat_overlay_region(source_w=1920, source_h=1080)
        self.assertIsNotNone(chat_reg)
        self.assertEqual(chat_reg.label, "chat_overlay")
        self.assertGreaterEqual(chat_reg.x, 1600)

        clean_x, clean_y, clean_w, clean_h = gameplay_crop_service.calculate_clean_gameplay_bounds(
            source_w=1920,
            source_h=1080,
            excluded_regions=[chat_reg]
        )
        self.assertEqual(clean_x, 0)
        self.assertEqual(clean_y, 0)
        self.assertEqual(clean_w, chat_reg.x)
        self.assertEqual(clean_h, 1080)

    def test_build_gameplay_focus_filtergraph_with_and_without_blur(self):
        """Verifies blurred background extension and direct 9:16 crop for GAMEPLAY_FOCUS."""
        # 1. With blurred background extension
        cfg_blur = GamingLayoutConfig(
            strategy=LayoutStrategy.GAMEPLAY_FOCUS,
            resolution=CanvasResolution.FHD_1080x1920,
            blur_background=True
        )
        fg_blur = self.layout_svc.build_filtergraph(cfg_blur, 1920, 1080)
        self.assertIn("boxblur=20:5[bg_out]", fg_blur)
        self.assertIn("overlay=(W-w)/2:(H-h)/2[v_out]", fg_blur)

        # 2. Without blurred background (direct 9:16 vertical crop)
        cfg_crop = GamingLayoutConfig(
            strategy=LayoutStrategy.GAMEPLAY_FOCUS,
            resolution=CanvasResolution.FHD_1080x1920,
            blur_background=False
        )
        fg_crop = self.layout_svc.build_filtergraph(cfg_crop, 1920, 1080, gameplay_crop_x=500)
        self.assertIn("crop=608:1080:500:0", fg_crop)
        self.assertIn("scale=1080:1920:flags=lanczos[v_out]", fg_crop)

    def test_build_streamer_focus_filtergraph(self):
        """Verifies streamer focus produces enlarged webcam over blurred context."""
        cfg = GamingLayoutConfig(
            strategy=LayoutStrategy.STREAMER_FOCUS,
            resolution=CanvasResolution.FHD_1080x1920
        )
        facecam = FacecamRegion(
            is_detected=True,
            x=1200,
            y=100,
            width=500,
            height=300,
            confidence=0.88
        )
        fg = self.layout_svc.build_filtergraph(cfg, 1920, 1080, facecam=facecam)
        self.assertIn("boxblur=25:5[bg_out]", fg)
        self.assertIn("crop=500:300:1200:100", fg)
        self.assertIn("overlay=(W-w)/2:(H-h)/2[v_out]", fg)

    def test_multi_resolution_presets_scaling(self):
        """Verifies correct target scaling dimensions for 1080p, 1440p, and 4K."""
        facecam = FacecamRegion(is_detected=True, x=1400, y=50, width=400, height=250)

        # 1440p (2K)
        cfg_2k = GamingLayoutConfig(
            strategy=LayoutStrategy.GAMING_SPLIT,
            resolution=CanvasResolution.QHD_1440x2560
        )
        fg_2k = self.layout_svc.build_filtergraph(cfg_2k, 2560, 1440, facecam=facecam)
        self.assertIn("scale=1440:960", fg_2k)
        self.assertIn("scale=1440:1600", fg_2k)

        # 2160p (4K)
        cfg_4k = GamingLayoutConfig(
            strategy=LayoutStrategy.GAMING_SPLIT,
            resolution=CanvasResolution.UHD_2160x3840
        )
        fg_4k = self.layout_svc.build_filtergraph(cfg_4k, 3840, 2160, facecam=facecam)
        self.assertIn("scale=2160:1440", fg_4k)
        self.assertIn("scale=2160:2400", fg_4k)

    def test_ffmpeg_command_structure(self):
        """Verifies argument array structure for FFmpeg subprocess invocation."""
        cfg = GamingLayoutConfig(strategy=LayoutStrategy.GAMING_SPLIT)
        cmd = self.layout_svc.build_ffmpeg_command(
            source_path=Path("C:/media/in.mp4"),
            output_path=Path("C:/media/out.mp4"),
            config=cfg,
            source_w=1920,
            source_h=1080,
            start_sec=10.5,
            duration_sec=30.0
        )

        self.assertEqual(cmd[0], "ffmpeg")
        self.assertIn("-filter_complex", cmd)
        self.assertIn("-map", cmd)
        self.assertIn("[v_out]", cmd)
        self.assertIn("-ss", cmd)
        self.assertIn("10.500", cmd)
        self.assertIn("-t", cmd)
        self.assertIn("30.000", cmd)
        self.assertEqual(cmd[-1], "C:\\media\\out.mp4")

    @patch("backend.app.api.routes_reframe.reframing_service.reframe_clip")
    def test_reframe_route_integration(self, mock_reframe):
        """Verifies API route accepts gaming layout options and passes them to ReframingService."""
        mock_reframe.return_value = Path("/mock/path/reframed.mp4")

        req = ReframeRequest(
            clip_id="clip_001",
            layout_strategy=LayoutStrategy.GAMING_SPLIT,
            resolution=CanvasResolution.FHD_1080x1920,
            split_ratio=0.40
        )

        res = reframe_project_clips("proj_test", req)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["reframed_clips"], [str(Path("/mock/path/reframed.mp4"))])

        # Verify arguments passed to reframing_service
        self.assertTrue(mock_reframe.called)
        _, kwargs = mock_reframe.call_args
        layout_cfg = kwargs.get("layout_config")
        self.assertIsNotNone(layout_cfg)
        self.assertEqual(layout_cfg.strategy, LayoutStrategy.GAMING_SPLIT)
        self.assertEqual(layout_cfg.resolution, CanvasResolution.FHD_1080x1920)
        self.assertAlmostEqual(layout_cfg.split_ratio, 0.40)


if __name__ == "__main__":
    unittest.main()
