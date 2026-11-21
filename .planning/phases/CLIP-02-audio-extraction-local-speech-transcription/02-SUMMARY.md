---
phase: CLIP-02-audio-extraction-local-speech-transcription
plan: "01"
subsystem: audio-and-transcription
tags: [ffmpeg, faster-whisper, audio-extraction, speech-to-text, timestamps]

requires:
  - phase: CLIP-01-project-foundation-ingestion-engine
    provides: Ingested source video files and project directory workspaces
provides:
  - "FFmpeg 16kHz mono WAV audio extraction service"
  - "Local speech-to-text transcription engine (faster-whisper) with word-level timestamps"
  - "Persistent transcript caching and disk serialization (transcript.json)"
  - "API routes for audio transcription and transcript querying"
affects: [Phase 3 AI Highlight Detection, Phase 6 Synchronized Captioning]

tech-stack:
  added: [faster-whisper, ctranslate2]
  patterns:
    - "16kHz mono PCM normalization for speech recognition"
    - "Word-level timestamp extraction with confidence scores"
    - "Deterministic JSON caching to prevent re-transcription"

key-files:
  created:
    - backend/app/models/transcript.py
    - backend/app/services/audio_service.py
    - backend/app/services/transcription_service.py
    - backend/app/api/routes_transcription.py
    - tests/test_transcription.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Extract 16kHz mono audio as intermediate WAV for optimal Whisper accuracy"
  - "Capture both sentence-level segments and word-level timing"
  - "Provide deterministic fallback simulator for testing and offline development"

requirements-completed: [AUDIO-01, TRANS-01, TRANS-02, TRANS-03, TRANS-04]

duration: 15min
completed: 2026-11-19
---

# Phase 2: Audio Extraction & Local Speech Transcription Summary

**Delivered 16kHz mono WAV extraction via FFmpeg and local speech-to-text transcription with word-level timestamps using faster-whisper and persistent disk caching.**

## Accomplishments
1. **Audio Extraction**: `AudioService` extracts 16kHz mono 16-bit PCM WAV (`audio.wav`) from ingested videos using safe FFmpeg argument lists, normalizing the input for Whisper.
2. **Local Transcription Engine**: `TranscriptionService` leverages `faster-whisper` on CPU or CUDA to extract full text with segment-level and word-level timestamps (`WordTiming` and `TranscriptSegment`).
3. **Resumable Disk Caching**: Transcripts are automatically saved to `projects/<id>/transcript/transcript.json` and reused to prevent re-transcribing long source videos.
4. **API & Test Coverage**: Endpoints `/api/projects/{id}/transcribe` and `/api/projects/{id}/transcript` tested with unit tests for models, commands, and caching.
