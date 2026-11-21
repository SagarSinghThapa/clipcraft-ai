"""Unit tests for subtitle chunking, SRT/ASS formatting, and styling."""

import unittest
from backend.app.models.transcript import WordTiming
from backend.app.services.caption_service import CaptionService


class TestCaptions(unittest.TestCase):
    def setUp(self):
        self.svc = CaptionService()

    def test_chunk_words_for_clip_relative_timing(self):
        words = [
            WordTiming(word="Building", start=10.0, end=10.5),
            WordTiming(word="modern", start=10.6, end=11.0),
            WordTiming(word="software", start=11.1, end=11.8),
            WordTiming(word="locally", start=12.0, end=12.6),
        ]
        # Clip from 10.0 to 15.0
        chunks = self.svc.chunk_words_for_clip(words, clip_start=10.0, clip_end=15.0, words_per_chunk=2)

        self.assertEqual(len(chunks), 2)
        # First chunk: BUILDING MODERN
        self.assertEqual(chunks[0]["text"], "BUILDING MODERN")
        self.assertEqual(chunks[0]["start"], 0.0)
        self.assertEqual(chunks[0]["end"], 1.0)
        # Second chunk: SOFTWARE LOCALLY
        self.assertEqual(chunks[1]["text"], "SOFTWARE LOCALLY")
        self.assertEqual(chunks[1]["start"], 1.1)
        self.assertEqual(chunks[1]["end"], 2.6)

    def test_generate_srt_format(self):
        chunks = [
            {"text": "HELLO WORLD", "start": 0.5, "end": 2.15},
            {"text": "LOCAL CLIPPING", "start": 2.2, "end": 4.0}
        ]
        srt = self.svc.generate_srt_content(chunks)
        self.assertIn("1\n00:00:00,500 --> 00:00:02,150\nHELLO WORLD", srt)
        self.assertIn("2\n00:00:02,200 --> 00:00:04,000\nLOCAL CLIPPING", srt)

    def test_generate_ass_format(self):
        chunks = [{"text": "VIRAL HIGHLIGHT", "start": 1.25, "end": 3.5}]
        ass = self.svc.generate_ass_content(chunks, margin_v=320)
        self.assertIn("PlayResX: 1080", ass)
        self.assertIn("PlayResY: 1920", ass)
        self.assertIn("320", ass)  # MarginV safe zone
        self.assertIn("Dialogue: 0,0:00:01.25,0:00:03.50,VerticalBold,,0,0,0,,VIRAL HIGHLIGHT", ass)


if __name__ == "__main__":
    unittest.main()
