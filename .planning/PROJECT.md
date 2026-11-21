# AI Video Clipper (ClipCraft / OpenClip)

## What This Is

A local-first, free, and open-source AI video clipping application that transforms long-form videos (local video files or authorized YouTube URLs) into high-impact 9:16 vertical short-form clips. It executes an automated pipeline spanning audio extraction, local transcription with timestamps, transcript segmentation, AI highlight detection, candidate scoring, speaker-aware vertical reframing, and burned-in synchronized captions, previewable and exportable via a modern web interface without requiring paid AI APIs.

## Core Value

Generate high-quality, engaging 9:16 vertical short-form video clips with synchronized animated captions from long-form video completely locally and free of paid external APIs.

## Current State

**Milestone v2.0 (Gaming & Streamer Vertical Reframing Engine) Shipped:** 2026-11-20  
Stacked vertical gaming composition (Top: Streamer Facecam / Bottom: Gameplay) with persistent webcam detection, aspect-preserving `FIT_WITH_BLUR` widescreen gameplay framing, stream chat overlay exclusion, word-level animated karaoke captions with active gold pop at seam safe zones, multimodal reaction detection (dual-baseline audio RMS, speech corroboration, facecam/gameplay visual differencing, causal sequence micro-narrative expansion), and interactive web review controls. Fully verified on real 35-minute GTA VI / IShowSpeed stream (`proj_40b4d189bb59`) with zero decode errors and 84/84 passing automated regression tests.

**Milestone v1.0 (MVP) Shipped:** 2026-11-19  
Full end-to-end local-first pipeline verified with real media on YouTube video `https://youtu.be/kR8bhkVAgBY` (35 minutes, 1080x1920 9:16 export with burned captions).

## Next Milestone Goals

**Milestone v3.0:** To be scoped and planned.  
Potential focus areas:
- Multi-speaker conversational framing and podcast split-screen.
- B-roll overlay insertion and visual engagement hooks.
- Background worker task queue (Celery/Redis or lightweight local job queue).
- Direct social platform export integrations.

## Requirements

### Validated Requirements

- **Milestone v1.0 (32/32 Shipped):** See full archive [.planning/milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)
  - Ingestion: `INGEST-01`, `INGEST-02`, `INGEST-03`
  - Audio: `AUDIO-01`, `AUDIO-02`
  - Transcription: `TRANS-01`, `TRANS-02`, `TRANS-03`, `TRANS-04`
  - AI Highlight Discovery: `AI-01`, `AI-02`, `AI-03`, `AI-04`
  - Scoring: `SCORE-01`, `SCORE-02`
  - Precision Clipping: `CLIP-01`, `CLIP-02`, `CLIP-03`
  - 9:16 Vertical Reframing: `REFRAME-01`, `REFRAME-02`, `REFRAME-03`, `REFRAME-04`
  - Synchronized Captions: `CAPTION-01`, `CAPTION-02`, `CAPTION-03`, `CAPTION-04`
  - Web Interface: `UI-01`, `UI-02`, `UI-03`, `UI-04`
  - System & Windows: `SYS-01`, `SYS-02`, `SYS-03`, `SYS-04`

- **Milestone v2.0 (17/17 Shipped):** See full archive [.planning/milestones/v2.0-REQUIREMENTS.md](milestones/v2.0-REQUIREMENTS.md)
  - Facecam Detection: `FACE-01`, `FACE-02`, `FACE-03`
  - Gameplay Cropping: `GAME-01`, `GAME-02`
  - Layout & Composition: `LAYOUT-01`, `LAYOUT-02`, `LAYOUT-03`, `LAYOUT-04`
  - Export Resolutions: `EXPORT-01`
  - Animated Karaoke: `CAPTION-01`, `CAPTION-02`, `CAPTION-03`
  - Reaction Scoring: `SCORE-01`, `SCORE-02`
  - UI Controls: `UI-01`, `UI-02`

### Out of Scope

- Cloud subscription services, cloud SaaS hosting, or mandatory paid third-party APIs (OpenAI, Anthropic, cloud GPUs) — application is strictly local-first and free.
- Bypassing DRM, paywalls, private videos, age-gated authentication, or platform security mechanisms — out of ethical and legal boundaries.
- Full professional Non-Linear Video Editor (NLE) timeline with multi-track multi-layer video effects — lightweight trimming/title editing is sufficient for MVP.
- Complex multi-speaker dynamic splitscreen compositing in initial MVP — speaker-aware crop and center-crop fallback are prioritized for stability.
- Claiming virality prediction guarantees — scores represent estimated short-form structural engagement quality.

## Context

- Operating System: Windows 10/11 environment.
- Media Processing: FFmpeg is central for extraction, cutting, scaling, cropping, caption burning, and audio mixing.
- AI Models: Whisper / faster-whisper for transcription; Ollama (e.g., llama3.2, mistral, qwen2.5, phi3) or local heuristics for highlight analysis.
- UI: Modern reactive frontend (React / Vite / Tailwind) communicating with a Python FastAPI backend over REST and static media serving.
- Modular code architecture ensuring each stage (ingestion, transcription, analysis, clipping, reframing, captions, rendering) is decoupled, testable, and reusable.

## Constraints

- **Local-First & Free**: Must run completely locally without paid API keys.
- **Hardware Agnostic**: Must function reliably on CPU-only machines while automatically leveraging NVIDIA CUDA when available.
- **Robust Error Handling**: Handle missing external tools (FFmpeg, Ollama), network dropouts during YouTube downloads, or malformed LLM outputs deterministically.
- **Windows Friendly**: Must avoid Linux-specific bash assumptions; paths must handle Windows separators correctly, and startup scripts must support PowerShell.

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Python + FastAPI for backend | Dominant ecosystem for AI/ML (faster-whisper, OpenCV, PyTorch) and high-performance async API | Validated |
| React + Vite + Tailwind for frontend | Modern, reactive, lightweight, fast build times, and great video player integration | Validated |
| faster-whisper for transcription | 4x faster than original OpenAI whisper with significantly lower memory footprint via CTranslate2 | Validated |
| Ollama + deterministic JSON fallback for LLM | Free, local, private, widely adopted on Windows; regex/heuristic fallback protects against malformed outputs | Validated |
| OpenCV Haar/DNN for face detection | Local, fast, lightweight face/head detection suitable for video frame sampling without giant model downloads | Validated |
| Filtergraph burned-in captions via FFmpeg (drawtext / subtitles / ass) | Zero external rendering engine overhead; produces universal standard MP4 files | Validated |
| Spatial persistence clustering for facecam | Discovers webcam region from coarse frame sampling without GPU overhead, ignoring transient cutscenes | Validated |
| `FIT_WITH_BLUR` gameplay composition | Preserves 100% widescreen gameplay field-of-view over ambient blurred backdrop without distortion | Validated |
| Horizontal clamping ($X \le 1700\text{px}$) | Completely cuts out native stream chat/comment overlays from source video | Validated |
| ASS word-level karaoke animations | Gold active word illumination with 112% pop bounce anchored to split seam safe zone | Validated |
| Multimodal reaction scoring | Fuses audio energy surges, speech corroboration penalties, visual motion differencing, and causal story expansion | Validated |
| Non-destructive re-rendering | Allows fine-tuning layouts, captions, and resolutions without re-running expensive upstream stages | Validated |

---
*Last updated: 2026-11-20 upon Milestone v2.0 completion*
