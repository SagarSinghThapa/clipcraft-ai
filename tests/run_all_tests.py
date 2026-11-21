"""Test runner executing all ClipCraft unit and integration test suites."""

import sys
import unittest
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parents[1]
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))


def run_all_tests():
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_modules = [
        "tests.test_hardware",
        "tests.test_storage",
        "tests.test_ingestion",
        "tests.test_transcription",
        "tests.test_analysis",
        "tests.test_scoring",
        "tests.test_clipping",
        "tests.test_reframing",
        "tests.test_captions",
        "tests.test_karaoke_captions",
        "tests.test_captions_api",
        "tests.test_facecam",
        "tests.test_facecam_api",
        "tests.test_gaming_crop",
        "tests.test_gaming_layout",
        "tests.test_audio_energy",
        "tests.test_causal_sequence",
        "tests.test_multimodal_scoring",
        "tests.test_ui_controls_backend",
        "tests.test_gaming_pipeline_e2e",
        "tests.test_e2e_pipeline",
    ]

    for mod in test_modules:
        try:
            tests = loader.loadTestsFromName(mod)
            suite.addTests(tests)
        except Exception as e:
            print(f"Error loading {mod}: {e}")

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
