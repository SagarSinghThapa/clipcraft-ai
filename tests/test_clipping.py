"""Unit tests for FFmpeg precision video clipping commands."""

import unittest
from pathlib import Path
from backend.app.services.clipping_service import ClippingService


class TestClipping(unittest.TestCase):
    def setUp(self):
        self.svc = ClippingService()

    def test_clipping_command_accuracy(self):
        source_p = Path("C:/videos/source.mp4")
        output_p = Path("C:/videos/clip_01.mp4")
        start_t = 14.5
        end_t = 42.125

        cmd = self.svc.build_cut_command(source_p, output_p, start_t, end_t)

        self.assertIn("-ss", cmd)
        ss_idx = cmd.index("-ss")
        self.assertEqual(cmd[ss_idx + 1], "14.500")

        self.assertIn("-to", cmd)
        to_idx = cmd.index("-to")
        self.assertEqual(cmd[to_idx + 1], "42.125")

        self.assertIn("-c:v", cmd)
        self.assertIn("libx264", cmd)
        self.assertIn("-crf", cmd)
        self.assertIn("18", cmd)
        self.assertIn("-c:a", cmd)
        self.assertIn("aac", cmd)
        self.assertIn("-avoid_negative_ts", cmd)
        self.assertIn("make_zero", cmd)
        self.assertEqual(cmd[-1], str(output_p))


if __name__ == "__main__":
    unittest.main()
