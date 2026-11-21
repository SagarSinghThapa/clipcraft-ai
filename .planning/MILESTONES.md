# Milestones

## v2.0: Gaming & Streamer Vertical Reframing Engine
**Shipped:** 2026-11-20  
**Status:** ✅ Complete & Verified  
**Phases:** 10–14 (12 plans)  
**Archive:** [.planning/milestones/v2.0-ROADMAP.md](milestones/v2.0-ROADMAP.md)  
**Requirements:** [.planning/milestones/v2.0-REQUIREMENTS.md](milestones/v2.0-REQUIREMENTS.md)  
**Verification Audit:** [.planning/v2.0-MILESTONE-AUDIT.md](v2.0-MILESTONE-AUDIT.md)  

### Key Accomplishments
- **Persistent Streamer Webcam Detection:** Spatial clustering algorithm analyzing low-frequency frame samples (1 frame / 2.5s) to localize facecam boundaries with quadrant grouping, transient cutscene face rejection, and shoulder/headroom expansion.
- **Modular Gaming Layout & Composition Engine:** Stacked dual-stream FFmpeg filtergraphs supporting `GAMING_SPLIT`, `GAMEPLAY_FOCUS`, `STREAMER_FOCUS`, and `AUTO_GAMING`. Implemented aspect-preserving `FIT_WITH_BLUR` widescreen gameplay composition, stream chat overlay exclusion ($X \le 1700\text{px}$), and multi-resolution canvas export (1080p, 1440p, 4K).
- **Animated Word-Level Karaoke Subtitles:** ASS subtitle generator featuring active spoken word gold illumination (`&H0000E6FF&`) and 112% reaction pop bounce, dynamically anchored to the split seam safe zone (`LOWER_CENTER`) to avoid occluding streamer faces or bottom platform UI.
- **Multimodal Reaction-Aware Scoring Engine:** High-energy reaction discovery fusing $O(N)$ dual-baseline audio RMS screening, speech corroboration penalties, 2 fps facecam/gameplay visual differencing, causal sequence micro-narrative expansion (20s–60s), and calibrated anti-saturation scoring.
- **Interactive Web Review & Export Quality Controls:** Candidate review gallery with reaction category badges and score rubrics; ClipEditorModal with dual-proportion slider (25%–50%), gameplay composition modes, chat exclusion toggle, resolution selector, and non-destructive re-rendering.
- **Real-World Verified:** Fully tested and verified end-to-end on live 35-minute GTA VI / IShowSpeed stream (`proj_40b4d189bb59`) with 0 decode errors, 60 FPS preservation, and 84/84 passing automated regression tests.

---

## v1.0: AI Video Clipper MVP
**Shipped:** 2026-11-19  
**Status:** ✅ Complete & Verified  
**Phases:** 1–9 (13 plans)  
**Archive:** [.planning/milestones/v1.0-ROADMAP.md](milestones/v1.0-ROADMAP.md)  
**Requirements:** [.planning/milestones/v1.0-REQUIREMENTS.md](milestones/v1.0-REQUIREMENTS.md)  
**Verification Audit:** [.planning/v1.0-MILESTONE-AUDIT.md](v1.0-MILESTONE-AUDIT.md)  

### Key Accomplishments
- Full automated pipeline: Ingestion (local + YouTube via `yt-dlp`), 16kHz audio extraction, local transcription (`faster-whisper`), Ollama LLM highlight extraction (`llama3.2:3b`), multi-factor scoring (0–100), precision cutting, OpenCV face-aware 9:16 vertical reframing, and burned-in synchronized captions.
- Zero paid API dependencies: Runs 100% locally on CPU int8 or NVIDIA CUDA.
- Interactive modern React + Vite + Tailwind local web application with real-time stage monitoring and clip trimming.
- Real end-to-end verified on 35-minute YouTube video (`https://youtu.be/kR8bhkVAgBY`) with zero stream errors.
