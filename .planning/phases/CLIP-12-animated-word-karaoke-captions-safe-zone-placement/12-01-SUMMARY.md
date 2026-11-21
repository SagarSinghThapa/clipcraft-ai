# Plan 12-01 Summary: Core Caption Models, Presets, Whisper Chunking & Karaoke ASS Generator

## Overview
Implemented foundational captioning architecture under Phase 12:
1. Pydantic models for caption styling presets, placement safe zones, word emphasis levels, styled word timings, and chunking groups (`backend/app/models/caption.py`).
2. Chunking engine converting faster-whisper word timestamps into clip-relative offsets without faking or linear interpolation, grouping into 2–5 word readable chunks with pause ($\ge 0.40$s) and punctuation break handling (`backend/app/services/caption_service.py`).
3. Word-level karaoke generator creating sequential ASS dialogue events with inline gold illumination (`&H0000E6FF&`) and subtle 6% scale pop (`\fscx106\fscy106`).
4. Proportional resolution scaling for 1080p, 1440p, and 4K vertical exports.
5. Dynamic seam placement geometry positioning captions safely below streamer facecam without obscuring gameplay action or platform mobile UI.

## Artifacts Created / Modified
- `backend/app/models/caption.py`: Added `CaptionPlacement`, `CaptionPreset`, `WordEmphasis`, `StyledWordTiming`, `CaptionChunk`, and `CaptionStyleConfig`.
- `backend/app/services/caption_service.py`: Updated `chunk_words_for_clip`, `generate_srt_content`, and `generate_ass_content` with backward-compatible dict and model support.
- `tests/test_karaoke_captions.py`: Added 6 unit tests covering relative timing math, pause/punctuation chunking, inline karaoke ASS rendering, resolution scaling, presets, and placement geometry.

## Verification
- `pytest tests/test_captions.py tests/test_karaoke_captions.py -v`: 9/9 passed in 0.69s.
