# Research: Phase 13 — Multimodal Reaction Discovery & Causal Gaming Highlight Engine

**Phase:** CLIP-13  
**Date:** 2026-11-20  
**Requirements:** SCORE-01, SCORE-02  
**Target Milestone:** v2.0 (Gaming & Streamer Vertical Reframing Engine)

---

## 1. Executive Vision: Beyond Raw Loudness

In gaming and streamer content (such as GTA gameplay with live streamer facecam and reactions), highlight discovery must **NOT** merely locate loud portions of audio. A loud in-game explosion, sudden gunfire, or blasting background radio music is not an entertaining clip on its own.

**The Primary Goal of Phase 13:**
> **Automatically find funny, surprising, chaotic, rage, fail, and high-energy streamer reaction moments that make sense as standalone vertical Shorts.**

To achieve this locally and efficiently on CPU, Phase 13 implements a **staged multimodal analysis pipeline** fusing:
1. **Audio Reaction Dynamics**: Fast dual-baseline RMS energy (local contrast + global scale), vocal burst clustering, and Whisper speech corroboration to separate human streamer shouting/laughter from game noise.
2. **Transcript Reaction Semantics**: Local Ollama semantic evaluation identifying surprise, disbelief, frustration, rage, celebration, and chaotic banter beyond rigid keyword matching.
3. **Streamer Facecam Visual Motion**: Targeted frame differencing within the Phase 10 persistent facecam region on candidate windows to quantify head turns, body movements, jumping, and leaning.
4. **Gameplay Visual Activity**: Targeted frame differencing within the Phase 11 gameplay region to verify high-motion game events (crashes, chases, action spikes).
5. **Causal Sequence Framing**: Expanding reaction peaks at timestamp $T$ into complete narrative arcs:
   $$\textbf{SETUP } (T - 5\text{ to }12\text{s}) \longrightarrow \textbf{GAMEPLAY EVENT} \longrightarrow \textbf{STREAMER REACTION } (T) \longrightarrow \textbf{PAYOFF } (T + 5\text{ to }20\text{s})$$
6. **Calibrated Multi-Metric Scoring & Anti-Saturation**: Eliminating artificial 100/100/100 ties with non-linear scoring, explicit penalty deductions, and temporal Non-Maximum Suppression (NMS) deduplication.

---

## 2. Audio Reaction Dynamics: Dual Baselining & Speech Corroboration

### 2.1 Fast $O(N)$ Cumulative Sum Moving-Window RMS
On 16kHz 16-bit mono PCM audio (`audio.wav`), moving-window RMS is computed using double-precision cumulative sums:
$$S[n] = x[n]^2, \quad C[k] = \sum_{j=0}^{k-1} S[j], \quad C[0] = 0$$
$$\text{RMS}[m] = \sqrt{\frac{C[k + N] - C[k]}{N}}$$
- Window size: $T_w = 500\text{ms}$ ($N = 8,000$ samples)
- Step size: $T_{\text{step}} = 250\text{ms}$ ($H = 4,000$ samples, 50% overlap)
- **Benchmark:** 35 minutes of audio ($33.4 \times 10^6$ samples) processes in **0.178 seconds** on standard CPU.

### 2.2 Global Baseline vs. Local Surrounding Baseline
A streamer's vocal dynamics drift across a long stream. A sudden outburst after quiet dialogue is far more engaging than sustained elevated noise during an intro:
1. **Global Track Statistics:**
   $$\mu_{\text{global}} = \frac{1}{M} \sum_{m=0}^{M-1} \text{RMS}[m], \quad \sigma_{\text{global}} = \sqrt{\frac{1}{M} \sum_{m=0}^{M-1} (\text{RMS}[m] - \mu_{\text{global}})^2}$$
   $$Z_{\text{global}}[m] = \frac{\text{RMS}[m] - \mu_{\text{global}}}{\sigma_{\text{global}}}$$
2. **Local Surrounding Baseline ($T \pm 5\text{s}$):**
   For window $m$, let $L_m$ be the surrounding 10-second neighborhood ($\pm 5\text{s}$, excluding the center $1\text{s}$):
   $$\mu_{\text{local}}[m] = \text{mean}(\text{RMS}[L_m]), \quad \sigma_{\text{local}}[m] = \text{std}(\text{RMS}[L_m])$$
   $$\Delta_{\text{local}}[m] = \frac{\text{RMS}[m] - \mu_{\text{local}}[m]}{\max(0.01, \sigma_{\text{local}}[m])}$$
3. **Surge Condition:**
   A window is a true reaction surge candidate if:
   $$Z_{\text{global}}[m] \ge 2.0 \quad \text{AND} \quad \Delta_{\text{local}}[m] \ge 2.5$$

### 2.3 Speech Corroboration: Discriminating Human Screams from Game SFX
A car explosion in GTA creates high RMS without human speech. To avoid false positives:
- Cross-reference audio surge window $m$ with Whisper word timestamps from `transcript.json`.
- If word density or speech activity occurs within $[t_m - 0.5\text{s}, t_m + 1.0\text{s}]$, flag as **Confirmed Vocal Surge**.
- If no speech occurs within 2.0 seconds of an isolated loudness spike, apply a **Non-Speech Noise Penalty** ($0.5\times$ attenuation to audio score).
- Detect sudden silence immediately followed by explosive speech (classic jumpscare / shock reaction pattern).

---

## 3. Staged Performance Architecture (Targeted Video Analysis)

Running full-frame computer vision across a 35-minute 60fps video (126,000 frames) on CPU is prohibitive. ClipCraft solves this with a staged funnel:

```
Full Video (35 min)
   │
   ▼
[Stage 1: Cheap Global Audio & Transcript Analysis]
   │  - Fast cumulative sum RMS (0.18s)
   │  - Dual-baseline Z-score surge peaks (Z >= 2.0)
   │  - Ollama transcript window semantic evaluation
   │
   ▼
[Stage 2: Candidate Reaction Hotspot Clustering]
   │  - Merge nearby audio surges and semantic hooks into ~8-15 hotspot windows
   │
   ▼
[Stage 3: Targeted Visual Differencing on Shortlist ONLY]
   │  - Streamer Facecam region (Phase 10 box): Sample 2 fps for ~30s (60 frames)
   │  - Gameplay region (Phase 11 box): Sample 2 fps for ~30s (60 frames)
   │  - Compute motion magnitude & visual change spikes in milliseconds
   │
   ▼
[Stage 4: Causal Sequence Boundary Snapping]
   │  - Setup (T - 5..12s) -> Event -> Reaction (T) -> Payoff (T + 5..20s)
   │  - Snap to Whisper sentence endpoints and speech pauses
   │  - Enforce clip bounds: min 20s, max 60s
   │
   ▼
[Stage 5: Multimodal Scoring, Saturation Calibration & Deduplication]
   │  - Compute weighted composite score (0-100)
   │  - Apply penalty deductions
   │  - Suppress overlapping candidates via temporal NMS
   │
   ▼
Top High-Impact Gaming Shorts Candidates
```

---

## 4. Visual Evidence Extraction on Shortlisted Windows

### 4.1 Streamer Facecam Visual Reaction Score ($0-100$)
Using the Phase 10 persistent facecam coordinates `(wx, wy, ww, wh)`:
- Sample frames inside candidate clip $[t_{\text{start}}, t_{\text{end}}]$ at 2 fps.
- Crop `frame[wy:wy+wh, wx:wx+ww]`.
- Convert to grayscale, downsample to $160\times90$.
- Compute normalized absolute frame difference:
  $$D_{\text{cam}}[k] = \frac{1}{A} \sum |I_k - I_{k-1}|$$
- High motion peaks inside the facecam (jumping, head back laughter, hands on head, sudden lean) generate visual spikes distinct from steady speaking.
- Map peak and variance of $D_{\text{cam}}$ to `StreamerVisualReactionScore: 0-100`.

### 4.2 Gameplay Activity Score ($0-100$)
Using the Phase 11 gameplay crop region:
- Sample gameplay frames at 2 fps across the candidate window.
- Compute frame differencing and optical variance outside the facecam mask.
- A sudden scene change, vehicle collision, or rapid camera whip produces a clear spike in gameplay motion immediately preceding or coinciding with the streamer's reaction.
- Map to `GameplayActivityScore: 0-100`.

---

## 5. Causal Reaction Sequence Framing

A reaction clip without context is confusing and disorienting. Every high-performing Short must tell a micro-story:

$$\begin{array}{|c|c|c|c|}
\hline
\textbf{SETUP} & \textbf{GAMEPLAY EVENT} & \textbf{STREAMER REACTION} & \textbf{PAYOFF} \\
\text{T - 12s to T - 4s} & \text{T - 4s to T} & \text{T to T + 6s} & \text{T + 6s to T + 18s} \\
\hline
\text{Calm dialogue, goal,} & \text{Unexpected crash, kill,} & \text{Shout, laugh, scream,} & \text{Punchline, disbelief,} \\
\text{anticipation, plan} & \text{NPC glitch, failure} & \text{physical jump, banter} & \text{resolution, recovery} \\
\hline
\end{array}$$

### 5.1 Temporal Boundary Refinement
Given reaction peak timestamp $T$:
1. **Search Window**: Look for setup starting at $T - 12\text{s}$ and payoff ending at $T + 20\text{s}$ (preliminary range: 32s).
2. **Sentence Snapping**:
   - Snap start time to the beginning of the Whisper sentence nearest to $T - 8\text{s}$.
   - Snap end time to the end of the sentence following the reaction punchline.
3. **Duration Clamping**:
   - Hard Minimum Duration: 20.0s (never produce micro-fragments).
   - Preferred Duration: 25.0s – 45.0s.
   - Hard Maximum Duration: 60.0s (platform limit for YouTube Shorts).
   - If sentence snapping yields $< 20.0\text{s}$, expand outward to adjacent speech segments.
   - If snapping yields $> 60.0\text{s}$, trim low-activity tail while preserving sentence integrity.

---

## 6. Reaction Categories & Typology

Phase 13 classifies candidates into actionable gaming categories:
```python
class ReactionCategory(str, Enum):
    FUNNY_REACTION = "FUNNY_REACTION"      # Laughter, mockery, hilarious fails
    SURPRISE = "SURPRISE"                  # Jumpscares, sudden unexpected events
    CHAOTIC_MOMENT = "CHAOTIC_MOMENT"      # Multi-vehicle pileups, madness, glitch
    FAIL = "FAIL"                          # Player death, mission failed, blown up
    RAGE = "RAGE"                          # Desk slam, shouting in frustration, anger
    EPIC_MOMENT = "EPIC_MOMENT"            # Insane clutch, miracle escape, stunt
    WIN = "WIN"                            # Mission passed, high-stakes victory
    FUNNY_DIALOGUE = "FUNNY_DIALOGUE"      # Witty banter, absurd NPC conversation
    STORY_MOMENT = "STORY_MOMENT"          # Cinematic plot twist, dramatic cutscene
    GENERAL_HIGHLIGHT = "GENERAL_HIGHLIGHT"# Standard notable engagement
```

Priority weighting during ranking favors: `FUNNY_REACTION`, `SURPRISE`, `CHAOTIC_MOMENT`, `FAIL`, and `RAGE`.

---

## 7. Anti-Saturation Scoring Calibration & Penalties

### 7.1 The Saturation Problem in v1.0
In v1.0, candidates scored 100/100/100 because additive factors easily saturated max caps. This provided zero ranking value.

### 7.2 Non-Linear Calibrated Multimodal Score
The new scoring architecture calculates a balanced composite:
$$\text{Base Score} = \sum_{k} w_k \cdot S_k - \text{Penalties}$$
Where:
- $w_{\text{transcript}} = 0.25$ (Context, dialogue quality, topic coherence)
- $w_{\text{hook}} = 0.20$ (First 3-5 seconds grab)
- $w_{\text{audio}} = 0.20$ (Dual-baseline vocal surge & intensity)
- $w_{\text{streamer\_motion}} = 0.15$ (Facecam body/head movement)
- $w_{\text{gameplay\_motion}} = 0.10$ (Game visual activity spike)
- $w_{\text{payoff}} = 0.10$ (Punchline, resolution, closure)

$$\sum w_k = 1.00$$

### 7.3 Calibrated Non-Linear Transformation
To ensure 100 is exceptionally rare and differentiate 90 from 75:
$$\text{Raw Score} = \text{clamp}\left(\text{Base Score}, 10.0, 98.0\right)$$
Apply a soft compression above 85:
$$\text{Calibrated Score} = \begin{cases} 
\text{Raw Score} & \text{if } \text{Raw Score} \le 80 \\
80 + 15 \times \tanh\left(\frac{\text{Raw Score} - 80}{15}\right) & \text{if } \text{Raw Score} > 80
\end{cases}$$
This naturally spaces high-scoring candidates across $[75, 94]$, reserving scores $\ge 95$ for phenomenal all-signal peaks.

### 7.4 Explicit Penalties
- **Dead Air Penalty (-10 to -20)**: Gaps $> 3.5\text{s}$ without speech or action in the setup or payoff.
- **Missing Setup Penalty (-15)**: Clip begins immediately with shouting without showing what triggered it.
- **Abrupt Cutoff Penalty (-15)**: Clip ends mid-reaction before the resolution or laughter subsides.
- **Game Music / Noise Dominance Penalty (-15)**: Loud audio with zero human vocal presence.
- **Overlong / Sluggish Pacing Penalty (-10)**: Excessive filler dialogue between setup and reaction.

---

## 8. Duplicate Candidate Suppression (Temporal NMS)

Multiple reaction peaks often occur within the same 60-second gameplay sequence. Generating multiple overlapping cuts is confusing and wasteful.

**Temporal NMS Algorithm:**
1. Sort candidate sequences by `total_score` descending.
2. Maintain an accepted candidates list.
3. For candidate $C_i$, calculate temporal Intersection-over-Union (IoU) with all accepted candidates $C_j$:
   $$\text{Overlap}(C_i, C_j) = \frac{\max(0, \min(C_i.\text{end}, C_j.\text{end}) - \max(C_i.\text{start}, C_j.\text{start}))}{\min(C_i.\text{duration}, C_j.\text{duration})}$$
4. If $\text{Overlap} > 0.40$ (or time distance between centers $< 15\text{s}$), suppress $C_i$ as a duplicate.
5. Result: Distinct, non-overlapping, high-impact Shorts spanning different moments of the stream.

---

## 9. Downstream Phase 12 Linkage: Caption Reaction Tagging

Phase 12 established `WordEmphasis.REACTION` (rendering active words with 112% pop and intense gold illumination).
- Phase 13 identifies exact timestamp intervals of confirmed vocal surges: $[t_{\text{surge\_start}}, t_{\text{surge\_end}}]$.
- When `CaptionService.chunk_words_for_clip` processes words, words that overlap a confirmed reaction surge are tagged `WordEmphasis.REACTION`.
- The energetic punchline words (*"WHAT?!"*, *"NO WAY!"*, *"HE'S GONE!"*) dynamically pop with 112% scale while standard speech stays at 106% pop.

---

## 10. Summary of Architectural Flow

```
1. Ingest audio.wav (16kHz mono)
2. AudioEnergyService -> compute cumulative sum RMS + dual baselines (global + local)
3. Identify confirmed vocal surges (Z_global >= 2.0 & Delta_local >= 2.5 & speech present)
4. Correlate with Ollama transcript reaction semantic evaluation
5. CausalSequenceService -> expand around peaks (Setup -> Event -> Reaction -> Payoff)
6. Enforce clip duration bounds (20s - 60s) & sentence endpoint snapping
7. StreamerVisualReactionService & GameplayActivityService -> compute visual motion on shortlist
8. ScoringService -> compute calibrated multimodal score (0-100) with penalties
9. Deduplicate via Temporal NMS
10. Persist to candidates.json, checkpoint_audio_energy.json, and link to Phase 12 WordEmphasis.REACTION
```
