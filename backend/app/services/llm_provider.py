"""Local LLM provider abstraction for highlight detection using Ollama with robust fallback parsing."""

import json
import re
from typing import List, Dict, Any, Optional
import httpx

from backend.app.core.config import settings
from backend.app.core.logger import logger


class OllamaProvider:
    """Queries local Ollama instance to analyze transcripts and extract highlights."""

    def __init__(self, base_url: Optional[str] = None):
        self.base_url = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")

    async def check_health(self) -> bool:
        """Checks if local Ollama server is running and reachable."""
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                res = await client.get(f"{self.base_url}/api/tags")
                return res.status_code == 200
        except Exception:
            return False

    def build_analysis_prompt(self, window_text: str, start_time: float, end_time: float, target_count: int = 2) -> str:
        """Constructs a strict system prompt directing the LLM to output candidate JSON."""
        return f"""You are an expert short-form video editor for YouTube Shorts, TikTok, and Instagram Reels.
Analyze this video transcript window (timestamp {start_time:.1f}s to {end_time:.1f}s) and extract the top {target_count} most engaging standalone clips.

TRANSCRIPT:
"{window_text}"

CRITERIA FOR A VIRAL CLIP:
1. Hook in the first 3 seconds (curiosity, controversy, surprising statement, question).
2. Standalone story or insight (makes complete sense without watching the rest of the video).
3. High information density or emotional resonance.
4. Duration between 15 and 60 seconds.
5. Exact start and end timestamps must align with natural sentence boundaries within {start_time:.1f}s and {end_time:.1f}s.

You MUST respond strictly with a valid JSON array of objects. Do not include introductory or explanatory conversational text.
Example format:
[
  {{
    "title": "Punchy 3-6 Word Title",
    "start_time": {start_time:.1f},
    "end_time": {min(start_time + 30.0, end_time):.1f},
    "hook_assessment": "Explains why the opening line grabs attention",
    "standalone_context": "Why this thought is self-contained",
    "reasoning": "Why viewers will share or watch to the end",
    "hook_score": 22,
    "clarity_score": 21,
    "density_score": 20,
    "pacing_score": 20
  }}
]
"""

    def parse_llm_json_response(self, raw_text: str, window_start: float, window_end: float) -> List[Dict[str, Any]]:
        """
        Multi-stage deterministic fallback parser that extracts structured candidate JSON
        even if the LLM output is wrapped in markdown code blocks or has syntax defects.
        """
        if not raw_text or not raw_text.strip():
            return []

        text = raw_text.strip()

        # Stage 1: Direct JSON parsing
        try:
            parsed = json.loads(text)
            if isinstance(parsed, list):
                return self._sanitize_candidates(parsed, window_start, window_end)
            if isinstance(parsed, dict) and "candidates" in parsed and isinstance(parsed["candidates"], list):
                return self._sanitize_candidates(parsed["candidates"], window_start, window_end)
        except json.JSONDecodeError:
            pass

        # Stage 2: Extract from markdown codeblock (```json ... ``` or ``` ...)
        codeblock_match = re.search(r"```(?:json)?\s*([\[\{].*?[\]\}])\s*```", text, re.DOTALL)
        if codeblock_match:
            try:
                parsed = json.loads(codeblock_match.group(1).strip())
                if isinstance(parsed, list):
                    return self._sanitize_candidates(parsed, window_start, window_end)
                if isinstance(parsed, dict) and "candidates" in parsed:
                    return self._sanitize_candidates(parsed["candidates"], window_start, window_end)
            except json.JSONDecodeError:
                pass

        # Stage 3: Outermost bracket boundary search
        first_bracket = text.find("[")
        last_bracket = text.rfind("]")
        if first_bracket != -1 and last_bracket != -1 and last_bracket > first_bracket:
            sub = text[first_bracket:last_bracket + 1]
            try:
                parsed = json.loads(sub)
                if isinstance(parsed, list):
                    return self._sanitize_candidates(parsed, window_start, window_end)
            except json.JSONDecodeError:
                pass

        # Stage 4: Regex-based field recovery fallback
        candidates = self._regex_field_recovery(text, window_start, window_end)
        if candidates:
            return candidates

        logger.warning(f"Failed to parse LLM response into candidates. Raw text: {raw_text[:200]}...")
        return []

    def _sanitize_candidates(self, candidates: List[Any], window_start: float, window_end: float) -> List[Dict[str, Any]]:
        """Validates and clamps timestamps within window boundaries."""
        sanitized = []
        for c in candidates:
            if not isinstance(c, dict):
                continue
            title = str(c.get("title", "Engaging Highlight")).strip()
            try:
                start = float(c.get("start_time", window_start))
                end = float(c.get("end_time", window_end))
            except (ValueError, TypeError):
                start, end = window_start, min(window_start + 30.0, window_end)

            # Clamp bounds
            start = max(0.0, start)
            if end <= start:
                end = start + 20.0
            if window_end > 0:
                end = min(end, window_end)

            duration = round(end - start, 2)
            if duration < 5.0:
                continue  # Skip unrealistically tiny clips

            sanitized.append({
                "title": title,
                "start_time": round(start, 2),
                "end_time": round(end, 2),
                "duration": duration,
                "hook_assessment": str(c.get("hook_assessment", "Clear curiosity hook.")),
                "standalone_context": str(c.get("standalone_context", "Context is complete.")),
                "reasoning": str(c.get("reasoning", "Strong engagement potential.")),
                "hook_score": float(c.get("hook_score", 20)),
                "clarity_score": float(c.get("clarity_score", 20)),
                "density_score": float(c.get("density_score", 20)),
                "pacing_score": float(c.get("pacing_score", 20)),
            })
        return sanitized

    def _regex_field_recovery(self, text: str, window_start: float, window_end: float) -> List[Dict[str, Any]]:
        """Fallback regex extraction for deformed JSON."""
        titles = re.findall(r'"title"\s*:\s*"([^"]+)"', text)
        starts = re.findall(r'"start_time"\s*:\s*([0-9\.]+)', text)
        ends = re.findall(r'"end_time"\s*:\s*([0-9\.]+)', text)

        results = []
        for i in range(min(len(titles), len(starts), len(ends))):
            try:
                s = float(starts[i])
                e = float(ends[i])
                if e > s:
                    results.append({
                        "title": titles[i],
                        "start_time": round(s, 2),
                        "end_time": round(e, 2),
                        "duration": round(e - s, 2),
                        "hook_assessment": "Identified through regex recovery",
                        "standalone_context": "Self-contained segment",
                        "reasoning": "High-interest discussion segment",
                        "hook_score": 19,
                        "clarity_score": 19,
                        "density_score": 19,
                        "pacing_score": 19,
                    })
            except ValueError:
                continue
        return results

    async def analyze_transcript_window(
        self,
        window_text: str,
        start_time: float,
        end_time: float,
        model_name: str = "llama3.2:3b"
    ) -> List[Dict[str, Any]]:
        """Queries Ollama HTTP API to extract candidates for a transcript window."""
        is_up = await self.check_health()
        if not is_up:
            logger.info("Ollama is not running. Using heuristic highlight discovery.")
            return self._heuristic_highlight_discovery(window_text, start_time, end_time)

        prompt = self.build_analysis_prompt(window_text, start_time, end_time)
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                res = await client.post(
                    f"{self.base_url}/api/generate",
                    json={
                        "model": model_name,
                        "prompt": prompt,
                        "stream": False,
                        "options": {"temperature": 0.3}
                    }
                )
                if res.status_code == 200:
                    raw_output = res.json().get("response", "")
                    return self.parse_llm_json_response(raw_output, start_time, end_time)
        except Exception as e:
            logger.warning(f"Ollama query failed: {e}. Falling back to heuristic highlight extraction.")

        return self._heuristic_highlight_discovery(window_text, start_time, end_time)

    def _heuristic_highlight_discovery(
        self,
        window_text: str,
        start_time: float,
        end_time: float
    ) -> List[Dict[str, Any]]:
        """Deterministic heuristic extractor for testing or when Ollama is unavailable."""
        duration = end_time - start_time
        clip_duration = min(duration, 30.0)
        clip_start = start_time
        clip_end = start_time + clip_duration

        words = window_text.split()
        summary_title = " ".join(words[:4]).capitalize() if words else "Video Highlight"

        return [{
            "title": summary_title,
            "start_time": round(clip_start, 2),
            "end_time": round(clip_end, 2),
            "duration": round(clip_duration, 2),
            "hook_assessment": "Strong opening sentence introducing key insight.",
            "standalone_context": "Complete conceptual explanation without prerequisites.",
            "reasoning": "High informational value and concise takeaway.",
            "hook_score": 21.0,
            "clarity_score": 22.0,
            "density_score": 20.0,
            "pacing_score": 21.0,
        }]


ollama_provider = OllamaProvider()
