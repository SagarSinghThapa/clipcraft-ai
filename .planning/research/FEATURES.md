# Feature Research

**Domain:** Local AI Video Clipping Application
**Researched:** 2026-11-19
**Confidence:** HIGH

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Local Video Ingestion | Users have local files on disk (MP4, MOV, MKV, WebM) | LOW | Validate file existence, read metadata (resolution, duration, fps, codecs) via `ffprobe` |
| YouTube Ingestion | Users want to clip talks, podcasts, and streams from URLs | MEDIUM | Use `yt-dlp` to download best video+audio format without bypassing security or DRM |
| Speech-to-Text Transcription | Needed to identify highlight topics and timing | HIGH | Local Whisper with word-level & segment timestamps; cached locally |
| Highlight Detection | Core value: AI suggests engaging clips | HIGH | Structured prompt to local LLM, parsing start/end times and engagement rationale |
| Exact Video Cutting | Creates standalone clips from timestamps | MEDIUM | FFmpeg seeking and trimming; keyframe re-encoding to avoid black frames or frozen audio |
| 9:16 Vertical Reframing | Shorts, Reels, TikTok format requires 1080x1920 | HIGH | Compute crop window, center on speaker face, smooth trajectory, fall back to center crop |
| Synchronized Captions | Short-form videos require burned-in readable captions | HIGH | Generate subtitle events, chunk into short phrases (1-4 words), apply vertical positioning & styling |
| Preview & Export UI | Users must inspect candidates before final export | MEDIUM | Interactive web interface with video player, score indicators, and download triggers |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but valuable.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| 100% Free & Local-First | No SaaS subscriptions, no API key fees, privacy preserved | MEDIUM | Entire pipeline runs offline / on-device |
| Explainable Engagement Score | User understands *why* a clip was chosen | MEDIUM | Score breakdown (Hook, Density, Clarity, Emotional value) |
| Active-Speaker / Face Smoothing | Eliminates jarring crop jumps across frames | HIGH | Exponential moving average (EMA) or Kalman filtering on crop coordinates |
| Dynamic Word Highlighting | TikTok/Reels style karaoke caption effect | HIGH | ASS / FFmpeg filter highlighting current spoken word |
| Lightweight Clip Trimming | Tweak clip bounds directly in web UI | LOW | Adjust start/end seconds and re-render without re-transcribing |
| Stage Caching & Resumability | Instant re-clipping if a later step fails | LOW | Checkpoint storage: source -> audio -> transcript -> candidates -> clips |

### Anti-Features (Commonly Requested, Often Problematic)

Features that seem good but create problems.

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| "Predict Viral Hits" Claim | Marketing hype | Virality is governed by distribution algorithms and audience timing, not pure audio text | Label as "Engagement & Content Quality Score" |
| Fixed-Interval Video Slicing | Easy to implement | Cuts sentences mid-word, destroys semantic flow | Transcribe first, detect natural sentence boundaries |
| Full Cloud SaaS Architecture | Perceived scalability | Introduces expensive hosting, bandwidth limits, privacy concerns | Local-first desktop/server workflow |
| Full Multitrack NLE Editor | Feature richness | Massive complexity, bugs, bloated UI distracting from automated clipping | Lightweight start/end trim & caption editor |

## Feature Dependencies

```
[Local Video / YouTube URL]
       ↓
[Audio Extraction (WAV)]
       ↓
[Whisper Transcription] (cached)
       ↓
[Transcript Segmentation]
       ↓
[Local AI Highlight Detection & Scoring]
       ↓
[Candidate Clip Selection & Review]
       ↓
[FFmpeg Video Cutting]
       ↓
[Face Detection & 9:16 Smooth Crop]
       ↓
[Synchronized Caption Burning]
       ↓
[Playable 1080x1920 MP4 Export]
```

## MVP Definition

### Launch With (v1)

- [x] Ingestion of local video files (MP4, MOV, MKV, WebM) & YouTube URLs via `yt-dlp`
- [x] Audio extraction (16kHz mono WAV)
- [x] Local transcription using faster-whisper with word & segment timestamps (cached)
- [x] Transcript segmentation & Ollama prompt engineering for candidate extraction
- [x] Robust fallback parser for LLM JSON output
- [x] Multi-factor candidate scoring (0-100) with hook and context rationale
- [x] FFmpeg cutting & MP4 generation
- [x] 9:16 vertical reframing with face detection & EMA motion smoothing (center-crop fallback)
- [x] Synchronized vertical captions with outline/shadow burned into MP4
- [x] Interactive web dashboard (Import, Live Stage Progress, Candidate Preview & Review, Clip Export)
- [x] Start/end trim adjustments & title editing
- [x] Hardware capability detection (CPU / CUDA)

### Add After Validation (v1.x)

- [ ] Advanced multi-speaker dynamic side-by-side / vertical split framing
- [ ] Word-by-word karaoke bouncing animation presets
- [ ] Batch processing of multiple source videos

### Future Consideration (v2+)

- [ ] Automatic B-roll / overlay insertion from keywords
- [ ] Background music ducking and synthesis
- [ ] Direct publishing integrations (YouTube Shorts / TikTok API)

## Sources

- Review of leading video clipping SaaS architectures (OpusClip, Klap, Munch)
- User requirements and feedback for local content creation tooling
- Open-source media processing and automated captioning guidelines
