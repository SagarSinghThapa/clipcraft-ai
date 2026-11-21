"""Unit tests for Phase 13: Dual-Baseline Audio Reaction Engine & Speech Corroboration."""

import wave
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
import numpy as np

from backend.app.models.audio import (
    ReactionCategory,
    GlobalAudioStats,
    ClipAudioProfile,
    calculate_audio_reaction_score
)
from backend.app.models.transcript import WordTiming
from backend.app.services.audio_energy_service import AudioEnergyService


class TestAudioEnergy(unittest.TestCase):
    def setUp(self):
        self.svc = AudioEnergyService()

    def _create_synthetic_wav(
        self,
        filepath: Path,
        duration_sec: float = 10.0,
        framerate: int = 16000,
        quiet_amp: float = 0.05,
        burst_amp: float = 0.85,
        burst_interval: tuple = (4.0, 5.0)
    ):
        """Generates a synthetic 16kHz 16-bit mono PCM WAV with an intentional loud burst."""
        total_samples = int(duration_sec * framerate)
        samples = np.full(total_samples, quiet_amp, dtype=np.float32)

        # Inject loud sinusoidal burst
        burst_start = int(burst_interval[0] * framerate)
        burst_end = int(burst_interval[1] * framerate)
        t = np.linspace(0, burst_interval[1] - burst_interval[0], burst_end - burst_start, endpoint=False)
        samples[burst_start:burst_end] = burst_amp * np.sin(2 * np.pi * 440.0 * t)

        # Convert to int16 PCM
        int16_samples = (np.clip(samples, -1.0, 1.0) * 32767.0).astype(np.int16)

        with wave.open(str(filepath), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(framerate)
            wf.writeframes(int16_samples.tobytes())

    def test_cumulative_sum_rms_accuracy(self):
        """O(N) cumulative sum RMS calculation must match mathematical definition."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "test.wav"
            self._create_synthetic_wav(wav_path, duration_sec=4.0, burst_amp=0.5, burst_interval=(1.0, 2.0))

            rms_series, timestamps, duration = self.svc.calculate_rms_series(wav_path, window_sec=0.50, step_sec=0.25)
            self.assertGreater(len(rms_series), 0)
            self.assertAlmostEqual(duration, 4.0, places=1)

            # Peak RMS must occur inside the burst interval [1.0s, 2.0s]
            peak_idx = int(np.argmax(rms_series))
            peak_time = timestamps[peak_idx]
            self.assertTrue(0.9 <= peak_time <= 2.1, f"Peak at {peak_time}s not in burst range")
            self.assertGreater(rms_series[peak_idx], 0.3)

    def test_global_and_local_dual_baseline(self):
        """Sudden loud burst after quiet speech produces high local contrast (delta_local >= 2.5)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "contrast.wav"
            # 12 seconds with quiet speech (amp=0.04) and a sharp 500ms shout at 6.0s (amp=0.90)
            self._create_synthetic_wav(wav_path, duration_sec=12.0, quiet_amp=0.04, burst_amp=0.90, burst_interval=(6.0, 6.5))

            rms_series, timestamps, duration = self.svc.calculate_rms_series(wav_path, window_sec=0.50, step_sec=0.25)
            stats = self.svc.compute_global_stats(rms_series, duration)
            mu_local, delta_local = self.svc.compute_local_baselines(rms_series, step_sec=0.25, neighborhood_sec=6.0)

            # Find peak local contrast
            peak_idx = int(np.argmax(delta_local))
            peak_time = timestamps[peak_idx]

            self.assertTrue(5.5 <= peak_time <= 6.8, f"Local peak at {peak_time}s")
            self.assertGreater(delta_local[peak_idx], 2.5, "Expected sudden burst to have delta_local >= 2.5")
            self.assertGreater(stats.max_rms, stats.mean_rms)

    def test_speech_corroboration_distinguishes_screams_from_explosions(self):
        """Surges coinciding with words receive full score; isolated non-speech spikes are penalized."""
        surge_time = 5.0
        words_present = [
            WordTiming(word="WHAT", start=4.8, end=5.3),
            WordTiming(word="IS", start=5.4, end=5.6),
            WordTiming(word="THAT", start=5.7, end=6.0)
        ]
        words_absent = [
            WordTiming(word="quiet", start=0.5, end=1.0),
            WordTiming(word="talk", start=1.2, end=1.8)
        ]

        # Case 1: Speech present
        speech_map_confirmed = self.svc.corroborate_speech([surge_time], words_present, tolerance_sec=1.0)
        self.assertTrue(speech_map_confirmed[surge_time])

        score_confirmed = calculate_audio_reaction_score(peak_z=3.0, local_contrast=3.0, density=0.15, speech_confirmed=True)
        self.assertGreaterEqual(score_confirmed, 85.0)

        # Case 2: Non-speech noise / explosion
        speech_map_unconfirmed = self.svc.corroborate_speech([surge_time], words_absent, tolerance_sec=1.0)
        self.assertFalse(speech_map_unconfirmed[surge_time])

        score_unconfirmed = calculate_audio_reaction_score(peak_z=3.0, local_contrast=3.0, density=0.15, speech_confirmed=False)
        # Should be penalized by 0.60x factor
        self.assertLess(score_unconfirmed, 65.0)
        self.assertAlmostEqual(score_unconfirmed, score_confirmed * 0.60, places=1)

    def test_vocal_burst_clustering_and_sustained_peaks(self):
        """Repeated sequential surges receive high reaction density and CHAOTIC_MOMENT or FUNNY_REACTION category."""
        # Simulated profile with 6 surges in 15 seconds (density ~ 0.20)
        profile = ClipAudioProfile(
            start_time=10.0,
            end_time=25.0,
            peak_rms=0.55,
            mean_rms=0.22,
            peak_z_score=3.5,
            local_contrast_peak=3.8,
            surge_count=6,
            reaction_density=0.20,
            has_speech_corroboration=True,
            audio_reaction_score=95.0,
            category=ReactionCategory.CHAOTIC_MOMENT
        )
        self.assertEqual(profile.category, ReactionCategory.CHAOTIC_MOMENT)
        self.assertGreaterEqual(profile.audio_reaction_score, 90.0)

    @patch("backend.app.services.storage_service.storage_service.load_stage_checkpoint")
    @patch("backend.app.services.storage_service.storage_service.save_stage_checkpoint")
    @patch("backend.app.services.storage_service.storage_service.init_project_workspace")
    def test_checkpoint_caching_and_reuse(self, mock_init, mock_save, mock_load):
        """Precomputed audio energy profiles are saved to and loaded from checkpoint."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            audio_file = tmppath / "audio.wav"
            self._create_synthetic_wav(audio_file, duration_sec=5.0)

            mock_init.return_value = {
                "audio": tmppath,
                "metadata": tmppath
            }
            # First run: no checkpoint
            mock_load.return_value = None

            res1 = self.svc.get_or_compute_project_energy("proj_cache_test", force_recompute=True)
            self.assertIn("stats", res1)
            self.assertEqual(mock_save.call_count, 1)

            # Second run: returns from in-memory cache directly without saving again
            res2 = self.svc.get_or_compute_project_energy("proj_cache_test", force_recompute=False)
            self.assertEqual(res1["stats"].duration_sec, res2["stats"].duration_sec)
            self.assertEqual(mock_save.call_count, 1)


if __name__ == "__main__":
    unittest.main()
