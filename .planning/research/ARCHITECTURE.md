# Architecture Research

**Domain:** Local AI Video Clipper Application
**Researched:** 2026-11-19
**Confidence:** HIGH

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    Web Frontend (React + Vite)              │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Import View  │  │ Status View  │  │ Clip Results View │  │
│  └──────┬───────┘  └──────┬───────┘  └─────────┬─────────┘  │
└─────────┼─────────────────┼────────────────────┼────────────┘
          │ REST API        │ SSE / Polling      │ Static Stream
┌─────────┴─────────────────┴────────────────────┴────────────┐
│                    FastAPI Backend Server                   │
├─────────────────────────────────────────────────────────────┤
│  API Routes (`/api/projects`, `/api/jobs`, `/api/clips`)   │
├─────────────────────────────────────────────────────────────┤
│  Pipeline Engine & Task Coordinator                         │
│  ┌───────────────┐ ┌────────────────┐ ┌──────────────────┐  │
│  │ Ingestion Svc │ │ Transcribe Svc │ │ Analysis & Score │  │
│  └───────┬───────┘ └───────┬────────┘ └────────┬─────────┘  │
│  ┌───────┴───────┐ ┌───────┴────────┐ ┌────────┴─────────┐  │
│  │ Clipping Svc  │ │ Reframe Svc    │ │ Captioning Svc   │  │
│  └───────────────┘ └────────────────┘ └──────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│  Storage Layer (`projects/<id>/...` + JSON/SQLite metadata) │
└─────────────────────────────────────────────────────────────┘
          │ Subprocess / HTTP
┌─────────┴───────────────────────────────────────────────────┐
│              Underlying Native Runtimes & Engines           │
│  ┌───────────────┐ ┌────────────────┐ ┌──────────────────┐  │
│  │    FFmpeg     │ │ faster-whisper │ │  Ollama Local    │  │
│  └───────────────┘ └────────────────┘ └──────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Typical Implementation |
|-----------|----------------|------------------------|
| `api/` | Exposes REST endpoints for project creation, job execution, status querying, clip adjustments, and media delivery | FastAPI routers with Pydantic request/response schemas |
| `ingestion/` | Validates local files, downloads authorized YouTube videos via `yt-dlp`, runs `ffprobe` for metadata | Subprocess calls with strict path validation |
| `transcription/` | Extracts 16kHz WAV audio, feeds to `faster-whisper`, formats word and segment timestamps, manages disk cache | `faster-whisper.WhisperModel` running on CPU or CUDA |
| `analysis/` | Segments transcript, prompts Ollama (or local LLM provider), enforces schema validation, falls back to deterministic regex parser | Pydantic JSON validation + httpx client |
| `scoring/` | Evaluates candidates against multi-factor scoring rubric (hook, density, clarity, emotional resonance) | Pure Python scoring module |
| `clipping/` | Cuts video at precise timestamps using FFmpeg accurate seek (`-ss` before `-i`, keyframe re-encode) | FFmpeg CLI subprocess |
| `reframing/` | Computes 9:16 crop window (1080x1920), detects speaker face using OpenCV, applies Exponential Moving Average (EMA) smoothing | OpenCV frame sampling + FFmpeg `crop` filter |
| `captions/` | Chunks transcript words into short vertical subtitle phrases, formats ASS/SRT subtitles with custom styling, burns via FFmpeg | Subtitle generator + FFmpeg filtergraph |
| `storage/` | Manages project workspace directories and state checkpoints | Local filesystem manager |

## Recommended Project Structure

```
clipping/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes_projects.py
│   │   │   ├── routes_jobs.py
│   │   │   └── routes_clips.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── hardware.py
│   │   │   └── logger.py
│   │   ├── services/
│   │   │   ├── ingestion_service.py
│   │   │   ├── transcription_service.py
│   │   │   ├── analysis_service.py
│   │   │   ├── scoring_service.py
│   │   │   ├── clipping_service.py
│   │   │   ├── reframing_service.py
│   │   │   ├── caption_service.py
│   │   │   └── pipeline_coordinator.py
│   │   ├── models/
│   │   │   ├── project.py
│   │   │   ├── transcript.py
│   │   │   ├── candidate.py
│   │   │   └── job.py
│   │   ├── utils/
│   │   │   ├── ffmpeg_utils.py
│   │   │   └── path_utils.py
│   │   └── main.py
│   ├── tests/
│   │   ├── test_ingestion.py
│   │   ├── test_transcription.py
│   │   ├── test_analysis.py
│   │   ├── test_scoring.py
│   │   ├── test_clipping.py
│   │   ├── test_reframing.py
│   │   ├── test_captions.py
│   │   └── test_api.py
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ImportCard.tsx
│   │   │   ├── JobProgress.tsx
│   │   │   ├── CandidateCard.tsx
│   │   │   ├── VideoPlayer.tsx
│   │   │   └── ClipEditorModal.tsx
│   │   ├── pages/
│   │   │   └── Dashboard.tsx
│   │   ├── services/
│   │   │   └── api.ts
│   │   ├── types/
│   │   │   └── index.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   ├── package.json
│   ├── vite.config.ts
│   └── tailwind.config.js
├── projects/              # Structured runtime storage (gitignored)
├── docs/                  # Architecture & User Guides
├── scripts/
│   ├── start.ps1          # Windows startup script
│   └── run_tests.ps1      # Test runner script
├── README.md
├── .gitignore
└── .env.example
```

## Architectural Patterns

### Pattern 1: Resumable Stage Checkpointing

Each stage produces a persistent disk artifact:
1. `projects/<id>/source/original.mp4`
2. `projects/<id>/audio/audio.wav`
3. `projects/<id>/transcript/transcript.json`
4. `projects/<id>/analysis/candidates.json`
5. `projects/<id>/clips/<clip_id>/raw_clip.mp4`
6. `projects/<id>/clips/<clip_id>/reframed.mp4`
7. `projects/<id>/clips/<clip_id>/final_clip.mp4`

If any step fails or is restarted, the pipeline checks for existing valid checkpoint files and skips redundant expensive compute.

### Pattern 2: Exponential Moving Average (EMA) Reframing Smoothing

When tracking a face across frames, sudden camera pans or detection flickers can cause nausea-inducing crop jitter:

```python
# Crop smoothing:
target_x = face_center_x - (crop_width / 2)
# Clamp within video boundaries:
target_x = max(0, min(video_width - crop_width, target_x))
# Smooth with alpha factor (e.g. 0.15):
smoothed_x = alpha * target_x + (1 - alpha) * previous_x
```

### Pattern 3: Deterministic LLM Response Parsing

LLMs may return markdown code blocks (````json ... ````), conversational preamble, or slightly truncated JSON. The parser tries:
1. Direct `json.loads(text)`
2. Markdown code block extraction (`r"```(?:json)?\s*(\{.*?\})\s*```"`)
3. Bracket boundary search (`text[first_bracket:last_bracket+1]`)
4. Deterministic regex field extraction fallback if JSON parsing completely fails.

## Data Flow

```
[User submits File or URL]
        ↓
FastAPI creates Project & Job record
        ↓
Job background task executes Pipeline Stages:
1. Ingest (Save file or run yt-dlp)
2. Extract Audio (FFmpeg -> 16kHz mono WAV)
3. Transcribe (faster-whisper -> word/segment timings -> transcript.json)
4. Segment & Prompt (Ollama / Local LLM)
5. Parse & Score Candidates (candidates.json)
6. For each chosen candidate:
   a. Cut subclip (FFmpeg -> raw_clip.mp4)
   b. Detect face trajectory & compute crop (OpenCV)
   c. Reframe 9:16 (FFmpeg crop -> reframed.mp4)
   d. Generate synchronized subtitle file (ASS/SRT)
   e. Burn captions into video (FFmpeg -> final_clip.mp4)
        ↓
Job marked COMPLETED
        ↓
Frontend polls or receives SSE update, displays candidates in interactive gallery
```

## Anti-Patterns Avoided

- **No Synchronous Heavy Processing in API Threads**: All media processing runs in background workers or async tasks.
- **No In-Memory Video Processing**: FFmpeg operates directly on disk files with streaming pipes where appropriate, avoiding Python RAM bloat.
- **No Unsanitized Subprocess Invocations**: Arguments are passed strictly as lists (`subprocess.run(["ffmpeg", "-i", input_path, ...])`), never concatenated into raw shell strings.
