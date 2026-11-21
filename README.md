# ClipCraft AI 🎬✨

> **Free, Local-First AI Video Clipping, Gaming Reframing & Synchronized Captioning Engine**  
> *Transform long-form videos into viral 9:16 vertical shorts without cloud API fees or privacy leaks.*

ClipCraft AI is a local-first, open-source media processing and AI application designed to transform long-form content—such as gaming livestreams, podcasts, and commentary—into high-impact 9:16 vertical short-form clips tailored for YouTube Shorts, TikTok, and Instagram Reels.

Every stage runs **100% locally on your own machine** using open-weights models and native media utilities. No OpenAI keys, no Anthropic credits, no cloud subscriptions, and no external data transmission.

---

## ⚡ Architecture Pipeline

```
[Local Video File OR Authorized YouTube URL]
                       ↓
            [Ingestion (yt-dlp)]
                       ↓
        [Audio Extraction (16kHz Mono WAV)]
                       ↓
    [Local Speech-to-Text (faster-whisper)]  ← Cached to disk
                       ↓
  [Dual-Baseline Audio Energy Screening (RMS)]
                       ↓
    [Semantic Causal Framing (Setup → Payoff)]
                       ↓
   [Facecam Spatial Clustering & Localization]
                       ↓
   [Multimodal Reaction Scoring & Temporal NMS]
                       ↓
          [Precision Cutting (FFmpeg)]
                       ↓
   [Modular 9:16 Reframing & FIT_WITH_BLUR]
                       ↓
   [Animated Word-Level Karaoke Subtitles (ASS)]
                       ↓
      [Interactive Web Review & Export Dashboard]
```

---

## 🚀 Key Features in Milestone v2.0

### 🎮 Gaming & Streamer Composition Engine
- **Persistent Webcam Localization:** Cheap spatial clustering algorithm samples video frames at low frequency (1 frame / 2.5s) to detect face persistence over time, isolating the streamer's webcam from transient cutscene characters with quadrant grouping and 2.0x width / 2.2x height shoulder/headroom expansion.
- **`FIT_WITH_BLUR` Widescreen Preservation:** Never forces wide 16:9 gameplay into a cramped vertical tunnel-vision crop. `FIT_WITH_BLUR` fits the complete aspect-ratio-preserved horizontal action over an ambient enlarged blurred background.
- **Stream Chat Overlay Exclusion:** Automatically clamps horizontal gameplay capture to $X \le 1700\text{px}$, cleanly trimming off native stream comments and right-side chat overlays.
- **Modular Layout Engine:** 
  - `GAMING_SPLIT`: Stacked vertical format (Top: Streamer Facecam / Bottom: Gameplay).
  - `GAMEPLAY_FOCUS`: Full-canvas gameplay with ambient blurred extensions or smart crop.
  - `STREAMER_FOCUS`: Full-canvas streamer reaction for high-emotion moments.
  - `AUTO_GAMING`: Automatically determines optimal strategy based on facecam presence.
  - Legacy `STANDARD_FACE_TRACK` and `CENTER_CROP`.

### 🎤 Animated Word-Level Karaoke Captions
- **Active Spoken Word Highlighting:** Real-time word-level ASS subtitles featuring active spoken word gold illumination (`&H0000E6FF&`) with a 112% pop bounce (`\fscx112\fscy112`).
- **Dynamic Seam Safe Placement:** Subtitles default to `LOWER_CENTER` on the visual split seam, keeping streamer faces, gameplay HUDs/crosshairs, and bottom platform UI overlays completely unobstructed.
- **Multiple Typography Presets:** Choose between `GAMING_KARAOKE`, `CLEAN` (static high-contrast white text with black outline), or `MINIMAL`.

### 🧠 Multimodal Reaction Detection & Scoring
- **Dual-Baseline Audio Energy Screening:** Fast $O(N)$ cumulative-sum sliding RMS analysis comparing instantaneous energy against both global and local baselines to catch shouting, laughter, and explosive volume surges.
- **Speech Corroboration Penalty:** Discards loud non-speech false positives (gameplay explosions, loud music, door slams) with a 40% penalty if no vocal speech is detected during the surge.
- **Targeted Visual Differencing:** Evaluates 2 fps frame-differencing across streamer facecam (head/body motion) and gameplay action regions.
- **Causal Micro-Narrative Expansion:** Expands detected reaction peaks into full 20s–60s story windows (`Setup` $\to$ `Event` $\to$ `Reaction` $\to$ `Payoff`) snapped cleanly to Whisper sentence boundaries without mid-word cuts.
- **Calibrated Anti-Saturation Scoring:** Soft nonlinear saturation curve eliminates score ties and ranks clips across explainable sub-scores: Hook, Standalone Clarity, Audio Surge, Streamer Motion, Gameplay Activity, and Payoff.

### 🎛️ Export Quality & Interactive Dashboard
- **Multi-Resolution Vertical Export:** Export clips at **1080x1920 (Full HD)**, **1440x2560 (2K QHD)**, or **2160x3840 (4K UHD)**.
- **Source-Aware Quality Tagging:** Clear UI indicators display whether an export resolution is *Native / Source-supported* or *Upscaled from source*. High-resolution exports from 1080p source footage are transparently labeled as upscaled rather than claiming artificial 4K detail.
- **Frame Rate Preservation:** Preserves source frame rate (e.g. 60 FPS) throughout the pipeline.
- **Clip Editor Modal:** Fine-tune clip start/end bounds, titles, dual-proportion split ratios (25%–50% streamer height), composition modes, and caption styling with pre-render configuration summaries.
- **Non-Destructive Re-rendering:** Changing layout presets, split proportions, or caption styles re-renders clips in seconds without recomputing upstream ingestion, transcription, or facecam stages.

---

## 🔒 Privacy & Local-First Philosophy

- **Zero API Fees:** No recurring bills or hidden token expenses.
- **100% Offline Capable:** Runs entirely on local compute after models are downloaded.
- **Absolute Privacy:** Video, audio, transcripts, and metadata stay confined to your machine inside isolated `projects/<id>/` workspaces. No content is ever uploaded to external servers.

---

## 🛠️ Prerequisites

To run ClipCraft AI on Windows, ensure the following tools are installed:

| Tool | Version | Purpose | Installation (Windows Winget) |
|------|---------|---------|-------------------------------|
| **Python** | 3.10 – 3.12 | Backend API & ML runtime | `winget install Python.Python.3.11` |
| **Node.js** | 18+ (20+ LTS rec.) | Web Dashboard UI | `winget install OpenJS.NodeJS.LTS` |
| **FFmpeg** | 6.0+ | Video cutting, reframing & audio | `winget install Gyan.FFmpeg` |
| **Ollama** | Latest | Local LLM inference server | Download from [ollama.com](https://ollama.com) |
| **Git** | Latest | Source control & versioning | `winget install Git.Git` |

---

## 💻 Windows Installation & Setup

### 1. Clone or Open Workspace
```powershell
git clone <your-repo-url>
cd clipping
```

### 2. Set Up Python Virtual Environment
```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
```

### 3. Set Up Frontend Web Interface
```powershell
cd frontend
npm install
cd ..
```

### 4. Pull Local LLM Model
Start Ollama, then pull the recommended lightweight model:
```powershell
ollama pull llama3.2:3b
```
*(Whisper models download automatically to the local cache on first execution).*

---

## 🎬 How to Run

### Option A: One-Click Windows Launcher (Recommended)
Launch both backend and frontend concurrently in PowerShell:
```powershell
.\start.ps1
```
Or double-click `start.bat`.

### Option B: Manual Startup
**Terminal 1 — Backend (FastAPI):**
```powershell
.venv\Scripts\activate
uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

**Terminal 2 — Frontend (React + Vite):**
```powershell
cd frontend
npm run dev
```

- **Frontend Dashboard:** [http://localhost:5173](http://localhost:5173)  
- **Interactive API Docs:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)  
- **Backend Health Check:** [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)

---

## 📖 5-Step Guide to Creating Your First Clip

1. **Open Dashboard**: Navigate to `http://localhost:5173`. Check the top navigation bar to confirm your hardware acceleration mode (CPU int8 or NVIDIA CUDA float16).
2. **Select Video Source**:
   - Local video: Enter an absolute path (e.g. `D:\Videos\stream_recording.mp4`).
   - YouTube: Paste a public video link.
3. **Configure Settings (Optional)**: Click **Pipeline Settings** to adjust clip duration limits (15s–60s), candidate count, Whisper model size (`base`, `small`), or LLM model (`llama3.2:3b`).
4. **Generate Highlights**: Click **Generate AI Highlights**. Monitor the live progress tracker as it executes audio extraction, transcription, multimodal screening, facecam clustering, cutting, reframing, and captioning.
5. **Review, Edit & Export**:
   - Preview the vertical short directly in the 9:16 player.
   - Click **Edit & Export** on any candidate card to tweak start/end timestamps, adjust the Streamer vs Gameplay ratio (30%/70%), toggle chat overlay exclusion, switch between `FIT_WITH_BLUR` and `CROP_FILL`, or select export resolution.
   - Download the final MP4 or standalone `.srt` subtitle file.

---

## 📁 Project Directory Structure

```
clipping/
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI REST routers (analysis, captions, clips, etc.)
│   │   ├── core/           # Configuration, hardware detection, logger
│   │   ├── models/         # Pydantic data schemas (candidate, layout, caption)
│   │   ├── services/       # Core pipeline services (audio, whisper, facecam, reframing)
│   │   ├── utils/          # FFmpeg command builders, subtitle parsers
│   │   └── main.py         # FastAPI application entry point
│   └── requirements.txt    # Backend Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/     # React components (CandidateCard, ClipEditorModal, VideoPlayer)
│   │   ├── pages/          # Dashboard views
│   │   ├── services/       # Fetch API client
│   │   └── types/          # TypeScript interface definitions
│   ├── package.json        # Frontend Node dependencies
│   └── vite.config.ts      # Vite bundler configuration
├── tests/                  # Automated unit, integration & regression test suite
├── scripts/                # Helper utilities (secret scanning, test runners)
├── .planning/              # GSD roadmap, milestone archives, and state history
├── .env.example            # Environment configuration template
├── .gitignore              # Production repository exclusions
├── README.md               # Application documentation
├── start.ps1               # One-click Windows PowerShell launcher
└── start.bat               # Windows Command Prompt batch launcher
```

---

## 🧪 Automated Testing

ClipCraft AI maintains a comprehensive automated regression suite covering all pipeline units, model parsers, filtergraph builders, and end-to-end integration flows.

Run the test suite in Python:
```powershell
python tests/run_all_tests.py
```
Or via PowerShell:
```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_tests.ps1
```

Verify frontend production compilation:
```powershell
cd frontend
npm run build
```

---

## ⚖️ Responsible Use & Legal Compliance

- **Fair Use & Copyright:** Only ingest and process videos you own, have explicit authorization to edit, or that qualify under fair use doctrine. ClipCraft AI does not defeat DRM, paywalls, or platform protections.
- **Zero Copyrighted Footage Tracked:** This repository contains source code and documentation only. No proprietary media, streamer recordings, or copyrighted gameplay assets are included in version control.
- **Engagement Disclaimer:** Multimodal quality scores reflect structural short-form video attributes (hook novelty, audio dynamics, narrative pacing) and do not guarantee viral reach or social media distribution.
