# Project Research Summary

**Project:** AI Video Clipper (ClipCraft / OpenClip)
**Domain:** Local-First AI Video Clipping, Transcription, Reframing & Captioning Pipeline
**Researched:** 2026-11-19
**Confidence:** HIGH

## Executive Summary

Building a free, local-first AI video clipping application requires orchestrating media ingestion, local speech-to-text transcription, AI highlight detection, video cutting, 9:16 vertical reframing, and burned-in captions without relying on expensive SaaS APIs.

The optimal approach is a decoupled architecture:
1. **Python + FastAPI Backend**: Manages background processing jobs, local disk caching, and coordinates native media and ML libraries.
2. **Native Local AI Engines**: `faster-whisper` (CTranslate2) for 4x faster speech recognition with word-level timestamps; Ollama (e.g. Llama 3.2, Mistral, Qwen 2.5) for semantic transcript analysis and candidate generation, paired with a deterministic fallback parser.
3. **Media Pipeline**: Native `FFmpeg` for exact keyframe cutting, audio extraction, and filtergraph caption burning; `OpenCV` with face detection and Exponential Moving Average (EMA) crop trajectory smoothing for vertical reframing.
4. **React + Vite Frontend**: Provides a clean local web interface with import workflows, real-time stage progress monitoring, candidate review, and clip export.

Key technical risks—such as Windows path escaping in FFmpeg filtergraphs, audio/video desync on stream-copied cuts, memory exhaustion on long videos, and malformed LLM outputs—have clear prevention strategies incorporated into our phase roadmap.

## Key Findings

### Recommended Stack

- **Backend**: Python 3.10-3.12, FastAPI, Uvicorn, Pydantic, httpx
- **Media**: FFmpeg (direct CLI subprocess with argument lists), yt-dlp
- **AI/ML**: `faster-whisper` (CPU int8 / CUDA float16), Ollama local API
- **Computer Vision**: `opencv-python-headless` (Haar Cascade / DNN face detection + EMA crop smoothing)
- **Frontend**: React 18/19, Vite, Tailwind CSS, Lucide React

### Expected Features

- **Table Stakes**: Local video file ingestion (MP4, MOV, MKV, WebM), authorized YouTube ingestion via yt-dlp, local transcription with timestamps, AI highlight discovery, exact cuts, 9:16 vertical reframing, synchronized burned captions, candidate review and export UI.
- **Differentiators**: 100% free and local-first (zero API keys), explainable candidate engagement scoring, smooth jitter-free face tracking, word-level caption highlighting, lightweight start/end trim editing, and stage caching for instant resumption.

### Critical Pitfalls & Mitigations

1. **Audio/Video Desync on Fast Cuts**: Mitigated by accurate seeks with re-encoding (`-ss -i -to` with libx264/aac).
2. **LLM Output Hallucination / Malformed JSON**: Mitigated by multi-step sanitization, Pydantic bounds checks, and deterministic fallback heuristics.
3. **Crop Jitter in Vertical Video**: Mitigated by frame sampling intervals and Exponential Moving Average (EMA) crop coordinate smoothing with safe center-crop fallback.
4. **Windows Path Escaping in Subtitle Filters**: Mitigated by forward-slash normalization and explicit colon escaping.

## Implications for Roadmap

The project should be built following a **Vertical MVP** approach across focused phases:

### Phase 1: Foundation, Project Workspace & Ingestion
- Set up project structure, FastAPI app, hardware capability detection, and project workspace manager (`projects/<id>/...`).
- Implement and test local video ingestion (probe metadata) and authorized YouTube ingestion via `yt-dlp`.

### Phase 2: Audio Extraction & Local Transcription Pipeline
- Implement 16kHz mono audio extraction via FFmpeg.
- Integrate `faster-whisper` with CPU/CUDA detection, word-level and segment-level timestamps, and persistent disk caching.

### Phase 3: AI Highlight Discovery & Explainable Scoring
- Implement transcript segmentation into semantic chunks.
- Build local LLM provider abstraction (Ollama client) with robust JSON sanitization and deterministic fallback.
- Implement multi-factor engagement scoring (hook, density, clarity, emotional resonance).

### Phase 4: Precision Video Clipping Engine
- Implement accurate FFmpeg clipping engine.
- Verify exact start/end cuts without black frames or audio drift.

### Phase 5: 9:16 Vertical Reframing & Face Tracking
- Implement OpenCV face detection and crop coordinate calculation.
- Apply Exponential Moving Average (EMA) trajectory smoothing.
- Generate stabilized 1080x1920 vertical video with center-crop fallback.

### Phase 6: Synchronized Vertical Captions
- Generate ASS / SRT captions with word timing and vertical safe-margin placement.
- Implement FFmpeg caption burning filtergraph.

### Phase 7: Local Web Interface & Review Dashboard
- Build modern React + Vite frontend (Import screen, Job Progress monitor, Candidate Review & Preview gallery, Clip Editor controls, and Export).
- Connect to backend API.

### Phase 8: End-to-End Pipeline Verification & Test Suite
- Comprehensive automated unit tests (segmentation, scoring, path escaping, validation).
- End-to-end integration test with synthetic test media verifying full pipeline from source to playable captioned 9:16 MP4.

### Phase 9: Documentation, Windows Startup & Git Preparation
- Complete README.md, .env.example, PowerShell start scripts (`start.ps1`), clean `.gitignore`, and Git initialization.

---
*Research completed: 2026-11-19*
*Ready for roadmap: yes*
