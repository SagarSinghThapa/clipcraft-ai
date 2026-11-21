---
phase: CLIP-03-ai-highlight-detection-explainable-scoring
plan: "01"
subsystem: ai-analysis-and-scoring
tags: [ollama, llm, highlight-detection, transcript-segmentation, scoring]

requires:
  - phase: CLIP-02-audio-extraction-local-speech-transcription
    provides: FullTranscript with sentence and word timestamps
provides:
  - "Transcript segmentation service strictly aligned with sentence endpoints"
  - "Ollama local LLM highlight discovery provider with multi-stage fallback parsing"
  - "Explainable multi-factor scoring algorithm (0-100)"
  - "API endpoints for highlight analysis, candidate querying, and fine-tuning"
affects: [Phase 4 Precision Video Clipping, Phase 7 Web Interface]

tech-stack:
  added: [httpx, regex, json]
  patterns:
    - "Overlapping analysis windows without mid-sentence cuts"
    - "Multi-stage fallback parser (direct JSON -> markdown block -> bracket boundary -> regex)"
    - "Multi-factor explainable scoring matrix (hook, clarity, density, pacing)"

key-files:
  created:
    - backend/app/models/candidate.py
    - backend/app/services/segmentation_service.py
    - backend/app/services/llm_provider.py
    - backend/app/services/scoring_service.py
    - backend/app/services/analysis_service.py
    - backend/app/api/routes_analysis.py
    - tests/test_analysis.py
    - tests/test_scoring.py
  modified:
    - backend/app/main.py

key-decisions:
  - "Default local LLM to Ollama (llama3.2:3b / mistral) with zero cloud fees"
  - "Guarantee candidate discovery even when LLM output is malformed via 4-stage parser"
  - "Explicitly explain scores without misleading virality guarantees"

requirements-completed: [AI-01, AI-02, AI-03, AI-04, SCORE-01, SCORE-02]

duration: 20min
completed: 2026-11-19
---

# Phase 3: AI Highlight Detection & Explainable Scoring Summary

**Delivered transcript segmentation aligned to sentence boundaries, local LLM highlight extraction via Ollama with multi-stage fallback parsing, and an explainable 4-factor scoring rubric.**

## Accomplishments
1. **Semantic Segmentation**: `SegmentationService` groups transcripts into 30–90 second windows with 10s overlaps, ensuring sentence boundaries remain intact.
2. **Local LLM Extraction**: `OllamaProvider` crafts focused system prompts for short-form video discovery and features a 4-tier fallback parser that recovers valid candidates from raw JSON, markdown code blocks, bracket boundaries, or regex patterns.
3. **Explainable Scoring Engine**: `ScoringService` evaluates hook strength, standalone clarity, information density, and pacing (each 0–25) to produce a 0–100 score with human-readable rationale.
4. **Interactive Adjustment API**: Created `/api/projects/{id}/analyze`, `/api/projects/{id}/candidates`, and `/api/projects/{id}/candidates/{clip_id}` allowing clients to fine-tune timestamps, titles, and render selections.
