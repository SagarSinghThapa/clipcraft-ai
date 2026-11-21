"""Unit tests for gaming layout models, canvas resolution presets, and content-aware gameplay cropping."""

import unittest
import numpy as np

from backend.app.models.facecam import FacecamRegion
from backend.app.models.layout import (
    LayoutStrategy,
    CanvasResolution,
    GamingLayoutConfig,
    CanvasDimensions,
    GameplayCropWindow,
)
from backend.app.services.gameplay_crop_service import GameplayCropService


class TestGamingCrop(unittest.TestCase):
    def setUp(self):
        self.crop_svc = GameplayCropService()

    def test_canvas_dimensions_geometry(self):
        """Validates top + bottom heights sum to total height and dimensions are even integers."""
        for res in [CanvasResolution.FHD_1080x1920, CanvasResolution.QHD_1440x2560, CanvasResolution.UHD_2160x3840]:
            cfg = GamingLayoutConfig(resolution=res, split_ratio=0.375)
            dims = cfg.get_dimensions()
            self.assertEqual(dims.top_height + dims.bottom_height, dims.height)
            self.assertEqual(dims.width % 2, 0)
            self.assertEqual(dims.height % 2, 0)
            self.assertEqual(dims.top_height % 2, 0)
            self.assertEqual(dims.bottom_height % 2, 0)

        # Explicit check for 1080x1920 defaults
        fhd_dims = GamingLayoutConfig(resolution=CanvasResolution.FHD_1080x1920).get_dimensions()
        self.assertEqual(fhd_dims.width, 1080)
        self.assertEqual(fhd_dims.height, 1920)
        self.assertEqual(fhd_dims.top_height, 720)
        self.assertEqual(fhd_dims.bottom_height, 1200)

    def test_calculate_gameplay_crop_dimensions(self):
        """Validates that cropped sub-rectangle exactly matches the target aspect ratio without distortion."""
        # 1. 1080x1920 Canvas (Bottom region: 1080x1200, aspect 9:10 = 0.9)
        # Source 1920x1080: crop_h = 1080, crop_w = 1080 * 0.9 = 972
        crop_w, crop_h = self.crop_svc.calculate_gameplay_crop_dimensions(
            source_w=1920, source_h=1080, target_w=1080, target_h=1200
        )
        self.assertEqual(crop_w, 972)
        self.assertEqual(crop_h, 1080)
        self.assertAlmostEqual(crop_w / crop_h, 1080 / 1200, places=4)

        # 2. 1440x2560 Canvas (Bottom region: 1440x1600, aspect 9:10 = 0.9)
        # Source 2560x1440: crop_h = 1440, crop_w = 1440 * 0.9 = 1296
        crop_w2, crop_h2 = self.crop_svc.calculate_gameplay_crop_dimensions(
            source_w=2560, source_h=1440, target_w=1440, target_h=1600
        )
        self.assertEqual(crop_w2, 1296)
        self.assertEqual(crop_h2, 1440)
        self.assertAlmostEqual(crop_w2 / crop_h2, 1440 / 1600, places=4)

        # 3. 4K 2160x3840 Canvas (Bottom region: 2160x2400)
        # Source 3840x2160: crop_h = 2160, crop_w = 2160 * 0.9 = 1944
        crop_w3, crop_h3 = self.crop_svc.calculate_gameplay_crop_dimensions(
            source_w=3840, source_h=2160, target_w=2160, target_h=2400
        )
        self.assertEqual(crop_w3, 1944)
        self.assertEqual(crop_h3, 2160)

    def test_facecam_masking(self):
        """Verifies that streamer facecam region is zeroed out in visual activity map."""
        activity = np.ones((1080, 1920), dtype=np.float32) * 10.0
        facecam = FacecamRegion(
            is_detected=True,
            x=1400,
            y=50,
            width=480,
            height=270,
            confidence=0.95
        )

        masked = self.crop_svc.mask_facecam_activity(activity, facecam)

        # Inside facecam area must be zero
        self.assertEqual(masked[100, 1500], 0.0)
        self.assertEqual(masked[200, 1600], 0.0)

        # Outside facecam area should remain unaffected
        self.assertEqual(masked[500, 500], 10.0)
        self.assertEqual(masked[800, 960], 10.0)

    def test_estimate_activity_x_focuses_outside_facecam(self):
        """
        When streamer facecam has huge motion (e.g. streamer laughing/reacting)
        and gameplay has smaller motion elsewhere (e.g. car chase at X=400),
        masking facecam ensures gameplay action at X=400 is chosen.
        """
        activity = np.zeros((1080, 1920), dtype=np.float32)

        # 1. High false motion inside streamer facecam (top-right X: 1400..1880, Y: 50..320)
        activity[50:320, 1400:1880] = 500.0

        # 2. Genuine gameplay action at X: 350..550
        activity[400:800, 350:550] = 50.0

        facecam = FacecamRegion(
            is_detected=True,
            x=1400,
            y=50,
            width=480,
            height=270,
            confidence=0.95
        )

        crop_w = 972
        chosen_x = self.crop_svc.estimate_activity_x(
            frame_diff_or_gradient=activity,
            crop_w=crop_w,
            facecam=facecam
        )

        # Chosen X window [chosen_x, chosen_x + 972] must enclose the gameplay motion at 350..550
        self.assertLessEqual(chosen_x, 350)
        self.assertGreaterEqual(chosen_x + crop_w, 550)
        # Must be an even integer
        self.assertEqual(chosen_x % 2, 0)

    def test_ema_smoothing_prevents_wild_jumps(self):
        """Verifies EMA smoothing dampens extreme coordinate jumps and stays within bounds."""
        noisy_coords = [300.0, 750.0, 250.0, 800.0, 320.0]
        smoothed = self.crop_svc.apply_ema_smoothing(noisy_coords, alpha=0.15, max_x=948)

        self.assertEqual(len(smoothed), len(noisy_coords))
        # Initial point starts at rounded even pos
        self.assertEqual(smoothed[0], 300)
        # Sharp jump to 750 is heavily dampened
        self.assertLess(smoothed[1], 400)
        # Every coordinate is even and bounded
        for val in smoothed:
            self.assertEqual(val % 2, 0)
            self.assertGreaterEqual(val, 0)
            self.assertLessEqual(val, 948)

    def test_get_gameplay_crop_window(self):
        """Verifies complete GameplayCropWindow object generation."""
        dims = CanvasDimensions(
            width=1080,
            height=1920,
            top_height=720,
            bottom_height=1200
        )
        window = self.crop_svc.get_gameplay_crop_window(
            source_w=1920,
            source_h=1080,
            canvas_dims=dims,
            preferred_x=450
        )

        self.assertEqual(window.width, 972)
        self.assertEqual(window.height, 1080)
        self.assertEqual(window.x, 450)
        self.assertEqual(window.y, 0)
        self.assertEqual(window.aspect_ratio, "1080:1200")


if __name__ == "__main__":
    unittest.main()
