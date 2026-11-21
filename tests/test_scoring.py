"""Unit tests for fallback LLM response parsing and candidate scoring."""

import unittest
from backend.app.services.llm_provider import OllamaProvider
from backend.app.services.scoring_service import ScoringService


class TestScoringAndParser(unittest.TestCase):
    def setUp(self):
        self.provider = OllamaProvider()
        self.scoring = ScoringService()

    def test_parser_markdown_codeblock(self):
        raw_llm = """Here are the top clips for your video:
```json
[
  {
    "title": "Secret to Viral Clips",
    "start_time": 12.0,
    "end_time": 42.0,
    "hook_assessment": "Great curiosity hook",
    "standalone_context": "Full insight",
    "reasoning": "High retention",
    "hook_score": 24,
    "clarity_score": 23,
    "density_score": 22,
    "pacing_score": 21
  }
]
```
Hope this helps!"""

        parsed = self.provider.parse_llm_json_response(raw_llm, 10.0, 50.0)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["title"], "Secret to Viral Clips")
        self.assertEqual(parsed[0]["start_time"], 12.0)
        self.assertEqual(parsed[0]["end_time"], 42.0)

    def test_parser_regex_fallback_on_corrupt_json(self):
        corrupt_text = """
        "title": "Corrupt JSON Highlight",
        "start_time": 15.5,
        "end_time": 45.0,
        some broken text without closing brackets...
        """
        parsed = self.provider.parse_llm_json_response(corrupt_text, 10.0, 50.0)
        self.assertEqual(len(parsed), 1)
        self.assertEqual(parsed[0]["title"], "Corrupt JSON Highlight")
        self.assertEqual(parsed[0]["start_time"], 15.5)
        self.assertEqual(parsed[0]["end_time"], 45.0)

    def test_scoring_service_bounds_and_explanation(self):
        candidate_data = {
            "title": "Test Clip",
            "duration": 30.0,
            "hook_score": 24.0,
            "clarity_score": 23.0,
            "density_score": 22.0,
            "pacing_score": 21.0
        }
        score = self.scoring.compute_candidate_score(candidate_data)
        self.assertGreaterEqual(score.total_score, 80)
        self.assertLessEqual(score.total_score, 100)
        self.assertIn("compelling opening hook", score.explanation)


if __name__ == "__main__":
    unittest.main()
