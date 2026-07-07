"""
Image pre-processing pipeline for OCR optimization.

Applies a sequence of transformations to improve OCR accuracy:
1. Grayscale conversion
2. CLAHE (Contrast Limited Adaptive Histogram Equalization)
3. Adaptive thresholding
4. Noise removal
5. Conditional upscaling for small images
"""

from __future__ import annotations

import cv2
import numpy as np
from dataclasses import dataclass


@dataclass
class Preprocessor:
    """Pipeline of image transformations applied before OCR.

    Attributes:
        clahe_clip_limit: Clip limit for CLAHE (contrast enhancement).
        clahe_tile_size: Grid size for CLAHE.
        threshold_block_size: Block size for adaptive threshold.
        threshold_c: Constant subtracted from threshold mean.
        upscale_factor: Factor to enlarge small images.
        upscale_min_width: Minimum width to trigger upscale.
        upscale_min_height: Minimum height to trigger upscale.
    """

    clahe_clip_limit: float = 2.0
    clahe_tile_size: tuple[int, int] = (8, 8)
    threshold_block_size: int = 11
    threshold_c: int = 2
    upscale_factor: float = 2.0
    upscale_min_width: int = 200
    upscale_min_height: int = 100

    def process(self, image: np.ndarray) -> np.ndarray:
        """Execute the full preprocessing pipeline on a BGR image.

        Args:
            image: Source image in BGR format.

        Returns:
            Processed grayscale image optimized for OCR.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

        clahe = cv2.createCLAHE(
            clipLimit=self.clahe_clip_limit,
            tileGridSize=self.clahe_tile_size,
        )
        enhanced = clahe.apply(gray)

        binary = cv2.adaptiveThreshold(
            enhanced,
            255,
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
            cv2.THRESH_BINARY,
            self.threshold_block_size,
            self.threshold_c,
        )

        denoised = cv2.medianBlur(binary, 3)

        kernel = np.ones((2, 2), np.uint8)
        cleaned = cv2.morphologyEx(denoised, cv2.MORPH_CLOSE, kernel)

        result = self._maybe_upscale(cleaned)

        return result

    def _maybe_upscale(self, image: np.ndarray) -> np.ndarray:
        """Upscale the image if it is below the minimum size threshold.

        Args:
            image: Grayscale image to potentially upscale.

        Returns:
            Upscaled image, or the original if already large enough.
        """
        h, w = image.shape[:2]
        if w >= self.upscale_min_width and h >= self.upscale_min_height:
            return image

        new_w = int(w * self.upscale_factor)
        new_h = int(h * self.upscale_factor)

        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_CUBIC)
