"""
Screen capture module.

Thin wrapper around MSS for capturing a rectangular region of the screen.
Returns raw numpy arrays in BGR format for downstream processing.
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import numpy as np
import mss

from config.settings import Region


@dataclass
class CaptureResult:
    """Result of a single screen capture operation.

    Attributes:
        image: Captured region as a BGR numpy array.
        timestamp: Unix timestamp of capture.
        elapsed_ms: Time taken to capture in milliseconds.
        region: The region that was captured.
    """

    image: np.ndarray
    timestamp: float
    elapsed_ms: float
    region: Region


class ScreenCapture:
    """Captures a rectangular region of the primary monitor using MSS.

    Usage:
        cap = ScreenCapture()
        cap.set_region(Region(left=100, top=100, width=400, height=300))
        result = cap.capture()
        image = result.image  # numpy array (height, width, 3) BGR
    """

    def __init__(self) -> None:
        self._sct = mss.mss()
        self._region: Region = Region()
        self._monitor: dict[str, int] = {}

    def set_region(self, region: Region) -> None:
        """Define the screen region to capture.

        Args:
            region: A Region dataclass with left, top, width, height.
        """
        self._region = region
        self._monitor = {
            "left": region.left,
            "top": region.top,
            "width": region.width,
            "height": region.height,
        }

    @property
    def region(self) -> Region:
        """Return the currently configured capture region."""
        return self._region

    def capture(self) -> CaptureResult:
        """Capture the configured screen region.

        Returns:
            CaptureResult containing the BGR image array and metadata.

        Raises:
            RuntimeError: If no region has been configured.
        """
        if not self._monitor:
            raise RuntimeError("Capture region not set. Call set_region() first.")

        start = time.perf_counter()
        sct_img = self._sct.grab(self._monitor)

        image = np.array(sct_img, dtype=np.uint8)
        image = image[:, :, :3].copy()

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        return CaptureResult(
            image=image,
            timestamp=start,
            elapsed_ms=elapsed_ms,
            region=self._region,
        )

    def close(self) -> None:
        """Release MSS resources."""
        self._sct.close()
