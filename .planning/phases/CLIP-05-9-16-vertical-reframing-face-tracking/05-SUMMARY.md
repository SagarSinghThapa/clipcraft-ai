---
phase: CLIP-05-9-16-vertical-reframing-face-tracking
plan: "01"
subsystem: vertical-reframing
tags: [opencv, face-tracking, 9-16-crop, ema-smoothing, ffmpeg]

requires:
  - phase: CLIP-04-precision-video-clipping-engine
    provides: Cut standalone candidate clips (raw_clip.mp4)
provides:
  - "9:16 vertical crop dimension calculation (1080x1920)"
  - "OpenCV speaker face tracking with outlier rejection"
  - "EMA crop trajectory smoothing to eliminate camera jitter"
  - "Robust center-crop fallback when detection confidence is low"
  - "FFmpeg crop + scale filtergraph pipeline"
affects: [Phase 6 Synchronized Captioning, Phase 7 Web Interface]

tech-stack:
  added: [opencv-python-headless]
  patterns:
    - "Sample frames at 5 fps to minimize CV CPU overhead"
    - "Median face position for robust crop center estimation"
    - "Lanczos filter scaling to 1080x1920"

key-files:
  created:
    - backend/app/services/reframing_service.py
    - backend/app/api/routes_reframe.py
    - tests/test_reframing.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Enforce even pixel dimensions for crop width (608px) to prevent H.264 encoder errors"
  - "Smooth horizontal tracking with Exponential Moving Average (alpha=0.15)"
  - "Always fall back safely to centered 9:16 crop if face detector returns empty"

requirements-completed: [REFRAME-01, REFRAME-02, REFRAME-03, REFRAME-04]

duration: 15min
completed: 2026-11-19
---

# Phase 5: 9:16 Vertical Reframing & Face Tracking Summary

**Implemented 9:16 vertical video reframing (1080x1920) with OpenCV face detection, EMA motion smoothing, and reliable center-crop fallback.**

## Accomplishments
1. **Mathematical Reframing**: `ReframingService` computes exact even 9:16 crop boxes (e.g. 608x1080 for 1080p source), scaling with Lanczos interpolation to 1080x1920.
2. **Jitter-Free Face Tracking**: Implemented frame-sampled OpenCV face tracking with median outlier rejection and Exponential Moving Average smoothing, eliminating distracting crop oscillation.
3. **Deterministic Fallback**: Automatically defaults to exact horizontal center crop if no face is visible.
4. **API Integration**: Mounted `/api/projects/{id}/reframe` endpoint for single or batch vertical reframing.
