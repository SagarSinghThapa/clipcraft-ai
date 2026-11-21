"""Unit tests for Phase 12: Animated Word-by-Word Karaoke Captions and Safe-Zone Placement."""

import unittest
from backend.app.models.transcript import WordTiming
from backend.app.models.caption import (
    CaptionPlacement,
    CaptionPreset,
    WordEmphasis,
    StyledWordTiming,
    CaptionChunk,
    CaptionStyleConfig
)
from backend.app.services.caption_service import CaptionService


class TestKaraokeCaptions(unittest.TestCase):
    def setUp(self):
        self.svc = CaptionService()

    def test_source_to_clip_relative_timestamp_conversion(self):
        """Word timestamps must be converted to clip-relative offsets (source_t - clip_start)."""
        words = [
            WordTiming(word="Before", start=150.0, end=152.0),   # Outside clip
            WordTiming(word="What", start=157.57, end=158.00),   # Exactly at clip start
            WordTiming(word="is", start=158.10, end=158.30),
            WordTiming(word="he", start=158.40, end=158.70),
            WordTiming(word="doing", start=158.80, end=159.20),
            WordTiming(word="After", start=180.0, end=182.0),    # Outside clip
        ]
        clip_start = 157.57
        clip_end = 172.58

        chunks = self.svc.chunk_words_for_clip(
            words=words,
            clip_start=clip_start,
            clip_end=clip_end,
            words_per_chunk=4
        )

        self.assertEqual(len(chunks), 1)
        chunk = chunks[0]
        self.assertEqual(chunk.text, "WHAT IS HE DOING")
        self.assertEqual(chunk.start, 0.0)  # 157.57 - 157.57
        self.assertEqual(chunk.end, 1.63)   # 159.20 - 157.57 = 1.63s

        # Verify word relative timings
        words_chunk = chunk.words
        self.assertEqual(len(words_chunk), 4)
        self.assertEqual(words_chunk[0].word, "WHAT")
        self.assertEqual(words_chunk[0].start, 0.0)
        self.assertEqual(words_chunk[1].word, "IS")
        self.assertAlmostEqual(words_chunk[1].start, 0.53, places=2)
        self.assertEqual(words_chunk[2].word, "HE")
        self.assertAlmostEqual(words_chunk[2].start, 0.83, places=2)
        self.assertEqual(words_chunk[3].word, "DOING")
        self.assertAlmostEqual(words_chunk[3].start, 1.23, places=2)

    def test_natural_chunking_2_to_5_words_and_pauses(self):
        """Chunking must respect punctuation breaks and pauses >= 0.40s while bounding length between 2 and 5 words."""
        words = [
            # First sentence / phrase
            WordTiming(word="Look", start=10.0, end=10.3),
            WordTiming(word="at", start=10.4, end=10.6),
            WordTiming(word="that!", start=10.7, end=11.0),   # Punctuation break
            # Pause of 0.8s (11.8 - 11.0)
            WordTiming(word="He", start=11.8, end=12.1),
            WordTiming(word="is", start=12.2, end=12.4),
            WordTiming(word="crashing", start=12.5, end=12.9),
            WordTiming(word="the", start=13.0, end=13.2),
            WordTiming(word="car", start=13.3, end=13.6),
        ]

        chunks = self.svc.chunk_words_for_clip(
            words=words,
            clip_start=10.0,
            clip_end=20.0,
            words_per_chunk=3
        )

        self.assertEqual(len(chunks), 3)
        # First chunk stops at punctuation break / pause
        self.assertEqual(chunks[0].text, "LOOK AT THAT!")
        self.assertEqual(len(chunks[0].words), 3)

        # Second and third chunks group the remaining words into 2-3 word readable mobile chunks
        self.assertEqual(chunks[1].text, "HE IS CRASHING")
        self.assertEqual(len(chunks[1].words), 3)
        self.assertAlmostEqual(chunks[1].start, 1.8, places=2)

        self.assertEqual(chunks[2].text, "THE CAR")
        self.assertEqual(len(chunks[2].words), 2)

        # When words_per_chunk=5, the 5 remaining words are grouped together up to max_words=5
        chunks_5 = self.svc.chunk_words_for_clip(
            words=words,
            clip_start=10.0,
            clip_end=20.0,
            words_per_chunk=5
        )
        self.assertEqual(len(chunks_5), 2)
        self.assertEqual(chunks_5[0].text, "LOOK AT THAT!")
        self.assertEqual(chunks_5[1].text, "HE IS CRASHING THE CAR")
        self.assertEqual(len(chunks_5[1].words), 5)

    def test_karaoke_inline_ass_generation(self):
        """Karaoke mode generates sequential active-word gold overrides and pop tags."""
        words = [
            WordTiming(word="What", start=10.0, end=10.4),
            WordTiming(word="is", start=10.5, end=10.8),
            WordTiming(word="happening", start=10.9, end=11.5),
        ]
        chunks = self.svc.chunk_words_for_clip(words, clip_start=10.0, clip_end=15.0, words_per_chunk=3)

        cfg = CaptionStyleConfig.from_preset(CaptionPreset.GAMING_KARAOKE)
        ass_text = self.svc.generate_ass_content(chunks, style_config=cfg)

        # Style checks
        self.assertIn("Style: VerticalBold,Arial,64,&H00FFFFFF&,&H000000FF,&H00000000&,&H80000000,-1,0,0,0,100,100,1,0,1,5,2", ass_text)

        # 3 words -> 3 sequential dialogue sub-events
        lines = [line for line in ass_text.splitlines() if line.startswith("Dialogue:")]
        self.assertEqual(len(lines), 3)

        # First word active: WHAT in gold + pop, IS HAPPENING in white
        self.assertIn("{\\c&H0000E6FF&\\fscx106\\fscy106}WHAT{\\fscx100\\fscy100} {\\c&H00FFFFFF&}IS HAPPENING", lines[0])

        # Second word active: WHAT in white, IS in gold + pop, HAPPENING in white
        self.assertIn("{\\c&H00FFFFFF&}WHAT {\\c&H0000E6FF&\\fscx106\\fscy106}IS{\\fscx100\\fscy100} {\\c&H00FFFFFF&}HAPPENING", lines[1])

        # Third word active: WHAT IS in white, HAPPENING in gold + pop
        self.assertIn("{\\c&H00FFFFFF&}WHAT IS {\\c&H0000E6FF&\\fscx106\\fscy106}HAPPENING{\\fscx100\\fscy100}", lines[2])

    def test_resolution_aware_ass_styling(self):
        """Font size, outline, and shadow scale proportionally across 1080p, 1440p, and 4K."""
        chunks = [{"text": "TEST", "start": 0.0, "end": 1.0}]

        # 1080x1920 (scale = 1.0)
        ass_1080 = self.svc.generate_ass_content(chunks, canvas_w=1080, canvas_h=1920)
        self.assertIn("PlayResX: 1080", ass_1080)
        self.assertIn("PlayResY: 1920", ass_1080)
        self.assertIn(",Arial,64,&H00FFFFFF&", ass_1080)

        # 1440x2560 (scale = 2560 / 1920 = 1.333) -> font_size ~ 85, outline = 7
        ass_1440 = self.svc.generate_ass_content(chunks, canvas_w=1440, canvas_h=2560)
        self.assertIn("PlayResX: 1440", ass_1440)
        self.assertIn("PlayResY: 2560", ass_1440)
        self.assertIn(",Arial,85,&H00FFFFFF&", ass_1440)

        # 2160x3840 (scale = 3840 / 1920 = 2.0) -> font_size = 128, outline = 10
        ass_4k = self.svc.generate_ass_content(chunks, canvas_w=2160, canvas_h=3840)
        self.assertIn("PlayResX: 2160", ass_4k)
        self.assertIn("PlayResY: 3840", ass_4k)
        self.assertIn(",Arial,128,&H00FFFFFF&", ass_4k)

    def test_clean_and_minimal_presets(self):
        """CLEAN and MINIMAL presets generate static typography without karaoke animation."""
        words = [
            WordTiming(word="Static", start=1.0, end=1.5),
            WordTiming(word="Captions", start=1.6, end=2.0)
        ]
        chunks = self.svc.chunk_words_for_clip(words, clip_start=1.0, clip_end=3.0, uppercase=False)

        cfg_clean = CaptionStyleConfig.from_preset(CaptionPreset.CLEAN)
        self.assertFalse(cfg_clean.karaoke_enabled)
        ass_clean = self.svc.generate_ass_content(chunks, style_config=cfg_clean)
        lines_clean = [l for l in ass_clean.splitlines() if l.startswith("Dialogue:")]
        self.assertEqual(len(lines_clean), 1)
        self.assertNotIn("&H0000E6FF&", lines_clean[0])
        self.assertIn("Static Captions", lines_clean[0])

        cfg_minimal = CaptionStyleConfig.from_preset(CaptionPreset.MINIMAL)
        self.assertFalse(cfg_minimal.karaoke_enabled)
        self.assertEqual(cfg_minimal.font_size, 48)
        ass_minimal = self.svc.generate_ass_content(chunks, style_config=cfg_minimal)
        self.assertIn(",Arial,48,&H00FFFFFF&", ass_minimal)

    def test_dynamic_placement_geometry(self):
        """AUTO placement places subtitles at seam (top_height + 35) when streamer section exists."""
        cfg = CaptionStyleConfig.from_preset(CaptionPreset.GAMING_KARAOKE)

        # With streamer section of height 720 on 1080x1920 canvas
        # margin_v = 720 + 35 = 755, alignment = 8 (Top-Center)
        margin_v, alignment = cfg.get_placement_geometry(canvas_h=1920, top_height=720)
        self.assertEqual(margin_v, 755)
        self.assertEqual(alignment, 8)

        # Single stream (no streamer section, top_height=None)
        # Falls back to BOTTOM safe zone (margin_v = 320, alignment = 2)
        margin_v_none, alignment_none = cfg.get_placement_geometry(canvas_h=1920, top_height=None)
        self.assertEqual(margin_v_none, 320)
        self.assertEqual(alignment_none, 2)


if __name__ == "__main__":
    unittest.main()
