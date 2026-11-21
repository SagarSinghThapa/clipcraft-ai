# Phase 14 Research: Interactive Gaming UI Controls & End-to-End Validation

**Phase:** CLIP-14-interactive-gaming-ui-controls-and-end-to-end-validation  
**Milestone:** v2.0 Gaming & Streamer Vertical Reframing Engine  
**Requirements Covered:** `UI-01`, `UI-02`  
**Dependencies:** Phase 10 (Facecam), Phase 11 (Modular Layout & Refinement), Phase 12 (Karaoke Captions), Phase 13 (Multimodal Scoring)

---

## 1. Domain & Architectural Context

In Phases 10 through 13, ClipCraft built the foundational backend engines for Milestone v2.0:
- **Phase 10:** Streamer facecam detection and spatial clustering (`FacecamService`, `checkpoint_facecam.json`).
- **Phase 11 & Refinement:** Modular multi-strategy layout engine (`GAMING_SPLIT`, `GAMEPLAY_FOCUS`, `STREAMER_FOCUS`, `AUTO_GAMING`, `STANDARD_FACE_TRACK`, `CENTER_CROP`), multi-resolution vertical rendering (1080p, 1440p, 4K), and visual refinement supporting:
  - `GameplayCompositionMode`: `FIT_WITH_BLUR` (fits 16:9 widescreen gameplay over ambient blurred background, preserving 100% of horizontal action), `CROP_FILL` (9:10 bottom crop), and `AUTO` (content-loss driven selection).
  - Stream chat / overlay exclusion (`exclude_chat_overlay`: masks persistent side chat $X \ge 1700\text{px}$).
  - Calibrated default split ratio of `30% Streamer / 70% Gameplay` (576px Top / 1344px Bottom in 1080p).
- **Phase 12:** Word-synchronized animated ASS karaoke captions with active word gold illumination (`&H0000E6FF&`), reaction pop scaling (`\fscx112\fscy112`), and safe-zone positioning (`LOWER_CENTER` seam placement).
- **Phase 13:** Multimodal reaction scoring combining dual-baseline audio energy surges, Whisper speech corroboration, facecam/gameplay visual motion differencing, and causal sequence expansion ($20\text{s}-60\text{s}$).

**Phase 14 is the capstone phase for Milestone v2.0.** It bridges these backend engines to the user-facing web dashboard and completes end-to-end validation.

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           WEB REVIEW DASHBOARD (React + Vite)                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  Candidate Gallery:                                                             │
│  - Multimodal Score Pill (78/100, Peak Z=3.52, Audio / Visual / Gameplay stats) │
│  - Reaction Category Badge (SURPRISE, FUNNY_REACTION, RAGE, etc.)               │
│  - Current Layout Badge (GAMING_SPLIT 30% • FIT_WITH_BLUR • LOWER_CENTER)       │
│                                                                                 │
│  Interactive Editor Modal:                                                      │
│  - Title & Bounds Fine-Tuning (snapped to Whisper words)                        │
│  - Layout Mode Selector: AUTO_GAMING, GAMING_SPLIT, GAMEPLAY_FOCUS...           │
│  - Gameplay Composition Selector: AUTO, FIT_WITH_BLUR, CROP_FILL                │
│  - Streamer Split Ratio Slider: 25% - 50% (visual bar: 30% Cam / 70% Game)      │
│  - Exclude Stream Chat Toggle: [x] Mask side chat overlay ($X \ge 1700px$)       │
│  - Caption Style Preset: GAMING_KARAOKE, CLEAN, MINIMAL                         │
│  - Caption Placement Dropdown: AUTO (Seam), LOWER_CENTER, CENTER, TOP, BOTTOM   │
│  - Export Quality & Resolution:                                                 │
│      * Full HD (1080x1920) - Default                                            │
│      * 1440p (1440x2560) - 2K                                                   │
│      * 4K UHD (2160x3840) - Explicit user choice only (never automatic)         │
│  - Source-Aware Quality Badge: "Native / Source-supported" vs "Upscaled"        │
│  - Frame Rate Indicator: Displays preserved source FPS (e.g. 60 FPS)            │
│  - Pre-Render Export Summary Card: Visual recap of all render parameters        │
│                                                                                 │
│  Action: Save Adjustments -> Re-render Clip -> Updated Video & Captions Preview │
└─────────────────────────────────────────────────────────────────────────────────┘
                                     │
                     REST API (FastAPI /routes_analysis)
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────────────┐
│                      BACKEND SERVICES & CANDIDATE PERSISTENCE                   │
├─────────────────────────────────────────────────────────────────────────────────┤
│  - CandidateClip model extended with layout_strategy, split_ratio,              │
│    gameplay_composition, exclude_chat_overlay, caption_preset,                 │
│    caption_placement, resolution                                                │
│  - PATCH /api/projects/{id}/candidates/{clip_id} persists user overrides       │
│  - POST /api/projects/{id}/reframe & /captions respect per-clip layout overrides│
│  - Non-destructive caching: only re-runs cut/reframe/captions on edit,          │
│    preserving source download, transcription, and Phase 13 reaction discoveries │
│  - FFmpeg dual/triple-stream pipeline renders custom compositions on demand     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Requirements & Specification Analysis

### Requirement UI-01: Layout Mode Selector
- **Target Location:** Candidate review cards and Clip Editor Modal in the React web dashboard.
- **Supported Strategies:**
  1. `AUTO_GAMING` (Default) — automatically resolves to `GAMING_SPLIT` if a persistent facecam is detected (confidence $\ge 0.40$), otherwise falls back to `GAMEPLAY_FOCUS`.
  2. `GAMING_SPLIT` — stacked vertical composition (Top: Streamer Facecam / Bottom: Gameplay).
  3. `GAMEPLAY_FOCUS` — vertical crop centered on high-activity gameplay, or blurred side-bars.
  4. `STREAMER_FOCUS` — focused on the streamer reaction (useful for podcast clips or full-screen reaction moments).
  5. `STANDARD_FACE_TRACK` — v1.0 dynamic single-speaker face tracking with EMA smoothing.
  6. `CENTER_CROP` — static centered 9:16 crop without face tracking.

### Requirement UI-02: Interactive Sliders & Overrides
- **Gameplay Composition Mode:**
  - Options:
    - `AUTO` (Auto: Fit with blur if widescreen action would be cut off)
    - `FIT_WITH_BLUR` (Fit uncropped widescreen gameplay foreground over blurred background - Verified winning default)
    - `CROP_FILL` (Direct 9:10 bottom crop)
  - Applicable when layout is `GAMING_SPLIT`, `AUTO_GAMING`, or `GAMEPLAY_FOCUS`.
- **Streamer Height Ratio Slider:**
  - Range: `0.25` (25%) to `0.50` (50%), stepping by `0.025` (2.5%). Default: `0.30` (30% streamer / 70% gameplay).
  - Visual Feedback: Real-time dual bar displaying Streamer % (e.g. 30.0%) vs Gameplay % (e.g. 70.0%), plus pixel dimensions for 1080p (e.g. 576px Top / 1344px Bottom).
- **Exclude Stream Chat Toggle:**
  - Checkbox toggle: `exclude_chat_overlay` (default: `true`).
  - Automatically crops out persistent right-side stream chat overlays (e.g. $X \ge 1700\text{px}$) from gameplay composition.
- **Caption Style & Placement:**
  - Style Preset: `GAMING_KARAOKE` (Default), `CLEAN`, `MINIMAL`.
  - Placement: `AUTO` (smart seam placement default), `LOWER_CENTER`, `CENTER`, `TOP`, `BOTTOM`.

---

## 3. Export Quality & Resolution Controls

### 3.1. Target Resolutions & Safe Defaults
The backend supports multi-resolution export via `CanvasResolution` enum from Phase 11. The frontend must explicitly expose these options without forcing high compute costs automatically:
1. **Full HD — 1080x1920 (Default):** Standard high-definition vertical format optimized for TikTok, YouTube Shorts, and Instagram Reels.
2. **1440p — 1440x2560:** 2K vertical export for high-resolution displays.
3. **4K UHD — 2160x3840:** Ultra-HD export. **Crucial rule:** 4K is never rendered automatically. It must be explicitly selected by the user.

### 3.2. Source-Aware Quality Labeling
The frontend inspects `project.metadata` (which contains `width`, `height`, and `fps` probed during ingestion).
- It compares the target canvas vertical height (1920, 2560, 3840) against the source media resolution.
- If target vertical pixels exceed source resolution (e.g. 1080p source requested at 4K UHD):
  - The UI displays: `4K — Upscaled from source`.
  - It does NOT claim native 4K quality; the UI makes it transparent that upscaling enlarges source pixels.
- If target vertical pixels are fully supported by source resolution (e.g. 1080p source exported to 1080p, or 4K source exported to 1080p/4K):
  - The UI displays: `Native / Source-supported`.

### 3.3. Frame Rate Preservation
- FFmpeg preserves the source frame rate ($fps_{src}$, e.g. 60 FPS or 30 FPS).
- The UI displays the expected output frame rate based on `project.metadata.fps` (e.g. `60 FPS (preserved from source)`), avoiding synthetic conversion.

### 3.4. Pre-Render Export Summary Card
Before clicking "Save & Re-Render", the `ClipEditorModal` renders a compact summary card displaying:
```
┌────────────────────────────────────────────────────────┐
│ EXPORT SUMMARY                                         │
├────────────────────────────────────────────────────────┤
│ Layout:                GAMING_SPLIT                    │
│ Streamer / Gameplay:   30% / 70% (576px / 1344px)      │
│ Gameplay Mode:         FIT_WITH_BLUR                   │
│ Stream Chat:           Excluded (Clean 1700px width)   │
│ Captions:              GAMING_KARAOKE / AUTO (Seam)    │
│ Target Resolution:     1080x1920 (Full HD)             │
│ Frame Rate:            60 FPS (Preserved from source)  │
│ Visual Quality:        Native / Source-supported       │
└────────────────────────────────────────────────────────┘
```

### 3.5. Non-Destructive Caching Guarantees
Adjusting export resolution, caption style, or split ratio MUST NOT rerun upstream stages:
- **Never re-run:** YouTube download (`ingested`), Whisper transcription (`transcribed`), Ollama LLM extraction, or Phase 13 reaction discovery.
- **Targeted re-render:** Only executes the render pipeline for the edited clip:
  1. `POST /api/projects/{id}/clips/cut` (only if start/end bounds changed, otherwise reuses `raw_clip.mp4`).
  2. `POST /api/projects/{id}/reframe` (produces `reframed.mp4` with new resolution/split ratio/composition).
  3. `POST /api/projects/{id}/captions` (burns `final_clip.mp4` with new preset/placement).

---

## 4. Data Flow & State Management

### 4.1. Data Model Extension
In `backend/app/models/candidate.py`:
```python
class CandidateClip(BaseModel):
    id: str
    project_id: str
    title: str
    start_time: float
    end_time: float
    duration: float
    transcript_excerpt: str
    hook_assessment: str
    standalone_context: str
    reasoning: str
    score: ScoreBreakdown
    selected_for_rendering: bool = True
    rendered_clip_path: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Phase 14 User Overrides:
    layout_strategy: Optional[LayoutStrategy] = None
    gameplay_composition: Optional[GameplayCompositionMode] = None
    split_ratio: Optional[float] = Field(default=None, ge=0.20, le=0.60)
    exclude_chat_overlay: Optional[bool] = None
    caption_preset: Optional[CaptionPreset] = None
    caption_placement: Optional[CaptionPlacement] = None
    resolution: Optional[CanvasResolution] = None
```

In `backend/app/api/routes_analysis.py`:
`UpdateCandidateRequest` will accept `layout_strategy`, `gameplay_composition`, `split_ratio`, `exclude_chat_overlay`, `caption_preset`, `caption_placement`, and `resolution`, persisting them directly to `candidates.json`.

---

## 5. Frontend Component Design

### 5.1. `CandidateCard.tsx`
- **Reaction Badge:** Render category tag with distinct color accents (e.g., Red for `RAGE`, Purple for `SURPRISE`, Amber for `CHAOTIC_MOMENT`, Blue for `GENERAL_HIGHLIGHT`).
- **Multimodal Score Accordion:** Show:
  - Audio Reaction Surge ($Z$-score and audio reaction score)
  - Streamer Visual Motion score
  - Gameplay Activity score
  - Opening Hook & Climactic Payoff scores
- **Configuration Pill:** Display active layout strategy, split ratio, composition mode, and resolution (e.g., `GAMING_SPLIT 30% • FIT_WITH_BLUR • 1080p`).

### 5.2. `ClipEditorModal.tsx`
- Form fields:
  1. **Clip Title:** Text input.
  2. **Bounds (Start / End):** Numerical inputs in seconds with real-time duration indicator.
  3. **Layout Mode:** Select dropdown for the 6 strategies (default `AUTO_GAMING`).
  4. **Gameplay Composition:** Select dropdown (`AUTO`, `FIT_WITH_BLUR`, `CROP_FILL`) visible when layout is `GAMING_SPLIT`, `AUTO_GAMING`, or `GAMEPLAY_FOCUS` (default `AUTO`).
  5. **Streamer Height Split Ratio:** Interactive range slider (25% to 50%, step 2.5%, default 30%) visible when layout is `GAMING_SPLIT` or `AUTO_GAMING`.
  6. **Exclude Stream Chat Overlay:** Checkbox toggle (default `true`).
  7. **Caption Preset:** Select dropdown for `GAMING_KARAOKE` (Default), `CLEAN`, `MINIMAL`.
  8. **Caption Safe-Zone Placement:** Select dropdown for `AUTO` (Default), `LOWER_CENTER`, `CENTER`, `TOP`, `BOTTOM`.
  9. **Export Quality & Resolution:** Select dropdown for `1080x1920` FHD (Default), `1440x2560` 2K, `2160x3840` 4K.
  10. **Source-Aware Quality Badge:** Computed label indicating `Native / Source-supported` vs `4K — Upscaled from source`.
  11. **Frame Rate Indicator:** Display source FPS.
  12. **Pre-Render Export Summary Card:** Real-time summary card displaying all resolved render parameters.
- **Save & Re-Render:** Updates candidate metadata and triggers single-clip re-render pipeline.

---

## 6. Verification Plan & Test Strategy

1. **Backend Unit Tests (`tests/test_ui_controls_backend.py`):**
   - Test updating candidate clips with layout strategy, split ratio, gameplay composition, chat exclusion, caption preset, caption placement, and resolution via PATCH `/api/projects/{id}/candidates/{clip_id}`.
   - Test validation of split ratio bounds ($0.20 \le \text{ratio} \le 0.60$).
   - Test fallback inheritance in `reframing_service` and `caption_service` when rendering a clip with candidate-level overrides.
   - Test non-destructive cache preservation (transcription and analysis checkpoints remain intact).
2. **Frontend Type Checking & Build Verification:**
   - Run `npm run build` in `frontend/` to ensure full TypeScript compilation and Vite bundling with zero errors.
3. **End-to-End Synthetic Integration Test (`tests/test_gaming_pipeline_e2e.py`):**
   - Automated end-to-end integration test creating a synthetic video, running facecam detection, modular layout reframing with custom split ratio (30%), `FIT_WITH_BLUR` composition, chat overlay exclusion, karaoke caption burning with seam placement, resolution override, and candidate metadata update.
   - All tests pass in the master test suite.
