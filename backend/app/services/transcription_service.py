"""Local speech-to-text transcription service powered by faster-whisper with stage caching."""

import json
from pathlib import Path
from typing import Optional, List

from backend.app.core.config import settings
from backend.app.core.hardware import detect_hardware
from backend.app.core.logger import logger
from backend.app.models.transcript import FullTranscript, TranscriptSegment, WordTiming
from backend.app.services.storage_service import storage_service
from backend.app.services.audio_service import audio_service


class TranscriptionService:
    """Manages local Whisper transcription with word timestamps and persistent caching."""

    def __init__(self):
        self._cached_model = None
        self._loaded_model_name = None

    def _get_whisper_model(self, model_size: str = "base"):
        """Initializes or reuses the faster-whisper model on CPU/CUDA."""
        if self._cached_model is not None and self._loaded_model_name == model_size:
            return self._cached_model

        try:
            from faster_whisper import WhisperModel  # type: ignore
        except ImportError:
            logger.warning("faster-whisper library is not installed in current environment.")
            return None

        caps = detect_hardware()
        device = caps["device"]
        compute_type = caps["compute_type"]

        logger.info(f"Loading faster-whisper model '{model_size}' on {device} ({compute_type})...")
        model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self._cached_model = model
        self._loaded_model_name = model_size
        return model

    def get_transcript_path(self, project_id: str) -> Path:
        """Returns the canonical transcript JSON file path for a project."""
        dirs = storage_service.init_project_workspace(project_id)
        return dirs["transcript"] / "transcript.json"

    def load_cached_transcript(self, project_id: str) -> Optional[FullTranscript]:
        """Loads transcript from disk cache if previously generated and valid."""
        t_path = self.get_transcript_path(project_id)
        if t_path.exists() and t_path.stat().st_size > 0:
            try:
                with open(t_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    logger.info(f"Loaded cached transcript for project '{project_id}' ({len(data.get('segments', []))} segments).")
                    return FullTranscript(**data)
            except Exception as e:
                logger.warning(f"Failed to read cached transcript for project '{project_id}': {e}")
        return None

    def transcribe_project(
        self,
        project_id: str,
        model_size: Optional[str] = None,
        force_recompute: bool = False
    ) -> FullTranscript:
        """
        Transcribes the project audio track into full transcript with word-level timestamps.
        Reuses cached transcript unless force_recompute is True.
        """
        model_name = model_size or settings.DEFAULT_WHISPER_MODEL

        # Check cache
        if not force_recompute:
            cached = self.load_cached_transcript(project_id)
            if cached:
                return cached

        # Ensure 16kHz audio exists
        audio_path = audio_service.extract_audio(project_id, force_recompute=force_recompute)

        model = self._get_whisper_model(model_name)

        if model is None:
            # Fallback simulator when faster-whisper is not installed (e.g. testing or minimal runtime)
            logger.info("Using deterministic fallback transcription simulator.")
            transcript = self._generate_simulated_transcript(project_id, model_name)
        else:
            logger.info(f"Starting faster-whisper transcription on '{audio_path}'...")
            segments_iter, info = model.transcribe(
                str(audio_path),
                word_timestamps=True,
                vad_filter=True,  # Voice activity detection to trim silence
            )

            formatted_segments: List[TranscriptSegment] = []
            full_text_parts: List[str] = []

            for seg_id, seg in enumerate(segments_iter):
                words: List[WordTiming] = []
                if seg.words:
                    for w in seg.words:
                        words.append(WordTiming(
                            word=w.word.strip(),
                            start=round(w.start, 2),
                            end=round(w.end, 2),
                            probability=round(w.probability, 2)
                        ))

                text = seg.text.strip()
                full_text_parts.append(text)

                formatted_segments.append(TranscriptSegment(
                    id=seg_id,
                    start=round(seg.start, 2),
                    end=round(seg.end, 2),
                    text=text,
                    words=words
                ))

            transcript = FullTranscript(
                project_id=project_id,
                language=info.language or "en",
                duration=round(info.duration, 2),
                full_text=" ".join(full_text_parts),
                segments=formatted_segments,
                model_name=model_name
            )

        # Persist to disk cache
        t_path = self.get_transcript_path(project_id)
        with open(t_path, "w", encoding="utf-8") as f:
            f.write(transcript.model_dump_json(indent=2))

        storage_service.save_stage_checkpoint(project_id, "transcription", {
            "transcript_path": str(t_path),
            "segment_count": len(transcript.segments),
            "duration": transcript.duration,
            "language": transcript.language
        })

        logger.info(f"Transcription saved to '{t_path}' ({len(transcript.segments)} segments, duration: {transcript.duration}s)")
        return transcript

    def _generate_simulated_transcript(self, project_id: str, model_name: str) -> FullTranscript:
        """Generates structured sample speech segments for testing when faster-whisper is not loaded."""
        sentences = [
            ("Welcome to this comprehensive tutorial on building AI applications.", 0.0, 4.5),
            ("In today's video, we are going to explore local-first video clipping and automated vertical reframing.", 4.8, 11.2),
            ("Here is the secret: you do not need expensive cloud APIs to get viral-worthy highlights.", 11.5, 17.8),
            ("By running Whisper locally and utilizing Ollama, your processing is 100% private and free.", 18.2, 25.0),
            ("Notice how the face tracking keeps the speaker perfectly centered in the 9:16 frame.", 25.5, 32.0),
            ("And finally, word-level synchronized captions make the content pop on Shorts and TikTok.", 32.5, 39.0),
            ("Make sure to like and subscribe for more open source engineering guides.", 39.5, 44.0),
        ]

        segments: List[TranscriptSegment] = []
        for idx, (text, start_sec, end_sec) in enumerate(sentences):
            words = []
            tokens = text.split()
            step = (end_sec - start_sec) / max(len(tokens), 1)
            for w_idx, token in enumerate(tokens):
                w_start = round(start_sec + w_idx * step, 2)
                w_end = round(w_start + step * 0.9, 2)
                words.append(WordTiming(word=token, start=w_start, end=w_end, probability=0.98))

            segments.append(TranscriptSegment(
                id=idx,
                start=start_sec,
                end=end_sec,
                text=text,
                words=words
            ))

        return FullTranscript(
            project_id=project_id,
            language="en",
            duration=45.0,
            full_text=" ".join(s[0] for s in sentences),
            segments=segments,
            model_name=f"{model_name}-simulated"
        )


transcription_service = TranscriptionService()
