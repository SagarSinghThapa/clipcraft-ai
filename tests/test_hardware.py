"""Unit tests for hardware capability detection."""

import unittest
from backend.app.core.hardware import detect_hardware


class TestHardwareDetection(unittest.TestCase):
    def test_detect_hardware_returns_valid_structure(self):
        caps = detect_hardware()
        self.assertIn("device", caps)
        self.assertIn(caps["device"], ["cpu", "cuda"])
        self.assertIn("compute_type", caps)
        self.assertIn("cuda_available", caps)
        self.assertIsInstance(caps["cuda_available"], bool)
        self.assertIn("description", caps)
        self.assertTrue(len(caps["description"]) > 0)


if __name__ == "__main__":
    unittest.main()
