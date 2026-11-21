"""Causal sequence framing service structuring clips into Setup -> Event -> Reaction -> Payoff."""

from typing import Tuple, List, Optional
from backend.app.core.logger import logger
from backend.app.models.transcript import FullTranscript, TranscriptSegment


class CausalSequenceService:
    """Expands reaction peaks into narrative causal sequences with strict duration bounds and sentence boundary snapping."""

    def identify_reaction_hotspots(
        self,
        surge_timestamps: List[float],
        min_gap_sec: float = 12.0
    ) -> List[float]:
        """
        Clusters nearby audio volume surge timestamps into distinct reaction hotspot moments,
        selecting the most representative timestamp for each cluster.
        """
        if not surge_timestamps:
            return []

        sorted_ts = sorted(surge_timestamps)
        clusters: List[List[float]] = []
        current_cluster = [sorted_ts[0]]

        for t in sorted_ts[1:]:
            if t - current_cluster[-1] <= min_gap_sec:
                current_cluster.append(t)
            else:
                clusters.append(current_cluster)
                current_cluster = [t]
        if current_cluster:
            clusters.append(current_cluster)

        # Pick the median timestamp of each cluster
        hotspots = []
        for cluster in clusters:
            n = len(cluster)
            if n % 2 == 1:
                hotspots.append(cluster[n // 2])
            else:
                hotspots.append((cluster[n // 2 - 1] + cluster[n // 2]) / 2.0)
        return hotspots

    def snap_to_sentence_endpoints(
        self,
        transcript: FullTranscript,
        target_time: float,
        prefer_start: bool = True,
        max_drift_sec: float = 4.0
    ) -> float:
        """
        Finds the nearest Whisper sentence endpoint to target_time within max_drift_sec.
        If prefer_start is True, prefers the start of a segment; else prefers the end.
        """
        if not transcript.segments:
            return target_time

        candidates: List[float] = []
        for seg in transcript.segments:
            candidates.append(seg.start if prefer_start else seg.end)

        candidates.sort(key=lambda t: abs(t - target_time))
        best = candidates[0]
        if abs(best - target_time) <= max_drift_sec:
            return best
        return target_time

    def expand_causal_window(
        self,
        peak_time: float,
        transcript: FullTranscript,
        min_duration: float = 20.0,
        pref_duration: float = 35.0,
        max_duration: float = 60.0,
        video_duration: Optional[float] = None
    ) -> Tuple[float, float]:
        """
        Expands around a reaction peak into:
        SETUP (T - 8..12s) -> GAMEPLAY EVENT -> STREAMER REACTION (T) -> PAYOFF (T + 12..18s).
        Enforces min_duration <= duration <= max_duration while snapping to sentence boundaries.
        """
        # Desired proportions: ~35% setup before peak, ~65% reaction & payoff after peak
        raw_setup_sec = max(6.0, min(14.0, pref_duration * 0.35))
        raw_payoff_sec = pref_duration - raw_setup_sec

        target_start = max(0.0, peak_time - raw_setup_sec)
        target_end = peak_time + raw_payoff_sec
        if video_duration is not None:
            target_end = min(video_duration, target_end)

        # Snap to sentence endpoints
        snapped_start = self.snap_to_sentence_endpoints(transcript, target_start, prefer_start=True, max_drift_sec=4.0)
        snapped_end = self.snap_to_sentence_endpoints(transcript, target_end, prefer_start=False, max_drift_sec=5.0)

        # Enforce hard duration constraints
        duration = snapped_end - snapped_start

        # Case 1: Duration too short (< min_duration)
        if duration < min_duration:
            deficit = min_duration - duration
            # Expand backward first if possible
            expand_back = min(deficit / 2.0, snapped_start)
            snapped_start = max(0.0, snapped_start - expand_back)
            snapped_end = snapped_start + min_duration
            if video_duration is not None and snapped_end > video_duration:
                snapped_end = video_duration
                snapped_start = max(0.0, snapped_end - min_duration)

            # Re-snap gently
            snapped_start = self.snap_to_sentence_endpoints(transcript, snapped_start, prefer_start=True, max_drift_sec=2.0)
            snapped_end = self.snap_to_sentence_endpoints(transcript, snapped_end, prefer_start=False, max_drift_sec=2.0)

        # Case 2: Duration too long (> max_duration)
        duration = snapped_end - snapped_start
        if duration > max_duration:
            excess = duration - max_duration
            # Trim from whichever edge is furthest from the peak
            dist_to_start = peak_time - snapped_start
            dist_to_end = snapped_end - peak_time

            if dist_to_start > 14.0:
                snapped_start = peak_time - 12.0
            if snapped_end - snapped_start > max_duration:
                snapped_end = snapped_start + max_duration

        final_duration = snapped_end - snapped_start
        if final_duration < min_duration:
            # Absolute hard clamp to guarantee requirement
            snapped_end = snapped_start + min_duration
            if video_duration is not None and snapped_end > video_duration:
                snapped_end = video_duration
                snapped_start = max(0.0, snapped_end - min_duration)

        logger.info(f"Causal window framed around peak T={round(peak_time, 2)}s: [{round(snapped_start, 2)}s -> {round(snapped_end, 2)}s] ({round(snapped_end - snapped_start, 2)}s)")
        return round(snapped_start, 2), round(snapped_end, 2)


causal_sequence_service = CausalSequenceService()
