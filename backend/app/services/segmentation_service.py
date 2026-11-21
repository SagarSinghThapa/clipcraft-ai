"""Transcript segmentation service respecting sentence boundaries."""

from typing import List, Dict, Any
from backend.app.models.transcript import FullTranscript, TranscriptSegment


class SegmentationService:
    """Chunks full speech transcripts into coherent semantic windows for LLM analysis."""

    def create_analysis_windows(
        self,
        transcript: FullTranscript,
        min_window_duration: float = 30.0,
        max_window_duration: float = 90.0,
        overlap_seconds: float = 10.0
    ) -> List[Dict[str, Any]]:
        """
        Groups transcript segments into overlapping windows strictly aligned with
        sentence segment boundaries. Never cuts sentences in half.
        """
        segments = transcript.segments
        if not segments:
            return []

        windows: List[Dict[str, Any]] = []
        n_segments = len(segments)
        start_idx = 0

        while start_idx < n_segments:
            window_segments: List[TranscriptSegment] = []
            window_start = segments[start_idx].start
            window_text_parts: List[str] = []

            curr_idx = start_idx
            while curr_idx < n_segments:
                seg = segments[curr_idx]
                curr_duration = seg.end - window_start

                window_segments.append(seg)
                window_text_parts.append(seg.text)

                # If reached max window duration, complete this window
                if curr_duration >= max_window_duration:
                    break

                curr_idx += 1

            window_end = window_segments[-1].end
            duration = round(window_end - window_start, 2)

            # Record window
            windows.append({
                "window_index": len(windows),
                "start_time": round(window_start, 2),
                "end_time": round(window_end, 2),
                "duration": duration,
                "text": " ".join(window_text_parts),
                "segments": window_segments
            })

            # Advance with overlap
            # Find next start_idx such that next start is >= window_end - overlap_seconds
            target_next_start = window_end - overlap_seconds
            next_start_idx = start_idx + 1
            while next_start_idx < n_segments and segments[next_start_idx].start < target_next_start:
                next_start_idx += 1

            if next_start_idx <= start_idx:
                next_start_idx = start_idx + 1

            start_idx = next_start_idx

        return windows

    def find_nearest_sentence_boundary(
        self,
        transcript: FullTranscript,
        timestamp: float,
        prefer_start: bool = True
    ) -> float:
        """Snaps an arbitrary timestamp to the nearest sentence boundary in the transcript."""
        if not transcript.segments:
            return timestamp

        best_time = timestamp
        min_diff = float("inf")

        for seg in transcript.segments:
            candidate = seg.start if prefer_start else seg.end
            diff = abs(candidate - timestamp)
            if diff < min_diff:
                min_diff = diff
                best_time = candidate

        return round(best_time, 2)


segmentation_service = SegmentationService()
