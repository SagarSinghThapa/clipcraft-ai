# Phase 10: Streamer Facecam Detection & Spatial Clustering - Research

**Phase:** Phase 10 (CLIP-10)  
**Requirements:** `FACE-01`, `FACE-02`, `FACE-03`  

---

## 1. Problem Definition & Domain Constraints

In gaming and streamer videos (GTA V, reaction streams, esports), creators embed a webcam box directly over gameplay footage. 
To convert these landscape videos into a vertical stacked format (**Top: Facecam / Bottom: Gameplay**), ClipCraft must:
1. Locate where the streamer webcam box is located without requiring manual coordinate entry.
2. Distinguish the streamer's persistent face from transient gameplay faces (e.g., cutscenes, NPC dialogue, pedestrians).
3. Extract the webcam region cleanly with appropriate padding for gestures, microphone, and headroom.
4. Execute efficiently: do NOT process every frame of a 30–60 minute video.

---

## 2. Algorithm Design: Low-Cost Spatial Clustering

### Step 1: Low-Frequency Frame Sampling
- For a source video of duration $T$, sample 1 frame every $\Delta t = 2.5$ seconds (capped at $N_{\max} = 150$ samples).
- Using OpenCV `VideoCapture` seeking by timestamp (`CAP_PROP_POS_MSEC`) or sampling evenly spaced frames avoids decoding the entire video stream.
- Total processing time: under 3–5 seconds on CPU.

### Step 2: Face Detection
- Run OpenCV's pre-trained Haar cascade (`haarcascade_frontalface_default.xml`) or DNN face detector on each sampled frame.
- Record `(x, y, w, h, timestamp)` for all detected faces.

### Step 3: Spatial Persistence & Quadrant Clustering
- Normalize face centroids: $c_x = (x + w/2) / W$, $c_y = (y + h/2) / H$.
- Categorize detections by quadrant:
  - `TOP_LEFT` ($c_x < 0.5, c_y < 0.5$)
  - `TOP_RIGHT` ($c_x \ge 0.5, c_y < 0.5$)
  - `BOTTOM_LEFT` ($c_x < 0.5, c_y \ge 0.5$)
  - `BOTTOM_RIGHT` ($c_x \ge 0.5, c_y \ge 0.5$)
- Compute cluster statistics for each quadrant:
  - Detection count $N_q$
  - Persistence ratio: $P_q = N_q / N_{\text{total frames with faces}}$
  - Spatial standard deviation: $\sigma_x, \sigma_y$
- Streamer Facecam Criteria:
  - $P_q \ge 0.30$ (detected in at least 30% of face frames).
  - Low spatial variance: $\sigma_x < 0.08, \sigma_y < 0.08$ (the face stays within a localized webcam box).
  - Relatively small face size: $w < 0.35 \times W$ (eliminating full-screen webcam reaction moments).

### Step 4: Facecam Crop Box Expansion & Padding
- Let median face box be $(f_x, f_y, f_w, f_h)$.
- Expand boundaries to capture full webcam box (torso, microphone, gestures, headroom):
  - $w_{\text{cam}} = \text{round}(f_w \times 2.0)$
  - $h_{\text{cam}} = \text{round}(f_h \times 2.2)$
  - Constrain aspect ratio (e.g. 16:9 or 4:3 widescreen webcam):
    $$\text{Ensure } w_{\text{cam}} / h_{\text{cam}} \approx 1.5 - 1.77$$
  - Anchor crop center around $(f_x + f_w/2, f_y + f_h/2 + 0.15 \times f_h)$ to allow natural headroom.
  - Clamp strictly within `[0, W]` and `[0, H]`.
  - Ensure even dimensions (divisible by 2 for H.264).

---

## 3. Data Structures & Caching

### Model: `FacecamRegion`
```python
class FacecamRegion(BaseModel):
    is_detected: bool = False
    x: int = 0
    y: int = 0
    width: int = 0
    height: int = 0
    confidence: float = 0.0
    quadrant: str = "NONE"  # TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT, CENTER
    sample_count: int = 0
```

### Checkpoint Persistence
- Stored in `projects/<id>/metadata/checkpoint_facecam.json`.
- Injected into `Project.metadata.facecam_region` for instantaneous frontend display and downstream Phase 11 layout compositing.
