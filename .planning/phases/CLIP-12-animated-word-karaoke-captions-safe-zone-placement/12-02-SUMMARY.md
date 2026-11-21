# Plan 12-02 Summary: Dynamic Seam Placement, Caching & REST API Integration

## Overview
Completed pipeline integration and REST API exposure for Phase 12:
1. Integrated dynamic seam-aware auto-placement (`LOWER_CENTER` anchoring at `top_height + 35 * scale` with `Alignment = 8`) for `GAMING_SPLIT` clips based on real dual-stream layout geometry.
2. Implemented intelligent non-destructive caption style caching (`caption_settings.json`): changing presets or placement reuses existing `reframed.mp4` and `transcript.json` without re-running YouTube downloading, Whisper transcription, or facecam detection.
3. Updated `GamingLayoutService` to record `layout_info.json` alongside reframed media.
4. Extended `POST /api/projects/{project_id}/captions` REST API endpoint to accept `preset`, `placement`, `karaoke_enabled`, `highlight_color`, `words_per_chunk`, and `font_size`.
5. Registered new test modules in master test runner `tests/run_all_tests.py` (59/59 passing).

## Artifacts Created / Modified
- `backend/app/services/caption_service.py`: Updated `burn_captions_for_clip` and `burn_all_selected_clips` with dynamic seam geometry, canvas dimension probing, and `caption_settings.json` caching.
- `backend/app/services/gaming_layout_service.py`: Added automatic `layout_info.json` persistence for downstream safe-zone placement.
- `backend/app/api/routes_captions.py`: Extended `CaptionRequest` model and `burn_project_captions` endpoint with preset options.
- `tests/test_captions_api.py`: Added 4 tests validating seam geometry, bottom fallback, non-destructive caching, and API parameter handling.
- `tests/run_all_tests.py`: Added `tests.test_karaoke_captions` and `tests.test_captions_api`.

## Verification
- `pytest tests/test_captions_api.py -v`: 4/4 passed in 0.63s.
- `python tests/run_all_tests.py`: 59/59 passed in 0.858s.
