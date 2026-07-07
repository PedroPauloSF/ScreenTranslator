"""
Screen capture worker.

Runs the capture loop in a dedicated thread, periodically grabbing
the configured screen region and emitting frames via Qt signals.
Uses QTimer for non-blocking, event-loop-friendly scheduling.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal, QTimer, Qt

from capture.screen_capture import ScreenCapture
from config.settings import Region
from utils.logger import get_logger

logger = get_logger(__name__)


class CaptureWorker(QObject):
    """Worker that captures screen frames in a background thread.

    Emits frame_captured with the raw image at the configured interval.
    Can be paused/resumed and stopped gracefully via QTimer scheduling.

    Signals:
        frame_captured: Emitted with the captured image (BGR numpy array).
        capture_error: Emitted with an error message on failure.
    """

    frame_captured = Signal(np.ndarray)
    capture_error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the capture worker.

        Args:
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._screen = ScreenCapture()
        self._interval_ms: int = 500
        self._paused: bool = False

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.PreciseTimer)
        self._timer.timeout.connect(self._capture_tick)

    def configure(self, region: Region, interval_ms: int) -> None:
        """Set the capture region and interval.

        Args:
            region: Screen region to capture.
            interval_ms: Delay between captures in milliseconds.
        """
        self._screen.set_region(region)
        self._interval_ms = interval_ms
        logger.info(
            "Capture configured: region=(%d,%d %dx%d), interval=%dms",
            region.left, region.top, region.width, region.height,
            interval_ms,
        )

    def start_capture(self) -> None:
        """Begin the capture loop."""
        self._paused = False
        self._timer.start(self._interval_ms)
        logger.info("Capture loop started (interval=%dms).", self._interval_ms)

    def stop_capture(self) -> None:
        """Stop the capture loop."""
        self._timer.stop()
        self._screen.close()
        logger.info("Capture loop stopped.")

    def pause(self) -> None:
        """Pause capture without stopping the timer."""
        self._paused = True
        logger.debug("Capture paused.")

    def resume(self) -> None:
        """Resume capture after pause."""
        self._paused = False
        logger.debug("Capture resumed.")

    def _capture_tick(self) -> None:
        """Single capture tick, called by the timer."""
        if self._paused:
            return

        try:
            result = self._screen.capture()
            self.frame_captured.emit(result.image)
        except Exception as e:
            logger.error("Capture failed: %s", e)
            self.capture_error.emit(str(e))

    def cleanup(self) -> None:
        """Release resources."""
        self._timer.stop()
        self._screen.close()
