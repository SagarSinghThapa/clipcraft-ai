# Pitfalls Research

**Domain:** Local AI Video Clipper & Reframer
**Researched:** 2026-11-19
**Confidence:** HIGH

## Critical Pitfalls

### Pitfall 1: Audio/Video Desync and Blank Frames on FFmpeg Cuts

**What goes wrong:**
Using `-c copy` (stream copy) with fast seek (`-ss`) cuts at nearest keyframes (I-frames), causing 1-3 seconds of frozen video with playing audio, or audio/video drift.

**Why it happens:**
Keyframes in long-form YouTube or H.264 videos may only occur every 2 to 5 seconds. If a clip starts at 00:15.3 and the keyframe is at 00:13.0, stream copying drops or duplicates frames until the next I-frame.

**How to avoid:**
Use accurate seeking and force re-encoding for final cuts:
`ffmpeg -ss {start} -to {end} -i {source} -c:v libx264 -preset fast -crf 18 -c:a aac -b:a 192k -avoid_negative_ts make_zero {output}`

**Warning signs:**
Black frames or audio starting 2 seconds before video moves in generated clips.

**Phase to address:**
Phase 4 (Clipping & Media Processing).

---

### Pitfall 2: Hallucinated Timestamps or Malformed JSON from Local LLM

**What goes wrong:**
Smaller local models (e.g., 3B parameter models) frequently output markdown-wrapped JSON, broken syntax, or timestamps that exceed the actual video duration or start after they end.

**Why it happens:**
Prompt drift, token length limits, or hallucinated numbers.

**How to avoid:**
1. Multi-stage JSON sanitization (strip backticks, regex extraction).
2. Strict Pydantic model validation.
3. Timestamp bounds validation (`0 <= start < end <= video_duration`).
4. Fallback heuristic segmentation based on silence/speech density if LLM fails completely.

**Warning signs:**
`JSONDecodeError` in logs, clips with negative durations or 0-second length.

**Phase to address:**
Phase 3 (AI Highlight Detection & Analysis).

---

### Pitfall 3: Nauseating Camera Jitter in Vertical 9:16 Cropping

**What goes wrong:**
If face detection runs on every frame and the crop box snaps to the detected center immediately, micro-movements, breathing, or minor detector noise cause aggressive screen jitter.

**Why it happens:**
Direct frame-by-frame crop assignment without spatial or temporal filtering.

**How to avoid:**
1. Sample face detection at intervals (e.g. 5-10 fps) rather than every raw 60fps frame.
2. Apply Exponential Moving Average (EMA) smoothing or deadzone windowing: only move the crop window if the speaker's face moves outside the inner 20% safe zone.
3. Fallback safely to center-crop if face confidence drops below threshold for >1.5 seconds.

**Warning signs:**
Shaky, jittery video previews where the crop oscillates rapidly.

**Phase to address:**
Phase 5 (Vertical Reframing & Subject Tracking).

---

### Pitfall 4: Subtitle Font Rendering and Encoding Failures on Windows

**What goes wrong:**
FFmpeg's `subtitles` or `ass` filter fails on Windows due to unescaped Windows backslashes (`C:\path\...`), missing font configurations, or fontconfig cache locks.

**Why it happens:**
FFmpeg filter syntax interprets `:` and `\` as escape characters. `C:\path\file.ass` gets parsed as filter `C` with argument `\path...`.

**How to avoid:**
1. Escape Windows paths for FFmpeg filter arguments: convert `\` to `/` and escape colons (`C\:/...` or relative paths).
2. Bundle a standard, highly legible font (e.g., Arial, Roboto, or Inter) or use FFmpeg's `drawtext` with relative font files.

**Warning signs:**
`Unable to parse filtergraph` or `No font found` errors when burning captions.

**Phase to address:**
Phase 6 (Captioning & Subtitle Rendering).

---

### Pitfall 5: Memory Exhaustion (OOM) on Large Videos

**What goes wrong:**
Loading entire 2-hour video files into memory, holding uncompressed OpenCV video frames in RAM lists, or running massive Whisper models simultaneously with Ollama on 8GB RAM machines.

**Why it happens:**
Assuming infinite RAM and holding streaming objects in global state.

**How to avoid:**
1. Only extract and hold 16kHz mono audio during transcription.
2. OpenCV processes frames as an iterator generator, computing crop coordinates and discarding pixel buffers immediately.
3. Default to lightweight model profiles (`faster-whisper` base/small, `llama3.2:3b` / `qwen2.5:3b`) with explicit CPU quantization (`int8`).

**Warning signs:**
System freezing, Python process terminated by OS OOM killer.

**Phase to address:**
Phase 2 (Audio & Transcription) & Phase 5 (Reframing).

## "Looks Done But Isn't" Checklist

- [ ] **FFmpeg Cuts:** Often looks done with `-c copy`, but first 2 seconds have audio with frozen black picture — verify frame-accurate re-encode.
- [ ] **YouTube Ingestion:** Often works on simple video, but crashes on age-restricted or live streams — verify descriptive error handling.
- [ ] **Captions:** Often looks fine in video center, but gets cut off by TikTok/Shorts UI overlays (comments, like buttons) — verify safe margin spacing.
- [ ] **LLM Responses:** Often works on prompt test, but fails on real 45-minute transcript because token window overflows — verify chunked segmentation before prompting.
