# Plan 11-01 Summary: Gaming Layout Models & Content-Aware Gameplay Cropping

## Implementation Overview
Implemented the foundational gaming layout data models, multi-resolution vertical canvas geometry calculators, and the content-aware gameplay cropping service with facecam masking and EMA trajectory smoothing.

### Key Deliverables Completed:
1. **Layout Models & Resolution Presets (`backend/app/models/layout.py`)**:
   - `LayoutStrategy` enum: `GAMING_SPLIT`, `GAMEPLAY_FOCUS`, `STREAMER_FOCUS`, `AUTO_GAMING`, `STANDARD_FACE_TRACK`, `CENTER_CROP`.
   - `CanvasResolution` enum: `FHD_1080x1920`, `QHD_1440x2560`, `UHD_2160x3840`.
   - `CanvasDimensions`: calculates exact proportional top streamer height (e.g. 720) and bottom gameplay height (e.g. 1200) ensuring even pixel dimensions.
   - `GamingLayoutConfig`: encapsulates strategy, resolution preset, configurable split ratio (0.20 to 0.60, default 0.375), and EMA smoothing factor.
   - `GameplayCropWindow`: bounding box and aspect ratio metadata.
2. **Gameplay Cropping Service (`backend/app/services/gameplay_crop_service.py`)**:
   - `calculate_gameplay_crop_dimensions`: computes mathematically exact non-distorting crop sizes from source video for any target canvas (e.g., $972\times1080$ crop for $1080\times1200$ bottom gameplay, achieving exact 1.111x proportional scaling with zero stretching).
   - `mask_facecam_activity`: zeroes out detected streamer facecam bounds within activity maps to prevent streamer motion from biasing gameplay camera tracking.
   - `estimate_activity_x`: slides a 1D window across cumulative horizontal motion gradients outside the facecam to find the center of in-game action (chases, crosshairs).
   - `apply_ema_smoothing`: applies Exponential Moving Average smoothing with macroblock-aligned even pixel coordinates and boundary clamping.
3. **Automated Unit Tests (`tests/test_gaming_crop.py`)**:
   - 6 test cases verifying geometry calculations across 1080p, 1440p, and 4K presets, facecam masking, action focus estimation, EMA jump damping, and crop window generation.
   - 100% pass rate in 0.23 seconds.

## Verification Results
- `pytest tests/test_gaming_crop.py -v`: 6 passed in 0.23s.
