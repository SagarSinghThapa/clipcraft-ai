# Phase 11 Research: Modular Gaming Layout Engine & Dual-Stream Compositing

## 1. Domain Overview
Modern gaming short-form videos (TikTok, YouTube Shorts, Instagram Reels) require high-impact vertical presentation where viewers can see both the streamer's reaction and the in-game action simultaneously without distortion or black bars.

Traditional single-crop reframing fails for gaming content because it forces a choice between showing only the streamer's face (losing the game context) or only the game (losing the streamer's high-energy reactions).

## 2. Mathematical Canvas Geometry & Resolution Presets (`EXPORT-01`)
Vertical export targets must be exact multiples of 9:16 and even pixel dimensions:

| Preset Name | Total Dimensions | Top (Streamer) Region | Bottom (Gameplay) Region | Default Split Ratio |
|:---|:---|:---|:---|:---|
| `FHD_1080x1920` | 1080 x 1920 | 1080 x 720 | 1080 x 1200 | 37.5% / 62.5% |
| `QHD_1440x2560` | 1440 x 2560 | 1440 x 960 | 1440 x 1600 | 37.5% / 62.5% |
| `UHD_2160x3840` | 2160 x 3840 | 2160 x 1440 | 2160 x 2400 | 37.5% / 62.5% |

### Aspect Ratio Preservation:
- **Streamer Region (Top)**: Standard 16:9 widescreen or 4:3 box expanded from `FacecamRegion`. It is scaled directly to `1080x720` (exact 3:2 or 16:9 fit).
- **Gameplay Region (Bottom)**: 1080x1200 has an aspect ratio of 9:10. To fill this without stretching, gameplay is cropped to a 9:10 sub-rectangle from the source video:
  $$\text{crop\_h} = \text{source\_h}$$
  $$\text{crop\_w} = \operatorname{round\_even}\left(\text{source\_h} \times \frac{9}{10}\right) = \operatorname{round\_even}(1080 \times 0.9) = 972\text{ px}$$
- Scaling $972 \times 1080 \to 1080 \times 1200$ achieves exact proportional scaling ($1.111\times$) with zero distortion!

## 3. Content-Aware Gameplay Cropping (`GAME-01`, `GAME-02`)
1. **Facecam Masking**: If a persistent facecam exists at `(cam_x, cam_y, cam_w, cam_h)`, that rectangle is zeroed out in visual motion/activity calculations.
2. **Horizontal Activity Density**:
   - The gameplay canvas can slide horizontally from $X = 0$ to $X = \text{source\_w} - \text{crop\_w}$ (e.g., $0$ to $1920 - 972 = 948\text{ px}$).
   - Divide candidate horizontal regions into overlapping windows.
   - Compute optical flow / frame differencing intensity outside the masked facecam.
   - For driving games (GTA chases) or action games, activity concentrates around vehicles, crosshairs, or player movement.
3. **EMA Smoothing**:
   $$X_{\text{smooth}}(t) = \alpha \cdot X_{\text{target}}(t) + (1 - \alpha) \cdot X_{\text{smooth}}(t-1)$$
   With $\alpha = 0.10$, camera panning is buttery smooth, eliminating jarring jumps between cuts while following prolonged game action.

## 4. Stacked Dual-Stream FFmpeg Filtergraph (`LAYOUT-01`)
Using FFmpeg's `split` and `vstack` filters in a single pass ensures optimal encoding speed and avoids temporary intermediate files:

```bash
ffmpeg -y -ss {start_time} -t {duration} -i "{source_path}" \
  -filter_complex "\
    [0:v]split=2[cam_raw][game_raw]; \
    [cam_raw]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale={target_w}:{cam_target_h}:flags=lanczos[cam_out]; \
    [game_raw]crop={game_w}:{game_h}:{game_x}:{game_y},scale={target_w}:{game_target_h}:flags=lanczos[game_out]; \
    [cam_out][game_out]vstack=inputs=2[v]" \
  -map "[v]" -map 0:a? \
  -c:v libx264 -crf 18 -preset fast -pix_fmt yuv420p -c:a aac -b:a 192k \
  "{output_path}"
```

## 5. Layout Strategies (`LAYOUT-01` to `LAYOUT-04`)
- **`GAMING_SPLIT`**: Top streamer facecam, bottom gameplay. Primary strategy when streamer facecam is detected.
- **`GAMEPLAY_FOCUS`**: High-action gameplay occupies full vertical canvas using 9:16 crop window with motion tracking, or 16:9 gameplay centered with top/bottom blurred background extension.
- **`STREAMER_FOCUS`**: Streamer occupies main canvas with blurred gameplay background for story/reaction moments.
- **`AUTO_GAMING`**: Automatically inspects `FacecamRegion.is_detected`. If `True` (confidence $\ge 0.40$), routes to `GAMING_SPLIT`; else routes to `GAMEPLAY_FOCUS`.
