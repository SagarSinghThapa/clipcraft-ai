# Stack Research

**Domain:** Local AI Video Clipping & Reframing Pipeline
**Researched:** 2026-11-19
**Confidence:** HIGH

## Recommended Stack

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| Python | 3.10 - 3.12 | Backend runtime | Premier ecosystem for ML/AI (PyTorch, CTranslate2, OpenCV) and cross-platform media automation |
| FastAPI | ^0.115.0 | Async Backend Web Framework | High throughput, async background task support, native Pydantic typing, SSE/WebSocket capabilities |
| Uvicorn | ^0.32.0 | ASGI Server | Production-grade ASGI server for async Python |
| React | ^19.0.0 (or 18.3) | Frontend Framework | Declarative component model, rich ecosystem for video players and real-time dashboard state |
| Vite | ^6.0.0 | Frontend Build Tool & Dev Server | Instant HMR, minimal config, fast builds, native ES modules |
| Tailwind CSS | ^3.4.0 | UI Styling | Rapid utility styling for responsive, clean vertical video previews and modern dark/light UI |
| FFmpeg | 6.0+ / 7.0+ | Media Processing Engine | The undisputed standard for low-level audio extraction, cutting, scaling, cropping, filtergraphs, and caption burning |
| yt-dlp | >=2024.11.0 | Authorized Media Ingestion | Actively maintained fork of youtube-dl with robust extraction, format sorting, and error reporting |
| faster-whisper | ^1.1.0 | Speech-to-Text Transcription | CTranslate2-accelerated Whisper implementation; 4x faster and 50% less RAM than openai-whisper with word-level timestamps |
| Ollama | >=0.4.0 | Local LLM Server | Free, local, private inference runtime for open weights (llama3.2, mistral, qwen2.5) with native Windows support |

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| OpenCV (`opencv-python-headless`) | ^4.10.0 | Computer Vision / Face Detection | Frame-by-frame face detection and bounding box tracking for smart 9:16 reframing |
| Pydantic | ^2.9.0 | Data Validation & Schemas | Validating API requests, LLM candidate JSON responses, and pipeline state objects |
| httpx | ^0.27.0 | Async HTTP Client | Calling Ollama HTTP endpoints (`/api/generate` or `/api/chat`) asynchronously |
| aiofiles | ^24.1.0 | Async File I/O | Non-blocking static file streaming for video previews |
| Lucide React | ^0.460.0 | UI Icons | Crisp, modern UI icons for media controls and status indicators |

### Development Tools

| Tool | Purpose | Notes |
|------|---------|-------|
| pytest & pytest-asyncio | Backend Automated Testing | Unit and integration testing for pipeline components, regex parsing, and API routes |
| Vitest | Frontend Testing | Fast Vite-native unit testing for frontend components |
| Ruff | Python Linter & Formatter | Extremely fast linting and formatting |

## Installation

```bash
# Backend (Python venv)
python -m venv venv
venv\Scripts\activate
pip install fastapi uvicorn pydantic httpx yt-dlp faster-whisper opencv-python-headless aiofiles pytest pytest-asyncio

# Frontend
cd frontend
npm install react react-dom lucide-react
npm install -D vite @vitejs/plugin-react tailwindcss postcss autoprefixer
```

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `faster-whisper` | `openai-whisper` | If CTranslate2 wheel binary fails to build on a specialized CPU architecture; otherwise `faster-whisper` is strictly superior |
| `faster-whisper` | `whisper.cpp` | In embedded C++ environments; Python bindings for faster-whisper are cleaner for FastAPI |
| Ollama local API | llama-cpp-python | If embedding the model directly into the Python process is strictly needed; Ollama provides better memory management and model swapping |
| OpenCV Haar/DNN | MediaPipe Face Detection | MediaPipe provides fine-grained landmarks, but `opencv-python-headless` has fewer dependency conflicts on Windows Python 3.12 |
| FFmpeg CLI subprocess | PyAV / MoviePy | MoviePy has memory leaks and slow re-encoding; direct FFmpeg subprocess is vastly faster and supports complex filtergraphs |

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| MoviePy | Bloated, notorious memory leaks on long videos, re-encodes through Python memory buffers | FFmpeg direct subprocess calls with argument lists |
| Paid Cloud APIs (OpenAI / Claude / AssemblyAI) | Violates the core zero-cost, local-first mandate | faster-whisper + Ollama |
| Electron / Tauri | Overcomplicates build pipeline for MVP; local web browser frontend (FastAPI + Vite) is lighter and easier to maintain | Local Web App (FastAPI serving Vite build or dev server) |
| Hardcoded Shell Strings (`shell=True`) | High vulnerability to command injection on filenames / URLs | `subprocess.run(["ffmpeg", ...], shell=False)` |

## Stack Patterns by Variant

**If NVIDIA GPU with CUDA is present:**
- `faster-whisper` automatically selects `device="cuda", compute_type="float16"`
- Ollama automatically offloads layers to GPU VRAM

**If CPU-only environment:**
- `faster-whisper` falls back smoothly to `device="cpu", compute_type="int8"`
- Ollama uses multi-threaded CPU quantization (e.g. `llama3.2:3b` or `qwen2.5:3b` which run at >20 tokens/sec on modern x86_64 CPUs)

## Version Compatibility

| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| Python 3.10 - 3.12 | faster-whisper 1.1.0 | Compatible with CTranslate2 prebuilt wheels for Windows |
| FastAPI 0.115 | Pydantic 2.9+ | Standard modern FastAPI setup |
| Node.js 18+ | Vite 6 | Fully compatible with Node 26.x present in environment |

## Sources

- faster-whisper GitHub repository & CTranslate2 documentation
- Ollama API specifications
- FFmpeg 6.0/7.0 documentation on filtergraphs, `drawtext`, `crop`, `subtitles`
- yt-dlp official documentation and best practices
