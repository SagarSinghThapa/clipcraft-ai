"""Reaction-aware audio energy analysis engine using dual-baseline sliding RMS and speech corroboration."""

import wave
import json
from pathlib import Path
from typing import Tuple, List, Dict, Any, Optional
import numpy as np

from backend.app.core.logger import logger
from backend.app.models.audio import (
    AudioEnergyWindow,
    GlobalAudioStats,
    ClipAudioProfile,
    ReactionCategory,
    calculate_audio_reaction_score
)
from backend.app.models.transcript import WordTiming
from backend.app.services.storage_service import storage_service
from backend.app.services.audio_service import audio_service
from backend.app.services.transcription_service import transcription_service


class AudioEnergyService:
    """High-performance sliding-window audio energy analysis and vocal reaction surge detection."""

    def __init__(self):
        # In-memory session cache: project_id -> cached_dict
        self._cache: Dict[str, Dict[str, Any]] = {}

    def calculate_rms_series(
        self,
        audio_path: Path,
        window_sec: float = 0.50,
        step_sec: float = 0.25
    ) -> Tuple[np.ndarray, np.ndarray, float]:
        """
        Calculates sliding-window RMS audio energy using double-precision cumulative sums
        over a 16kHz mono 16-bit PCM WAV in O(N) time.
        Returns: (rms_series, timestamps_sec, duration_sec)
        """
        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        with wave.open(str(audio_path), "rb") as wf:
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            sampwidth = wf.getsampwidth()
            n_channels = wf.getnchannels()

            if n_channels != 1 or sampwidth != 2:
                logger.warning(f"Audio file {audio_path.name} is {n_channels}ch {sampwidth*8}bit. Expected 1ch 16-bit PCM.")

            raw_frames = wf.readframes(n_frames)

        samples = np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32) / 32768.0
        duration_sec = float(len(samples) / framerate)

        win_size = int(round(window_sec * framerate))
        step = int(round(step_sec * framerate))

        if len(samples) < win_size:
            # Very short audio fallback
            rms_val = float(np.sqrt(np.mean(samples ** 2))) if len(samples) > 0 else 0.0
            return np.array([rms_val], dtype=np.float32), np.array([0.0], dtype=np.float32), duration_sec

        # O(N) Cumulative Sum Algorithm
        sq = (samples ** 2).astype(np.float64)
        cs = np.empty(len(sq) + 1, dtype=np.float64)
        cs[0] = 0.0
        np.cumsum(sq, out=cs[1:])

        indices = np.arange(0, len(samples) - win_size + 1, step)
        window_sums = cs[indices + win_size] - cs[indices]
        rms_series = np.sqrt(np.maximum(0.0, window_sums / win_size)).astype(np.float32)
        timestamps = (indices / framerate).astype(np.float32)

        return rms_series, timestamps, duration_sec

    def compute_global_stats(
        self,
        rms_series: np.ndarray,
        duration_sec: float,
        step_sec: float = 0.25
    ) -> GlobalAudioStats:
        """Computes track-wide baseline distribution metrics."""
        if len(rms_series) == 0:
            return GlobalAudioStats(
                duration_sec=duration_sec,
                mean_rms=0.0,
                std_rms=0.0,
                max_rms=0.0,
                median_rms=0.0,
                window_count=0,
                step_sec=step_sec
            )

        mean_val = float(np.mean(rms_series))
        std_val = float(np.std(rms_series))
        max_val = float(np.max(rms_series))
        median_val = float(np.median(rms_series))

        return GlobalAudioStats(
            duration_sec=round(duration_sec, 2),
            mean_rms=round(mean_val, 4),
            std_rms=round(std_val, 4),
            max_rms=round(max_val, 4),
            median_rms=round(median_val, 4),
            window_count=len(rms_series),
            step_sec=step_sec
        )

    def compute_local_baselines(
        self,
        rms_series: np.ndarray,
        step_sec: float = 0.25,
        neighborhood_sec: float = 10.0
    ) -> Tuple[np.ndarray, np.ndarray]:
        """
        Computes local baseline contrast (Delta_local) for every window relative to its
        surrounding neighborhood (+/- 5.0s, excluding the center 1.0s) in O(N) time.
        Returns: (mu_local, delta_local)
        """
        n = len(rms_series)
        if n == 0:
            return np.array([], dtype=np.float32), np.array([], dtype=np.float32)

        radius = int(round((neighborhood_sec / 2.0) / step_sec))  # e.g. 20 windows = 5s
        inner_gap = int(round(0.50 / step_sec))                   # 2 windows = 0.5s

        # Cumulative sums over rms_series for O(1) box queries
        cs_rms = np.empty(n + 1, dtype=np.float64)
        cs_rms[0] = 0.0
        np.cumsum(rms_series.astype(np.float64), out=cs_rms[1:])

        cs_sq = np.empty(n + 1, dtype=np.float64)
        cs_sq[0] = 0.0
        np.cumsum((rms_series.astype(np.float64) ** 2), out=cs_sq[1:])

        mu_local = np.empty(n, dtype=np.float32)
        std_local = np.empty(n, dtype=np.float32)

        for i in range(n):
            # Left neighborhood: [left_start, left_end)
            left_start = max(0, i - radius)
            left_end = max(0, i - inner_gap)

            # Right neighborhood: [right_start, right_end)
            right_start = min(n, i + inner_gap + 1)
            right_end = min(n, i + radius + 1)

            count_left = left_end - left_start
            count_right = right_end - right_start
            total_count = count_left + count_right

            if total_count > 0:
                sum_val = (cs_rms[left_end] - cs_rms[left_start]) + (cs_rms[right_end] - cs_rms[right_start])
                sum_sq = (cs_sq[left_end] - cs_sq[left_start]) + (cs_sq[right_end] - cs_sq[right_start])
                mean_l = sum_val / total_count
                var_l = max(0.0, (sum_sq / total_count) - (mean_l ** 2))
                std_l = float(np.sqrt(var_l))
            else:
                mean_l = float(rms_series[i])
                std_l = 0.01

            mu_local[i] = mean_l
            std_local[i] = max(0.01, std_l)

        delta_local = ((rms_series - mu_local) / std_local).astype(np.float32)
        return mu_local, delta_local

    def corroborate_speech(
        self,
        surge_timestamps: List[float],
        word_timings: List[WordTiming],
        tolerance_sec: float = 1.0
    ) -> Dict[float, bool]:
        """
        Cross-references audio volume surge timestamps with Whisper word intervals.
        Returns a dict mapping timestamp -> bool indicating whether speech occurred nearby.
        """
        result = {}
        for t in surge_timestamps:
            has_word = any(
                (w.start - tolerance_sec) <= t <= (w.end + tolerance_sec)
                for w in word_timings
            )
            result[t] = has_word
        return result

    def extract_clip_profile(
        self,
        rms_series: np.ndarray,
        timestamps: np.ndarray,
        global_stats: GlobalAudioStats,
        delta_local: np.ndarray,
        start_sec: float,
        end_sec: float,
        word_timings: Optional[List[WordTiming]] = None
    ) -> ClipAudioProfile:
        """
        Extracts comprehensive dual-baseline reaction metrics and bounded 0-100 score
        for a candidate highlight segment [start_sec, end_sec].
        """
        mask = (timestamps >= start_sec) & (timestamps <= end_sec)
        clip_rms = rms_series[mask]
        clip_delta = delta_local[mask]
        clip_ts = timestamps[mask]

        if len(clip_rms) == 0:
            return ClipAudioProfile(
                start_time=start_sec,
                end_time=end_sec,
                peak_rms=0.0,
                mean_rms=0.0,
                peak_z_score=0.0,
                local_contrast_peak=0.0,
                surge_count=0,
                reaction_density=0.0,
                has_speech_corroboration=True,
                audio_reaction_score=50.0,
                category=ReactionCategory.GENERAL_HIGHLIGHT
            )

        peak_rms = float(np.max(clip_rms))
        mean_rms = float(np.mean(clip_rms))

        std_guard = max(0.001, global_stats.std_rms)
        z_scores = (clip_rms - global_stats.mean_rms) / std_guard
        peak_z = float(np.max(z_scores))
        local_contrast_peak = float(np.max(clip_delta))

        # Surge windows: Z_global >= 2.0 AND delta_local >= 2.0 (or extreme peak_z >= 2.5)
        surge_mask = (z_scores >= 2.0) & (clip_delta >= 2.0) | (z_scores >= 2.5)
        surge_count = int(np.sum(surge_mask))
        reaction_density = float(surge_count / max(1, len(clip_rms)))

        # Speech corroboration check
        has_speech = True
        if word_timings is not None and surge_count > 0:
            surge_times = [float(clip_ts[idx]) for idx in np.where(surge_mask)[0]]
            speech_map = self.corroborate_speech(surge_times, word_timings, tolerance_sec=1.0)
            has_speech = any(speech_map.values()) if speech_map else False

        # Calculate bounded 0-100 audio reaction score
        audio_score = calculate_audio_reaction_score(
            peak_z=peak_z,
            local_contrast=local_contrast_peak,
            density=reaction_density,
            speech_confirmed=has_speech
        )

        # Categorize reaction typology
        category = ReactionCategory.GENERAL_HIGHLIGHT
        if has_speech:
            if peak_z >= 3.0 and reaction_density >= 0.12:
                category = ReactionCategory.RAGE if local_contrast_peak >= 3.0 else ReactionCategory.FUNNY_REACTION
            elif local_contrast_peak >= 3.2 and surge_count <= 3:
                category = ReactionCategory.SURPRISE
            elif surge_count >= 5:
                category = ReactionCategory.CHAOTIC_MOMENT
            elif peak_z >= 2.2:
                category = ReactionCategory.FUNNY_REACTION
        else:
            if peak_z >= 2.5:
                category = ReactionCategory.CHAOTIC_MOMENT

        return ClipAudioProfile(
            start_time=round(start_sec, 2),
            end_time=round(end_sec, 2),
            peak_rms=round(peak_rms, 4),
            mean_rms=round(mean_rms, 4),
            peak_z_score=round(peak_z, 2),
            local_contrast_peak=round(local_contrast_peak, 2),
            surge_count=surge_count,
            reaction_density=round(reaction_density, 3),
            has_speech_corroboration=has_speech,
            audio_reaction_score=audio_score,
            category=category
        )

    def get_or_compute_project_energy(
        self,
        project_id: str,
        force_recompute: bool = False
    ) -> Dict[str, Any]:
        """
        Returns full audio energy analysis for project, reusing in-memory cache
        or disk checkpoint metadata/checkpoint_audio_energy.json when available.
        """
        if project_id in self._cache and not force_recompute:
            return self._cache[project_id]

        dirs = storage_service.init_project_workspace(project_id)
        audio_path = dirs["audio"] / "audio.wav"
        if not audio_path.exists():
            # Trigger audio extraction
            audio_path = audio_service.extract_audio(project_id, force_recompute=force_recompute)

        checkpoint_data = storage_service.load_stage_checkpoint(project_id, "audio_energy")
        rms_series: Optional[np.ndarray] = None
        timestamps: Optional[np.ndarray] = None
        local_contrast: Optional[np.ndarray] = None

        if checkpoint_data and not force_recompute:
            try:
                stats = GlobalAudioStats(**checkpoint_data["stats"])
                rms_series = np.array(checkpoint_data["rms_series"], dtype=np.float32)
                timestamps = np.array(checkpoint_data["timestamps"], dtype=np.float32)
                local_contrast = np.array(checkpoint_data["local_contrast"], dtype=np.float32)

                res = {
                    "stats": stats,
                    "rms_series": rms_series,
                    "timestamps": timestamps,
                    "local_contrast": local_contrast,
                    "surge_windows": checkpoint_data.get("surge_windows", [])
                }
                self._cache[project_id] = res
                logger.info(f"Loaded cached audio energy profile for project '{project_id}' ({stats.window_count} windows).")
                return res
            except Exception as e:
                logger.warning(f"Failed to load cached audio energy checkpoint: {e}. Recomputing...")

        logger.info(f"Computing dual-baseline audio energy series for project '{project_id}'...")
        rms_series, timestamps, duration = self.calculate_rms_series(audio_path)
        stats = self.compute_global_stats(rms_series, duration)
        _, local_contrast = self.compute_local_baselines(rms_series)

        # Detect surge window intervals (Z_global >= 2.0 and local_contrast >= 2.0)
        surge_mask = (rms_series - stats.mean_rms) / max(0.001, stats.std_rms) >= 2.0
        surge_mask = surge_mask & (local_contrast >= 2.0)
        surge_indices = np.where(surge_mask)[0]
        surge_windows = [float(timestamps[idx]) for idx in surge_indices]

        # Save checkpoint to disk (storing downsampled points if huge to preserve disk)
        storage_service.save_stage_checkpoint(project_id, "audio_energy", {
            "stats": stats.model_dump(),
            "rms_series": rms_series.tolist(),
            "timestamps": timestamps.tolist(),
            "local_contrast": local_contrast.tolist(),
            "surge_windows": surge_windows
        })

        res = {
            "stats": stats,
            "rms_series": rms_series,
            "timestamps": timestamps,
            "local_contrast": local_contrast,
            "surge_windows": surge_windows
        }
        self._cache[project_id] = res
        logger.info(f"Audio energy profile computed: {stats.window_count} windows, mean RMS={stats.mean_rms}, surges={len(surge_windows)}")
        return res

    def analyze_project_audio_energy(
        self,
        project_id: str,
        whisper_words: Optional[List[WordTiming]] = None,
        force_recompute: bool = False
    ) -> Dict[str, Any]:
        """Convenience alias for get_or_compute_project_energy."""
        return self.get_or_compute_project_energy(project_id, force_recompute=force_recompute)

    def get_clip_audio_profile(
        self,
        project_id: str,
        start_sec: float,
        end_sec: float,
        word_timings: Optional[List[WordTiming]] = None
    ) -> ClipAudioProfile:
        """Retrieves ClipAudioProfile for a candidate window from cached project audio energy."""
        try:
            energy_data = self.get_or_compute_project_energy(project_id)
            return self.extract_clip_profile(
                rms_series=energy_data["rms_series"],
                timestamps=energy_data["timestamps"],
                global_stats=energy_data["stats"],
                delta_local=energy_data["local_contrast"],
                start_sec=start_sec,
                end_sec=end_sec,
                word_timings=word_timings
            )
        except Exception as e:
            logger.warning(f"Could not compute clip audio profile for {project_id} [{start_sec}-{end_sec}]: {e}")
            return ClipAudioProfile(
                start_time=start_sec,
                end_time=end_sec,
                peak_rms=0.0,
                mean_rms=0.0,
                peak_z_score=0.0,
                local_contrast_peak=0.0,
                surge_count=0,
                reaction_density=0.0,
                has_speech_corroboration=True,
                audio_reaction_score=50.0,
                category=ReactionCategory.GENERAL_HIGHLIGHT
            )


audio_energy_service = AudioEnergyService()
