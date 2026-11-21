---
phase: CLIP-04-precision-video-clipping-engine
plan: "01"
subsystem: precision-clipping
tags: [ffmpeg, video-cutting, libx264, audio-sync, mp4]

requires:
  - phase: CLIP-03-ai-highlight-detection-explainable-scoring
    provides: Candidate highlights with start and end timestamps
provides:
  - "Frame-accurate FFmpeg video cutting service"
  - "Keyframe-synchronized MP4 output with zero audio drift"
  - "Endpoints to cut single or batch candidate clips"
affects: [Phase 5 9:16 Vertical Reframing, Phase 6 Synchronized Captioning]

tech-stack:
  added: [ffmpeg]
  patterns:
    - "Precise seeking with -ss/-to before -i"
    - "libx264 fast preset + crf 18 re-encoding to eliminate frozen start frames"
    - "avoid_negative_ts make_zero for audio sync protection"

key-files:
  created:
    - backend/app/services/clipping_service.py
    - backend/app/api/routes_clips.py
    - tests/test_clipping.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Always re-encode cuts rather than stream copy to ensure perfect keyframe alignment and audio sync"
  - "Store individual candidate subclips under projects/<id>/clips/<clip_id>/"

requirements-completed: [CLIP-01, CLIP-02, CLIP-03]

duration: 15min
completed: 2026-11-19
---

# Phase 4: Precision Video Clipping Engine Summary

**Implemented frame-accurate FFmpeg cutting with libx264/aac re-encoding, eliminating I-frame freeze and audio drift for clean standalone MP4 candidate clips.**

## Accomplishments
1. **Accurate Cut Engine**: `ClippingService` builds precise FFmpeg argument lists (`-ss`, `-to`, `-c:v libx264`, `-crf 18`, `-c:a aac`, `-avoid_negative_ts make_zero`), ensuring that cuts begin immediately without black frames or frozen video.
2. **Standard Output**: Generates web-optimized MP4 files with `+faststart` metadata under `projects/<id>/clips/<clip_id>/raw_clip.mp4`.
3. **API Endpoints**: Implemented `/api/projects/{id}/clips/cut` supporting selective single-clip cuts or batch rendering of all chosen candidates.
