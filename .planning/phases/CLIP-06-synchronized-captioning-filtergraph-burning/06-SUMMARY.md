---
phase: CLIP-06-synchronized-captioning-filtergraph-burning
plan: "01"
subsystem: synchronized-captions
tags: [subtitles, srt, ass, caption-burning, typography, ffmpeg]

requires:
  - phase: CLIP-05-9-16-vertical-reframing-face-tracking
    provides: 9:16 vertical video (reframed.mp4)
  - phase: CLIP-02-audio-extraction-local-speech-transcription
    provides: Word-level timestamps (WordTiming)
provides:
  - "Word-chunked vertical subtitle cards (1-4 words)"
  - "Standard .srt subtitle generator"
  - "High-contrast .ass subtitle generator with safe-zone margin (MarginV=320)"
  - "FFmpeg filtergraph subtitle burning engine producing final_clip.mp4"
affects: [Phase 7 Local Web Interface, Phase 8 End-to-End Test Suite]

tech-stack:
  added: [ass, srt, ffmpeg-filtergraph]
  patterns:
    - "Relative timing normalization (word timestamp minus clip start)"
    - "Safe margin positioning (240-320px bottom buffer) for TikTok/Shorts UI elements"
    - "Windows path escaping in FFmpeg subtitle filters"

key-files:
  created:
    - backend/app/services/caption_service.py
    - backend/app/api/routes_captions.py
    - tests/test_captions.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Chunk captions into short 2-3 word blocks for optimal mobile readability"
  - "Provide both ASS (burned-in styled subtitles) and SRT (standalone export)"
  - "Automatic fallback from ASS filter to standard SRT subtitles filter if fontconfig is restricted"

requirements-completed: [CAPTION-01, CAPTION-02, CAPTION-03, CAPTION-04]

duration: 15min
completed: 2026-11-19
---

# Phase 6: Synchronized Captioning & Filtergraph Burning Summary

**Implemented word-synchronized vertical subtitle chunking, ASS/SRT formatting with safe-margin typography, and burned-in caption rendering via FFmpeg to produce playable final MP4 clips.**

## Accomplishments
1. **Vertical Word Chunking**: `CaptionService` groups word timings into rapid, readable 1–3 word phrases normalized to relative clip timestamps.
2. **High-Contrast Styling**: Generates custom ASS scripts with PlayResX=1080, PlayResY=1920, heavy black outlines, drop shadows, and 320px bottom safe margins to avoid platform UI overlap.
3. **Robust Burn Engine**: Burns subtitles directly into video using FFmpeg filtergraph with Windows path escaping, and outputs standalone `.srt` files.
4. **API Endpoints**: Exposed `/api/projects/{id}/captions` and `/api/projects/{id}/captions/{clip_id}/srt`.
