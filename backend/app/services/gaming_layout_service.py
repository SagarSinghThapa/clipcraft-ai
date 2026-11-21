"""Dual-stream FFmpeg compositing engine for stacked streamer/gameplay vertical compositions."""

import subprocess
from pathlib import Path
from typing import Optional, List, Dict, Any

from backend.app.core.config import settings
from backend.app.core.logger import logger
from backend.app.models.facecam import FacecamRegion
from backend.app.models.layout import (
    LayoutStrategy,
    CanvasResolution,
    GamingLayoutConfig,
    CanvasDimensions,
    GameplayCompositionMode,
    ExcludedRegion,
)
from backend.app.services.gameplay_crop_service import gameplay_crop_service
from backend.app.services.storage_service import storage_service
from backend.app.utils.ffmpeg_utils import escape_ffmpeg_path, probe_media_metadata


class GamingLayoutService:
    """Manages multi-region vertical layout generation, strategy resolution, and dual-stream filtergraphs."""

    def resolve_strategy(
        self,
        strategy: LayoutStrategy,
        facecam: Optional[FacecamRegion]
    ) -> LayoutStrategy:
        """
        Resolves AUTO_GAMING into an explicit concrete strategy (GAMING_SPLIT or GAMEPLAY_FOCUS)
        based on streamer facecam detection status and confidence threshold.
        """
        if strategy != LayoutStrategy.AUTO_GAMING:
            return strategy

        if facecam is not None and facecam.is_detected and facecam.confidence >= 0.40:
            return LayoutStrategy.GAMING_SPLIT
        return LayoutStrategy.GAMEPLAY_FOCUS

    def build_filtergraph(
        self,
        config: GamingLayoutConfig,
        source_w: int,
        source_h: int,
        facecam: Optional[FacecamRegion] = None,
        gameplay_crop_x: Optional[int] = None
    ) -> str:
        """
        Constructs an FFmpeg filtercomplex string for the specified layout configuration.
        Ensures exact aspect ratio preservation without distortion or stretching.
        """
        resolved_strategy = self.resolve_strategy(config.strategy, facecam)
        dims = config.get_dimensions()
        target_w = dims.width
        target_h = dims.height
        top_h = dims.top_height
        bottom_h = dims.bottom_height

        if resolved_strategy == LayoutStrategy.GAMING_SPLIT:
            top_aspect = target_w / top_h

            # 1. Streamer Facecam Region (Top) - strictly preserve top_aspect for zero stretching
            if facecam and facecam.is_detected:
                cx = facecam.x + (facecam.width / 2.0)
                cy = facecam.y + (facecam.height / 2.0)

                # Match top_aspect so scaling scale_x == scale_y (zero distortion)
                raw_w = facecam.width
                raw_h = facecam.height
                if raw_w / raw_h < top_aspect:
                    raw_w = raw_h * top_aspect
                else:
                    raw_h = raw_w / top_aspect

                cam_h = gameplay_crop_service._round_even(raw_h)
                cam_w = gameplay_crop_service._round_even(cam_h * top_aspect)

                if cam_w > source_w:
                    cam_w = source_w - (source_w % 2)
                    cam_h = gameplay_crop_service._round_even(cam_w / top_aspect)
                if cam_h > source_h:
                    cam_h = source_h - (source_h % 2)
                    cam_w = gameplay_crop_service._round_even(cam_h * top_aspect)

                cam_x = max(0, min(source_w - cam_w, int(round(cx - (cam_w / 2.0)))))
                cam_y = max(0, min(source_h - cam_h, int(round(cy - (cam_h / 2.0)))))

                # Guard against including bottom sub counter / overlays directly under facecam
                if cam_y + cam_h > facecam.y + facecam.height + 25:
                    cam_y = max(0, facecam.y + facecam.height + 25 - cam_h)

                cam_x = cam_x if cam_x % 2 == 0 else cam_x - 1
                cam_y = cam_y if cam_y % 2 == 0 else cam_y - 1
            else:
                # Fallback to upper-right quadrant
                cam_h = gameplay_crop_service._round_even(source_h * 0.30)
                cam_w = gameplay_crop_service._round_even(cam_h * top_aspect)
                cam_x = max(0, source_w - cam_w - 20)
                cam_x = cam_x if cam_x % 2 == 0 else cam_x - 1
                cam_y = 20

            # 2. Excluded Overlay Regions (Stream Chat / Comments)
            excluded = list(config.excluded_overlay_regions or [])
            if config.exclude_chat_overlay and not any(r.label == "chat_overlay" for r in excluded):
                chat_reg = gameplay_crop_service.detect_chat_overlay_region(source_w=source_w, source_h=source_h)
                if chat_reg:
                    excluded.append(chat_reg)

            clean_x, clean_y, clean_w, clean_h = gameplay_crop_service.calculate_clean_gameplay_bounds(
                source_w=source_w,
                source_h=source_h,
                excluded_regions=excluded
            )

            # 3. Resolve Gameplay Composition Mode (CROP_FILL vs FIT_WITH_BLUR vs AUTO)
            comp_mode = config.gameplay_composition
            if comp_mode == GameplayCompositionMode.AUTO:
                target_aspect = target_w / bottom_h
                clean_aspect = clean_w / clean_h
                if clean_aspect > target_aspect:
                    crop_w = int(clean_h * target_aspect)
                    loss_ratio = (clean_w - crop_w) / clean_w
                    if loss_ratio > 0.25:
                        comp_mode = GameplayCompositionMode.FIT_WITH_BLUR
                    else:
                        comp_mode = GameplayCompositionMode.CROP_FILL
                else:
                    comp_mode = GameplayCompositionMode.CROP_FILL

            # 4. Construct Dual-Stream Filtergraph
            if comp_mode == GameplayCompositionMode.FIT_WITH_BLUR:
                filtergraph = (
                    f"[0:v]split=3[cam_in][game_bg_in][game_fg_in]; "
                    f"[cam_in]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale={target_w}:{top_h}:flags=lanczos[cam_out]; "
                    f"[game_bg_in]crop={clean_w}:{clean_h}:{clean_x}:{clean_y},scale={target_w}:{bottom_h},boxblur=25:5[game_bg]; "
                    f"[game_fg_in]crop={clean_w}:{clean_h}:{clean_x}:{clean_y},scale={target_w}:-2:flags=lanczos[game_fg]; "
                    f"[game_bg][game_fg]overlay=(W-w)/2:(H-h)/2[game_out]; "
                    f"[cam_out][game_out]vstack=inputs=2[v_out]"
                )
                return filtergraph
            else:
                # CROP_FILL: Crop clean gameplay region to exact target aspect ratio
                game_w, game_h = gameplay_crop_service.calculate_gameplay_crop_dimensions(
                    source_w=clean_w,
                    source_h=clean_h,
                    target_w=target_w,
                    target_h=bottom_h
                )
                max_game_x = max(0, clean_w - game_w)
                if gameplay_crop_x is not None:
                    game_x = clean_x + max(0, min(gameplay_crop_x, max_game_x))
                else:
                    game_x = clean_x + (max_game_x // 2)
                game_x = game_x if game_x % 2 == 0 else game_x - 1
                game_y = clean_y + ((clean_h - game_h) // 2)
                game_y = game_y if game_y % 2 == 0 else game_y - 1

                filtergraph = (
                    f"[0:v]split=2[cam_in][game_in]; "
                    f"[cam_in]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale={target_w}:{top_h}:flags=lanczos[cam_out]; "
                    f"[game_in]crop={game_w}:{game_h}:{game_x}:{game_y},scale={target_w}:{bottom_h}:flags=lanczos[game_out]; "
                    f"[cam_out][game_out]vstack=inputs=2[v_out]"
                )
                return filtergraph

        elif resolved_strategy == LayoutStrategy.GAMEPLAY_FOCUS:
            if config.blur_background:
                # Blurred background extension with centered gameplay
                filtergraph = (
                    f"[0:v]split=2[bg_in][fg_in]; "
                    f"[bg_in]scale={target_w}:{target_h},boxblur=20:5[bg_out]; "
                    f"[fg_in]scale={target_w}:-2[fg_out]; "
                    f"[bg_out][fg_out]overlay=(W-w)/2:(H-h)/2[v_out]"
                )
            else:
                # Direct content-aware 9:16 vertical crop
                crop_w = int(round(source_h * 9.0 / 16.0))
                crop_w = crop_w if crop_w % 2 == 0 else crop_w - 1
                crop_h = source_h
                max_x = max(0, source_w - crop_w)
                crop_x = min(max_x, gameplay_crop_x if gameplay_crop_x is not None else max_x // 2)
                crop_x = crop_x if crop_x % 2 == 0 else crop_x - 1
                filtergraph = (
                    f"[0:v]crop={crop_w}:{crop_h}:{crop_x}:0,scale={target_w}:{target_h}:flags=lanczos[v_out]"
                )
            return filtergraph

        elif resolved_strategy == LayoutStrategy.STREAMER_FOCUS:
            if facecam and facecam.is_detected:
                cam_x = facecam.x
                cam_y = facecam.y
                cam_w = facecam.width
                cam_h = facecam.height
            else:
                cam_w = int(round(source_w * 0.35))
                cam_h = int(round(source_h * 0.45))
                cam_x = source_w - cam_w - 20
                cam_y = 20

            # Streamer webcam scaled in foreground with blurred gameplay background
            filtergraph = (
                f"[0:v]split=2[bg_in][fg_in]; "
                f"[bg_in]scale={target_w}:{target_h},boxblur=25:5[bg_out]; "
                f"[fg_in]crop={cam_w}:{cam_h}:{cam_x}:{cam_y},scale={target_w}:-2:flags=lanczos[fg_out]; "
                f"[bg_out][fg_out]overlay=(W-w)/2:(H-h)/2[v_out]"
            )
            return filtergraph

        else:
            # Fallback to 9:16 center crop
            crop_w = int(round(source_h * 9.0 / 16.0))
            crop_w = crop_w if crop_w % 2 == 0 else crop_w - 1
            crop_x = max(0, (source_w - crop_w) // 2)
            crop_x = crop_x if crop_x % 2 == 0 else crop_x - 1
            return f"[0:v]crop={crop_w}:{source_h}:{crop_x}:0,scale={target_w}:{target_h}:flags=lanczos[v_out]"

    def build_ffmpeg_command(
        self,
        source_path: Path,
        output_path: Path,
        config: GamingLayoutConfig,
        source_w: int,
        source_h: int,
        facecam: Optional[FacecamRegion] = None,
        gameplay_crop_x: Optional[int] = None,
        start_sec: Optional[float] = None,
        duration_sec: Optional[float] = None
    ) -> List[str]:
        """Assembles the exact FFmpeg command argument list for safe subprocess execution."""
        filtergraph = self.build_filtergraph(
            config=config,
            source_w=source_w,
            source_h=source_h,
            facecam=facecam,
            gameplay_crop_x=gameplay_crop_x
        )

        cmd = ["ffmpeg", "-y"]

        if start_sec is not None:
            cmd.extend(["-ss", f"{start_sec:.3f}"])
        if duration_sec is not None:
            cmd.extend(["-t", f"{duration_sec:.3f}"])

        cmd.extend(["-i", str(source_path)])
        cmd.extend(["-filter_complex", filtergraph])
        cmd.extend([
            "-map", "[v_out]",
            "-map", "0:a?",
            "-c:v", "libx264",
            "-crf", "18",
            "-preset", "fast",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "192k",
            "-avoid_negative_ts", "make_zero",
            str(output_path)
        ])
        return cmd

    def render_layout_clip(
        self,
        source_path: Path,
        output_path: Path,
        config: GamingLayoutConfig,
        source_w: int,
        source_h: int,
        facecam: Optional[FacecamRegion] = None,
        gameplay_crop_x: Optional[int] = None,
        start_sec: Optional[float] = None,
        duration_sec: Optional[float] = None,
        force_recompute: bool = False
    ) -> Path:
        """Executes FFmpeg to render the modular vertical composition."""
        if output_path.exists() and output_path.stat().st_size > 1024 and not force_recompute:
            logger.info(f"Reusing cached layout clip: {output_path}")
            return output_path

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if gameplay_crop_x is None and source_path.exists():
            try:
                import cv2
                cap = cv2.VideoCapture(str(source_path), cv2.CAP_FFMPEG)
                ret1, f1 = cap.read()
                ret2, f2 = cap.read()
                cap.release()
                if ret1 and ret2 and f1 is not None and f2 is not None:
                    game_w, _ = gameplay_crop_service.calculate_gameplay_crop_dimensions(
                        source_w, source_h, config.get_dimensions().width, config.get_dimensions().bottom_height
                    )
                    gameplay_crop_x = gameplay_crop_service.estimate_activity_x(
                        cv2.absdiff(f1, f2), game_w, facecam
                    )
            except Exception as e:
                logger.warning(f"Could not auto-estimate gameplay activity X: {e}")

        cmd = self.build_ffmpeg_command(
            source_path=source_path,
            output_path=output_path,
            config=config,
            source_w=source_w,
            source_h=source_h,
            facecam=facecam,
            gameplay_crop_x=gameplay_crop_x,
            start_sec=start_sec,
            duration_sec=duration_sec
        )

        logger.info(f"Executing gaming layout FFmpeg render -> {output_path.name}")
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if proc.returncode != 0:
            logger.error(f"FFmpeg layout rendering failed: {proc.stderr}")
            raise RuntimeError(f"FFmpeg layout render failed with exit code {proc.returncode}: {proc.stderr}")

        if not output_path.exists() or output_path.stat().st_size == 0:
            raise RuntimeError(f"Rendered layout video not found or 0 bytes: {output_path}")

        # Save layout metadata for downstream caption positioning
        try:
            import json
            dims = config.get_dimensions()
            info_file = output_path.parent / "layout_info.json"
            with open(info_file, "w", encoding="utf-8") as f:
                json.dump({
                    "strategy": config.strategy.value,
                    "resolution": config.resolution.value,
                    "top_height": dims.top_height,
                    "bottom_height": dims.bottom_height,
                    "width": dims.width,
                    "height": dims.height,
                    "split_ratio": config.split_ratio
                }, f, indent=2)
        except Exception as e:
            logger.warning(f"Could not write layout_info.json: {e}")

        logger.info(f"Successfully rendered gaming layout vertical video ({output_path.stat().st_size} bytes)")
        return output_path


gaming_layout_service = GamingLayoutService()
