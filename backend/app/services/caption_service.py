"""Synchronized vertical subtitle generation, styling, and FFmpeg filtergraph burning."""

import math
import subprocess
import json
from pathlib import Path
from typing import List, Dict, Any, Optional, Union, Tuple

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.models.candidate import CandidateClip
from backend.app.models.transcript import WordTiming, FullTranscript
from backend.app.models.caption import (
    CaptionPlacement,
    CaptionPreset,
    WordEmphasis,
    StyledWordTiming,
    CaptionChunk,
    CaptionStyleConfig
)
from backend.app.models.layout import GamingLayoutConfig, LayoutStrategy
from backend.app.services.storage_service import storage_service
from backend.app.services.transcription_service import transcription_service
from backend.app.services.analysis_service import analysis_service
from backend.app.utils.ffmpeg_utils import is_ffmpeg_available, escape_ffmpeg_path, probe_media_metadata


class CaptionService:
    """Chunks word timestamps into vertical subtitle events and burns them into MP4 video."""

    def format_timestamp_srt(self, seconds: float) -> str:
        """Formats floating-point seconds into SRT time: HH:MM:SS,mmm."""
        sec = max(0.0, seconds)
        hours = int(sec // 3600)
        minutes = int((sec % 3600) // 60)
        secs = int(sec % 60)
        millis = int(round((sec - int(sec)) * 1000))
        return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

    def format_timestamp_ass(self, seconds: float) -> str:
        """Formats floating-point seconds into ASS time: H:MM:SS.cc."""
        sec = max(0.0, seconds)
        hours = int(sec // 3600)
        minutes = int((sec % 3600) // 60)
        secs = int(sec % 60)
        centis = int(round((sec - int(sec)) * 100))
        return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"

    def chunk_words_for_clip(
        self,
        words: List[WordTiming],
        clip_start: float,
        clip_end: float,
        words_per_chunk: int = 3,
        uppercase: bool = True,
        max_pause_sec: float = 0.40,
        min_words: int = 2,
        max_words: int = 5,
        confirmed_surge_windows: Optional[List[Tuple[float, float]]] = None,
    ) -> List[CaptionChunk]:
        """
        Filters words belonging to the candidate clip range [clip_start, clip_end],
        normalizes timestamps to relative clip time (0.00s start),
        and groups words into 2-5 word readable vertical caption chunks,
        respecting inter-word pauses and punctuation boundaries.
        Words overlapping confirmed_surge_windows receive WordEmphasis.REACTION (112% pop).
        """
        styled_words: List[StyledWordTiming] = []
        for w in words:
            # Skip words outside clip range
            if w.end <= clip_start or w.start >= clip_end:
                continue

            rel_start = max(0.0, round(w.start - clip_start, 2))
            rel_end = max(rel_start + 0.05, round(min(clip_end, w.end) - clip_start, 2))
            raw_text = w.word.strip()
            if not raw_text:
                continue

            emphasis = WordEmphasis.NORMAL
            if raw_text.endswith("!") or (raw_text.isupper() and len(raw_text) > 1):
                emphasis = WordEmphasis.STRONG

            # Check if this word falls within any confirmed reaction surge window
            if confirmed_surge_windows:
                for s_start, s_end in confirmed_surge_windows:
                    if (s_start <= w.start <= s_end) or (s_start <= w.end <= s_end) or (w.start <= s_start and w.end >= s_end):
                        emphasis = WordEmphasis.REACTION
                        break

            display_text = raw_text.upper() if uppercase else raw_text
            styled_words.append(
                StyledWordTiming(
                    word=display_text,
                    start=rel_start,
                    end=rel_end,
                    emphasis=emphasis,
                    probability=getattr(w, "probability", 1.0)
                )
            )

        if not styled_words:
            fallback_text = "HIGHLIGHT CLIP" if uppercase else "Highlight Clip"
            fallback_end = max(1.0, round(clip_end - clip_start, 2))
            return [CaptionChunk(text=fallback_text, start=0.0, end=fallback_end, words=[])]

        chunks: List[CaptionChunk] = []
        current_group: List[StyledWordTiming] = []

        for i, word in enumerate(styled_words):
            current_group.append(word)

            if i == len(styled_words) - 1:
                break

            next_word = styled_words[i + 1]
            inter_word_gap = next_word.start - word.end
            current_len = len(current_group)

            should_break = False
            if current_len >= max_words:
                should_break = True
            elif inter_word_gap >= max_pause_sec and current_len >= 1:
                should_break = True
            elif any(word.word.endswith(p) for p in [".", "?", "!"]) and current_len >= min_words:
                should_break = True
            elif current_len >= words_per_chunk:
                # Lookahead: if only 1 word remains before phrase boundary, absorb it if within max_words
                remaining_in_phrase = 1
                if i + 2 < len(styled_words):
                    gap_after_next = styled_words[i + 2].start - next_word.end
                    if gap_after_next < max_pause_sec:
                        remaining_in_phrase = 2

                if remaining_in_phrase == 1 and current_len + 1 <= max_words:
                    should_break = False
                else:
                    should_break = True

            if should_break:
                chunk_text = " ".join(w.word for w in current_group)
                chunk_start = current_group[0].start
                chunk_end = current_group[-1].end
                chunks.append(
                    CaptionChunk(
                        text=chunk_text,
                        start=chunk_start,
                        end=chunk_end,
                        words=list(current_group)
                    )
                )
                current_group = []

        if current_group:
            chunk_text = " ".join(w.word for w in current_group)
            chunk_start = current_group[0].start
            chunk_end = current_group[-1].end
            chunks.append(
                CaptionChunk(
                    text=chunk_text,
                    start=chunk_start,
                    end=chunk_end,
                    words=list(current_group)
                )
            )

        return chunks

    def generate_srt_content(self, chunks: List[Any]) -> str:
        """Generates standard .srt format subtitle text."""
        lines = []
        for idx, chunk in enumerate(chunks, 1):
            start = chunk["start"] if isinstance(chunk, dict) else chunk.start
            end = chunk["end"] if isinstance(chunk, dict) else chunk.end
            text = chunk["text"] if isinstance(chunk, dict) else chunk.text
            start_str = self.format_timestamp_srt(start)
            end_str = self.format_timestamp_srt(end)
            lines.append(f"{idx}\n{start_str} --> {end_str}\n{text}\n")
        return "\n".join(lines)

    def generate_ass_content(
        self,
        chunks: List[Any],
        style_config: Optional[CaptionStyleConfig] = None,
        canvas_w: int = 1080,
        canvas_h: int = 1920,
        top_height: Optional[int] = None,
        font_size: Optional[int] = None,
        font_name: Optional[str] = None,
        primary_color: Optional[str] = None,
        outline_color: Optional[str] = None,
        margin_v: Optional[int] = None,
    ) -> str:
        """
        Generates Advanced SubStation Alpha (.ass) format with high-contrast
        bold typography, active-word karaoke overrides, and safe placement zones.
        """
        if style_config is None:
            style_config = CaptionStyleConfig.from_preset(CaptionPreset.GAMING_KARAOKE)

        # Apply backward-compatible explicit parameter overrides if present
        updates = {}
        if font_size is not None:
            updates["font_size"] = font_size
        if font_name is not None:
            updates["font_name"] = font_name
        if primary_color is not None:
            updates["primary_color"] = primary_color
        if outline_color is not None:
            updates["outline_color"] = outline_color
        if updates:
            style_config = style_config.model_copy(update=updates)

        scaled_config = style_config.get_scaled_config(canvas_h=canvas_h)

        if margin_v is not None:
            effective_margin_v = margin_v
            alignment = 2
        else:
            effective_margin_v, alignment = scaled_config.get_placement_geometry(
                canvas_h=canvas_h, top_height=top_height
            )

        header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {canvas_w}
PlayResY: {canvas_h}
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: VerticalBold,{scaled_config.font_name},{scaled_config.font_size},{scaled_config.primary_color},&H000000FF,{scaled_config.outline_color},&H80000000,-1,0,0,0,100,100,1,0,1,{scaled_config.outline_width},{scaled_config.shadow_offset},{alignment},40,40,{effective_margin_v},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
        dialogue_lines = []
        for chunk in chunks:
            chunk_start = chunk["start"] if isinstance(chunk, dict) else chunk.start
            chunk_end = chunk["end"] if isinstance(chunk, dict) else chunk.end
            chunk_text = chunk["text"] if isinstance(chunk, dict) else chunk.text
            words = chunk.get("words", []) if isinstance(chunk, dict) else getattr(chunk, "words", [])

            if not scaled_config.karaoke_enabled or not words:
                start_ass = self.format_timestamp_ass(chunk_start)
                end_ass = self.format_timestamp_ass(chunk_end)
                dialogue_lines.append(
                    f"Dialogue: 0,{start_ass},{end_ass},VerticalBold,,0,0,0,,{chunk_text}"
                )
            else:
                num_words = len(words)
                for i, word in enumerate(words):
                    w_start = word["start"] if isinstance(word, dict) else word.start
                    w_end = word["end"] if isinstance(word, dict) else word.end
                    w_emphasis = word.get("emphasis", WordEmphasis.NORMAL) if isinstance(word, dict) else getattr(word, "emphasis", WordEmphasis.NORMAL)

                    sub_start = min(chunk_start, w_start) if i == 0 else w_start
                    if i < num_words - 1:
                        next_w = words[i + 1]
                        next_w_start = next_w["start"] if isinstance(next_w, dict) else next_w.start
                        sub_end = max(w_end, next_w_start)
                    else:
                        sub_end = max(chunk_end, w_end)

                    if sub_end <= sub_start:
                        sub_end = sub_start + 0.10

                    start_ass = self.format_timestamp_ass(sub_start)
                    end_ass = self.format_timestamp_ass(sub_end)

                    pop_pct = scaled_config.active_pop_percent
                    if w_emphasis == WordEmphasis.REACTION:
                        pop_pct = min(25, pop_pct + 6)
                    elif w_emphasis == WordEmphasis.STRONG:
                        pop_pct = min(20, pop_pct + 2)

                    pop_tag = f"\\fscx{100 + pop_pct}\\fscy{100 + pop_pct}" if pop_pct > 0 else ""
                    pop_reset = "\\fscx100\\fscy100" if pop_pct > 0 else ""

                    line_parts = []
                    if i > 0:
                        before_text = " ".join(
                            (w["word"] if isinstance(w, dict) else w.word)
                            for w in words[:i]
                        )
                        line_parts.append(f"{{\\c{scaled_config.primary_color}}}{before_text}")

                    active_word_str = word["word"] if isinstance(word, dict) else word.word
                    line_parts.append(f"{{\\c{scaled_config.highlight_color}{pop_tag}}}{active_word_str}{{{pop_reset}}}")

                    if i < num_words - 1:
                        after_text = " ".join(
                            (w["word"] if isinstance(w, dict) else w.word)
                            for w in words[i + 1:]
                        )
                        line_parts.append(f"{{\\c{scaled_config.primary_color}}}{after_text}")

                    line_str = " ".join(line_parts)
                    dialogue_lines.append(
                        f"Dialogue: 0,{start_ass},{end_ass},VerticalBold,,0,0,0,,{line_str}"
                    )

        return header + "\n".join(dialogue_lines) + "\n"

    def burn_captions_for_clip(
        self,
        project_id: str,
        candidate: CandidateClip,
        force_recompute: bool = False,
        style_config: Optional[CaptionStyleConfig] = None,
        top_height: Optional[int] = None
    ) -> Path:
        """
        Generates synchronized ASS/SRT subtitles and burns them into 9:16 vertical video
        using FFmpeg, outputting projects/<id>/clips/<clip_id>/final_clip.mp4.
        """
        dirs = storage_service.init_project_workspace(project_id)
        clip_dir = dirs["clips"] / candidate.id

        reframed_video = clip_dir / "reframed.mp4"
        if not reframed_video.exists():
            # Fall back to raw_clip if reframing was skipped
            reframed_video = clip_dir / "raw_clip.mp4"
            if not reframed_video.exists():
                raise FileNotFoundError(f"No source clip found for candidate '{candidate.id}'. Cut clip first.")

        final_clip = clip_dir / "final_clip.mp4"
        srt_file = clip_dir / "captions.srt"
        ass_file = clip_dir / "captions.ass"
        caption_settings_file = clip_dir / "caption_settings.json"

        if style_config is None:
            preset = getattr(candidate, "caption_preset", None) or CaptionPreset.GAMING_KARAOKE
            style_config = CaptionStyleConfig.from_preset(preset)
        elif getattr(candidate, "caption_preset", None) and style_config.preset == CaptionPreset.GAMING_KARAOKE:
            style_config = CaptionStyleConfig.from_preset(candidate.caption_preset)

        # Check candidate placement override
        if getattr(candidate, "caption_placement", None) and style_config.placement == CaptionPlacement.AUTO:
            style_config = style_config.model_copy(update={"placement": candidate.caption_placement})

        # Probe canvas dimensions from reframed video
        canvas_w = 1080
        canvas_h = 1920
        try:
            meta = probe_media_metadata(reframed_video)
            if meta.width > 0 and meta.height > 0:
                canvas_w = meta.width
                canvas_h = meta.height
        except Exception as e:
            logger.warning(f"Could not probe reframed video metadata for clip '{candidate.id}': {e}")

        # Resolve top_height for dynamic seam placement if placement is AUTO
        effective_top_height = top_height
        if style_config.placement == CaptionPlacement.AUTO and effective_top_height is None:
            # Check candidate explicit split_ratio first
            if getattr(candidate, "split_ratio", None) is not None:
                raw_top = int(round(canvas_h * candidate.split_ratio))
                effective_top_height = raw_top if raw_top % 2 == 0 else raw_top + 1
            else:
                # 1. Try reading clip-level layout_info.json
                layout_info_file = clip_dir / "layout_info.json"
                if layout_info_file.exists():
                    try:
                        with open(layout_info_file, "r", encoding="utf-8") as f:
                            linfo = json.load(f)
                        strat = linfo.get("strategy")
                        if strat in (LayoutStrategy.GAMING_SPLIT.value, LayoutStrategy.AUTO_GAMING.value):
                            effective_top_height = linfo.get("top_height")
                    except Exception as e:
                        logger.warning(f"Failed to read layout_info.json: {e}")

                # 2. Try reading project checkpoint_facecam.json
                if effective_top_height is None:
                    cached_facecam = storage_service.load_stage_checkpoint(project_id, "facecam")
                    if cached_facecam and cached_facecam.get("is_detected"):
                        cfg_layout = GamingLayoutConfig(strategy=LayoutStrategy.GAMING_SPLIT)
                        effective_top_height = cfg_layout.get_dimensions().top_height

        # Check caching: reuse final_clip if settings match and not force_recompute
        current_settings = style_config.model_dump()
        current_settings["effective_top_height"] = effective_top_height
        current_settings["canvas_w"] = canvas_w
        current_settings["canvas_h"] = canvas_h

        if final_clip.exists() and final_clip.stat().st_size > 0 and not force_recompute:
            if caption_settings_file.exists():
                try:
                    with open(caption_settings_file, "r", encoding="utf-8") as f:
                        cached_settings = json.load(f)
                    if cached_settings == current_settings:
                        logger.info(f"Reusing cached final captioned clip ({style_config.preset.value}): {final_clip}")
                        return final_clip
                except Exception:
                    pass

        if not is_ffmpeg_available():
            raise RuntimeError("FFmpeg is required to burn captions into video.")

        # Extract words for this clip
        transcript = transcription_service.load_cached_transcript(project_id)
        all_words: List[WordTiming] = []
        if transcript:
            for seg in transcript.segments:
                all_words.extend(seg.words)

        chunks = self.chunk_words_for_clip(
            words=all_words,
            clip_start=candidate.start_time,
            clip_end=candidate.end_time,
            words_per_chunk=style_config.words_per_chunk,
            uppercase=style_config.uppercase
        )

        # Write SRT and ASS files
        srt_content = self.generate_srt_content(chunks)
        with open(srt_file, "w", encoding="utf-8") as f:
            f.write(srt_content)

        ass_content = self.generate_ass_content(
            chunks=chunks,
            style_config=style_config,
            canvas_w=canvas_w,
            canvas_h=canvas_h,
            top_height=effective_top_height
        )
        with open(ass_file, "w", encoding="utf-8") as f:
            f.write(ass_content)

        escaped_ass = escape_ffmpeg_path(ass_file)

        # Build FFmpeg command to burn captions
        # Subtitles filter syntax: ass='filename'
        filter_str = f"ass='{escaped_ass}'"
        cmd = [
            settings.FFMPEG_PATH,
            "-y",
            "-i", str(reframed_video),
            "-vf", filter_str,
            "-c:v", "libx264",
            "-preset", "fast",
            "-crf", "18",
            "-c:a", "copy",
            "-movflags", "+faststart",
            str(final_clip)
        ]

        logger.info(f"Burning synchronized captions ({style_config.preset.value}) for clip '{candidate.title}'...")
        try:
            subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            logger.warning(f"ASS subtitle burn failed: {e.stderr}. Attempting SRT fallback...")
            # Fallback to standard subtitles filter
            escaped_srt = escape_ffmpeg_path(srt_file)
            fallback_cmd = [
                settings.FFMPEG_PATH,
                "-y",
                "-i", str(reframed_video),
                "-vf", f"subtitles='{escaped_srt}'",
                "-c:v", "libx264",
                "-preset", "fast",
                "-crf", "18",
                "-c:a", "copy",
                "-movflags", "+faststart",
                str(final_clip)
            ]
            try:
                subprocess.run(fallback_cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as err:
                logger.error(f"Subtitle burning failed completely: {err.stderr}")
                raise RuntimeError(f"Caption burning failed: {err.stderr}")

        if not final_clip.exists() or final_clip.stat().st_size == 0:
            raise RuntimeError("Final clip was not created or is empty.")

        # Save settings for non-destructive cache checking
        with open(caption_settings_file, "w", encoding="utf-8") as f:
            json.dump(current_settings, f, indent=2)

        storage_service.save_stage_checkpoint(project_id, "captions", {
            "clip_id": candidate.id,
            "preset": style_config.preset.value,
            "placement": style_config.placement.value,
            "karaoke_enabled": style_config.karaoke_enabled,
            "effective_top_height": effective_top_height,
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "final_clip_path": str(final_clip)
        })

        candidate.rendered_clip_path = str(final_clip)
        logger.info(f"Final captioned clip rendered: {final_clip} ({round(final_clip.stat().st_size / (1024 * 1024), 2)} MB)")
        return final_clip

    def burn_all_selected_clips(
        self,
        project_id: str,
        force_recompute: bool = False,
        style_config: Optional[CaptionStyleConfig] = None
    ) -> List[Path]:
        """Renders final captioned clips for all selected candidate highlights."""
        candidates_data = analysis_service.load_cached_candidates(project_id)
        if not candidates_data or not candidates_data.candidates:
            raise ValueError(f"No candidate highlights available for project '{project_id}'.")

        rendered: List[Path] = []
        for candidate in candidates_data.candidates:
            if candidate.selected_for_rendering:
                p = self.burn_captions_for_clip(
                    project_id,
                    candidate,
                    force_recompute=force_recompute,
                    style_config=style_config
                )
                rendered.append(p)

        # Update candidates.json with rendered paths
        c_path = analysis_service.get_candidates_path(project_id)
        with open(c_path, "w", encoding="utf-8") as f:
            f.write(candidates_data.model_dump_json(indent=2))

        storage_service.save_stage_checkpoint(project_id, "captions", {
            "rendered_count": len(rendered),
            "clips": [str(p) for p in rendered],
            "preset": style_config.preset.value if style_config else CaptionPreset.GAMING_KARAOKE.value
        })
        return rendered


caption_service = CaptionService()
