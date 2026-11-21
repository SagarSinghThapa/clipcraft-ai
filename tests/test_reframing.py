"""Unit tests for 9:16 vertical reframing, EMA smoothing, and filtergraphs."""

import unittest
from pathlib import Path
from backend.app.services.reframing_service import ReframingService


class TestReframing(unittest.TestCase):
    def setUp(self):
        self.svc = ReframingService()

    def test_calculate_9_16_crop_dimensions(self):
        crop_w, crop_h = self.svc.calculate_9_16_crop_dimensions(1920, 1080)
        self.assertEqual(crop_h, 1080)
        self.assertEqual(crop_w, 608)  # 1080 * 9 / 16 = 607.5 -> even 608
        self.assertEqual(crop_w % 2, 0)
        self.assertEqual(crop_h % 2, 0)

    def test_ema_smoothing_reduces_variance(self):
        # Oscillating noisy coordinates
        raw_positions = [600.0, 650.0, 590.0, 660.0, 605.0]
        smoothed = self.svc.apply_ema_smoothing(raw_positions, alpha=0.2)

        self.assertEqual(len(smoothed), len(raw_positions))
        self.assertEqual(smoothed[0], 600.0)
        # Check that extreme jumps are dampened
        self.assertLess(smoothed[1], 650.0)
        self.assertGreater(smoothed[2], 590.0)

    def test_reframe_filter_command(self):
        input_p = Path("C:/videos/raw.mp4")
        output_p = Path("C:/videos/reframed.mp4")

        cmd = self.svc.build_reframe_command(
            input_p, output_p, crop_w=608, crop_h=1080, crop_x=656, target_w=1080, target_h=1920
        )
        self.assertIn("-vf", cmd)
        vf_idx = cmd.index("-vf")
        filter_str = cmd[vf_idx + 1]
        self.assertIn("crop=608:1080:656:0", filter_str)
        self.assertIn("scale=1080:1920", filter_str)
        self.assertEqual(cmd[-1], str(output_p))


if __name__ == "__main__":
    unittest.main()
