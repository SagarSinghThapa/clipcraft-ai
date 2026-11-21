"""Service for calculating non-distorting gameplay crop dimensions, facecam masking, and activity-aware trajectory tracking."""

from typing import List, Tuple, Optional, Union
import numpy as np

from backend.app.core.logger import logger
from backend.app.models.facecam import FacecamRegion
from backend.app.models.layout import GameplayCropWindow, CanvasDimensions, ExcludedRegion


class GameplayCropService:
    """Calculates optimal content-aware gameplay crop windows for stacked vertical compositions."""

    @staticmethod
    def _round_even(val: float) -> int:
        """Rounds a float to the nearest even integer, required for FFmpeg encoders."""
        n = int(round(val))
        return n if n % 2 == 0 else n + 1

    def calculate_gameplay_crop_dimensions(
        self,
        source_w: int,
        source_h: int,
        target_w: int,
        target_h: int
    ) -> Tuple[int, int]:
        """
        Calculates the crop sub-rectangle dimensions from the source video to fill
        the target region with zero stretching or aspect ratio distortion.
        """
        if source_w <= 0 or source_h <= 0 or target_w <= 0 or target_h <= 0:
            raise ValueError("All dimensions must be positive non-zero integers.")

        target_ratio = target_w / target_h
        source_ratio = source_w / source_h

        if target_ratio <= source_ratio:
            # Target is narrower or equal to source (typical for vertical/stacked gaming):
            # Fit full height, crop width
            crop_h = source_h
            raw_w = source_h * target_ratio
            crop_w = self._round_even(raw_w)
            if crop_w > source_w:
                crop_w = self._round_even(source_w)
        else:
            # Target is wider than source:
            # Fit full width, crop height
            crop_w = source_w
            raw_h = source_w / target_ratio
            crop_h = self._round_even(raw_h)
            if crop_h > source_h:
                crop_h = self._round_even(source_h)

        # Ensure dimensions stay within bounds and are even
        crop_w = max(2, min(crop_w, source_w - (source_w % 2)))
        crop_h = max(2, min(crop_h, source_h - (source_h % 2)))

        return crop_w, crop_h

    def detect_chat_overlay_region(
        self,
        frame: Optional[np.ndarray] = None,
        source_w: int = 1920,
        source_h: int = 1080
    ) -> Optional[ExcludedRegion]:
        """
        Detects persistent side chat or comment overlays along the screen boundary.
        Analyzes edge density and variance in the right 15-20% strip of the frame.
        """
        if frame is not None:
            try:
                import cv2
                h, w = frame.shape[:2]
                right_bound = int(w * 0.82)
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
                strip = gray[0:min(h, 600), right_bound:w]
                lap = cv2.Laplacian(strip, cv2.CV_64F)
                stds = np.std(lap, axis=0)

                for idx, s in enumerate(stds):
                    if s > 15.0:
                        chat_x = self._round_even(right_bound + idx)
                        return ExcludedRegion(
                            x=chat_x,
                            y=0,
                            width=w - chat_x,
                            height=h,
                            label="chat_overlay"
                        )
            except Exception as e:
                logger.warning(f"Error analyzing frame for chat overlay: {e}")

        # Fallback heuristic for standard 1920x1080 streams with right-side chat
        if source_w >= 1920:
            return ExcludedRegion(
                x=1700,
                y=0,
                width=source_w - 1700,
                height=source_h,
                label="chat_overlay"
            )
        elif source_w >= 1280:
            chat_w = int(source_w * 0.11)
            return ExcludedRegion(
                x=source_w - chat_w,
                y=0,
                width=chat_w,
                height=source_h,
                label="chat_overlay"
            )
        return None

    def calculate_clean_gameplay_bounds(
        self,
        source_w: int,
        source_h: int,
        excluded_regions: Optional[List[ExcludedRegion]] = None
    ) -> Tuple[int, int, int, int]:
        """
        Calculates the clean bounding rectangle (clean_x, clean_y, clean_w, clean_h)
        for gameplay, excluding persistent side overlays such as stream chat.
        """
        clean_x = 0
        clean_y = 0
        clean_w = source_w
        clean_h = source_h

        if excluded_regions:
            for reg in excluded_regions:
                # If region is along the right boundary, truncate clean width
                if reg.x + reg.width >= source_w - 20 and reg.x > source_w * 0.60:
                    clean_w = min(clean_w, reg.x)
                # If region is along the left boundary, advance clean_x
                elif reg.x <= 20 and reg.width < source_w * 0.40 and reg.label != "facecam":
                    offset = reg.x + reg.width
                    clean_x = max(clean_x, offset)
                    clean_w = max(100, clean_w - offset)

        clean_x = self._round_even(clean_x)
        clean_w = self._round_even(clean_w)
        clean_y = self._round_even(clean_y)
        clean_h = self._round_even(clean_h)
        return clean_x, clean_y, min(clean_w, source_w - clean_x), clean_h

    def mask_facecam_activity(
        self,
        activity_map: np.ndarray,
        facecam: Optional[FacecamRegion],
        padding_ratio: float = 0.05,
        excluded_regions: Optional[List[ExcludedRegion]] = None
    ) -> np.ndarray:
        """
        Zeroes out the streamer facecam and any excluded overlay regions (such as stream chat)
        within a 2D activity map to prevent non-gameplay motion from biasing camera tracking.
        """
        if (facecam is None or not facecam.is_detected) and not excluded_regions:
            return activity_map

        h, w = activity_map.shape[:2]
        masked = activity_map.copy()

        if facecam is not None and facecam.is_detected:
            pad_x = int(facecam.width * padding_ratio)
            pad_y = int(facecam.height * padding_ratio)
            x1 = max(0, facecam.x - pad_x)
            y1 = max(0, facecam.y - pad_y)
            x2 = min(w, facecam.x + facecam.width + pad_x)
            y2 = min(h, facecam.y + facecam.height + pad_y)
            masked[y1:y2, x1:x2] = 0.0

        if excluded_regions:
            for reg in excluded_regions:
                rx1 = max(0, reg.x)
                ry1 = max(0, reg.y)
                rx2 = min(w, reg.x + reg.width)
                ry2 = min(h, reg.y + reg.height)
                masked[ry1:ry2, rx1:rx2] = 0.0

        return masked

    def estimate_activity_x(
        self,
        frame_diff_or_gradient: np.ndarray,
        crop_w: int,
        facecam: Optional[FacecamRegion] = None,
        excluded_regions: Optional[List[ExcludedRegion]] = None
    ) -> int:
        """
        Determines the optimal horizontal top-left X coordinate for the gameplay crop window
        by identifying the region with highest visual activity outside the facecam and excluded overlays.
        """
        h, w = frame_diff_or_gradient.shape[:2]
        max_x = max(0, w - crop_w)
        if max_x == 0:
            return 0

        # Mask facecam and overlay activity
        activity = self.mask_facecam_activity(frame_diff_or_gradient, facecam, excluded_regions=excluded_regions)

        # Sum along vertical axis to obtain 1D horizontal intensity profile
        if activity.ndim == 3:
            activity = np.mean(activity, axis=2)
        h_profile = np.sum(activity, axis=0)  # shape: (w,)

        # Compute sliding window sum via cumulative sum for fast O(W) evaluation
        cumsum = np.cumsum(np.insert(h_profile, 0, 0.0))
        # window sum from i to i + crop_w is cumsum[i + crop_w] - cumsum[i]
        window_sums = cumsum[crop_w:w + 1] - cumsum[:w - crop_w + 1]

        if len(window_sums) == 0 or np.max(window_sums) <= 1e-4:
            # Default to center if no visual motion detected
            return self._round_even(max_x / 2.0)

        best_x = int(np.argmax(window_sums))
        # Force even X coordinate for FFmpeg macroblock alignment
        best_x = min(max_x, best_x if best_x % 2 == 0 else best_x - 1)
        return max(0, best_x)

    def apply_ema_smoothing(
        self,
        positions: List[float],
        alpha: float = 0.10,
        max_x: Optional[int] = None
    ) -> List[int]:
        """
        Applies Exponential Moving Average (EMA) smoothing across a sequence of crop X positions.
        Prevents jarring camera jumps between frames while tracking consistent gameplay motion.
        """
        if not positions:
            return []

        smoothed: List[int] = []
        current = float(positions[0])

        for pos in positions:
            current = alpha * float(pos) + (1.0 - alpha) * current
            val = int(round(current))
            # Align to even pixel
            if val % 2 != 0:
                val -= 1
            if max_x is not None:
                val = max(0, min(val, max_x))
            else:
                val = max(0, val)
            smoothed.append(val)

        return smoothed

    def get_gameplay_crop_window(
        self,
        source_w: int,
        source_h: int,
        canvas_dims: CanvasDimensions,
        facecam: Optional[FacecamRegion] = None,
        preferred_x: Optional[int] = None
    ) -> GameplayCropWindow:
        """
        Constructs a complete GameplayCropWindow tailored for the given CanvasDimensions.
        """
        crop_w, crop_h = self.calculate_gameplay_crop_dimensions(
            source_w=source_w,
            source_h=source_h,
            target_w=canvas_dims.width,
            target_h=canvas_dims.bottom_height
        )

        max_x = max(0, source_w - crop_w)
        if preferred_x is not None:
            crop_x = max(0, min(preferred_x, max_x))
            crop_x = crop_x if crop_x % 2 == 0 else crop_x - 1
        else:
            # Center by default
            crop_x = self._round_even(max_x / 2.0)

        crop_y = max(0, (source_h - crop_h) // 2)
        crop_y = crop_y if crop_y % 2 == 0 else crop_y - 1

        ratio_str = f"{canvas_dims.width}:{canvas_dims.bottom_height}"

        return GameplayCropWindow(
            x=crop_x,
            y=crop_y,
            width=crop_w,
            height=crop_h,
            aspect_ratio=ratio_str
        )


gameplay_crop_service = GameplayCropService()
