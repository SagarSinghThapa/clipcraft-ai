# Phase 12 Research: Professional Animated Word-Synchronized Captions for Gaming Shorts

## 1. Real Whisper Word-Timestamp Synchronization

### Timing Pipeline
faster-whisper produces segment-level word timings (`WordTiming(word, start, end, probability)`):
- All word timestamps in `transcript.json` are anchored in source video time $t_{\text{source}}$.
- When rendering candidate clip $[t_{\text{clip\_start}}, t_{\text{clip\_end}}]$, every word is normalized to clip-relative time:
  $$t_{\text{rel\_start}} = \max(0.0, t_{\text{word\_start}} - t_{\text{clip\_start}})$$
  $$t_{\text{rel\_end}} = \max(t_{\text{rel\_start}} + 0.10, t_{\text{word\_end}} - t_{\text{clip\_start}})$$
- Words strictly outside $[t_{\text{clip\_start}} - 0.20, t_{\text{clip\_end}} + 0.20]$ are discarded.
- If the user re-adjusts clip start/end boundaries, relative offsets recompute cleanly in milliseconds without touching Whisper or audio extraction.

## 2. Natural Caption Chunking Heuristics (2–5 Words)
Displaying entire sentences clutters vertical 9:16 canvases, while single-word rapid flashes cause eye fatigue.

### Chunking Rules:
1. **Target Word Count**: 2 to 5 words per chunk (default 3–4 words).
2. **Punctuation Breaks**: Terminal punctuation (`.`, `!`, `?`, `,`) forces a chunk break.
3. **Speech Pause Threshold**: An inter-word gap $\ge 0.40\text{s}$ triggers an immediate chunk boundary.
4. **Max Display Duration**: No chunk exceeds $2.5\text{s}$.
5. **Min Display Duration**: Every chunk displays for at least $0.40\text{s}$ to guarantee viewer legibility.

## 3. SubStation Alpha (.ass) Typography & Colors

### Color Specifications (ASS `&HAABBGGRR&` hex):
| Role | Color | Hex Code | Visual Effect |
|:---|:---|:---|:---|
| **Active Word (Highlight)** | Vibrant Neon Gold / Yellow | `&H0000E6FF&` | Draws eye to spoken word in real time |
| **Normal Word (Context)** | Crisp Solid White | `&H00FFFFFF&` | High readability against dark/light game scenes |
| **Stroke Outline** | Deep Solid Black | `&H00000000&` | 5px thick stroke prevents blending into bright game UI |
| **Drop Shadow** | Translucent Charcoal | `&H80000000&` | 2px shadow adds depth separation |

### Active-Word Inline Override Syntax:
For a 4-word chunk `"WHAT IS HE DOING"` where `t` progresses across words:
```ass
Dialogue: 0,0:00:01.00,0:00:01.25,KaraokeStyle,,0,0,0,,{\c&H0000E6FF&\fscx106\fscy106}WHAT{\fscx100\fscy100} {\c&H00FFFFFF&}IS HE DOING
Dialogue: 0,0:00:01.25,0:00:01.45,KaraokeStyle,,0,0,0,,{\c&H00FFFFFF&}WHAT {\c&H0000E6FF&\fscx106\fscy106}IS{\fscx100\fscy100} {\c&H00FFFFFF&}HE DOING
Dialogue: 0,0:00:01.45,0:00:01.80,KaraokeStyle,,0,0,0,,{\c&H00FFFFFF&}WHAT IS {\c&H0000E6FF&\fscx106\fscy106}HE{\fscx100\fscy100} {\c&H00FFFFFF&}DOING
Dialogue: 0,0:00:01.80,0:00:02.30,KaraokeStyle,,0,0,0,,{\c&H00FFFFFF&}WHAT IS HE {\c&H0000E6FF&\fscx106\fscy106}DOING{\fscx100\fscy100}
```
- `\fscx106\fscy106`: subtle 6% active-word pop that feels energetic and crisp without bouncing or shifting text layout.
- 100% deterministic across all FFmpeg builds and platforms.

## 4. Resolution-Aware Scaling & Multi-Canvas Geometry

All typographic and spatial dimensions scale proportionally with vertical canvas height ($S = \text{height} / 1920$):

| Parameter | Base (1080x1920) | QHD (1440x2560, $S=1.333$) | 4K UHD (2160x3840, $S=2.0$) |
|:---|:---:|:---:|:---:|
| **Font Size** | 64 pt | 85 pt | 128 pt |
| **Outline Width** | 5 px | 7 px | 10 px |
| **Shadow Offset** | 2 px | 3 px | 4 px |
| **LOWER_CENTER Seam Offset** | +40 px | +53 px | +80 px |

## 5. Dynamic Seam-Aware Auto-Placement

Rather than hard-coding 37.5%, the caption engine queries the actual layout geometry (`top_height`) from Phase 11 (`GamingLayoutConfig` / `CanvasDimensions`).

### Placement Calculation:
- **`AUTO` (Default for Gaming)**:
  - If `GAMING_SPLIT`: Anchors text in the visual seam just below the streamer reaction and above gameplay action:
    $$\text{MarginV} = \text{top\_height} + \operatorname{round}(35 \cdot S) \quad (\text{with } \text{Alignment} = 8 \text{ Top-Center})$$
    For 1080p with 37.5% split (`top_height = 720`):
    Text top sits at $Y = 720 + 35 = 755\text{ px}$.
    Baseline sits at $Y \approx 820\text{ px}$.
    - $755\text{ px} > 720\text{ px}$: 100% clear of the streamer's chin, microphone, and reaction box.
    - $820\text{ px} \ll 1600\text{ px}$: 100% clear of bottom TikTok / Shorts / Reels action buttons.
    - If split ratio is later adjusted (e.g. 32% or 45%), `top_height` automatically updates and captions track the seam flawlessly.
  - If single-stream (`GAMEPLAY_FOCUS`, `STANDARD_FACE_TRACK`, `CENTER_CROP`):
    Defaults to `BOTTOM` ($\text{MarginV} = \operatorname{round}(320 \cdot S), \text{Alignment} = 2$).
- **Manual Overrides**: `TOP`, `CENTER`, `LOWER_CENTER`, `BOTTOM`.

## 6. Preset Architecture & Reaction Readiness

### Presets:
1. **`GAMING_KARAOKE`** (Default): Uppercase, bold, 3–4 words/chunk, active word gold (`&H0000E6FF&`), seam-aware placement.
2. **`CLEAN`**: Sentence-case, bold white text with black outline, static display (no karaoke color cycling), standard bottom margin.
3. **`MINIMAL`**: Smaller font size (50 pt), thinner outline (3 px), no shadow, clean bottom placement.

### Phase 13 Reaction Readiness:
Each word in the caption data model includes an `emphasis` tag:
```python
class WordEmphasis(str, Enum):
    NORMAL = "normal"
    STRONG = "strong"      # e.g. all-caps or exclamation
    REACTION = "reaction"  # High audio surge word (Phase 13 hook)
```
When `emphasis == "reaction"`, future phases or styles can apply extra glow (`\blur`), color shift, or uppercase formatting without altering the underlying timing or rendering engine.
