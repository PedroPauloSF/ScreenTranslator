"""
Study mode capture action.

Handles a single manual capture: region selection -> screen capture
-> OCR -> translation -> persistence. Runs the heavy work in a
QThread to keep the GUI responsive.
"""

from __future__ import annotations

import time
from pathlib import Path

import cv2
import numpy as np
from PySide6.QtCore import QObject, Signal, Slot, QThread

from config.settings import AppSettings, Region
from capture.screen_capture import ScreenCapture
from ocr.engine import OCREngine
from translation.translator import Translator
from database.repository import (
    CaptureRepository,
    OCRRepository,
    TranslationRepository,
)
from utils.paths import app_data_dir
from utils.logger import get_logger

logger = get_logger(__name__)


def _ensure_captures_dir() -> Path:
    """Ensure the captures directory exists."""
    return app_data_dir("captures")


def _save_image(image: np.ndarray) -> Path:
    """Save a captured image as PNG.

    Args:
        image: BGR image as numpy array.

    Returns:
        Path to the saved image file.
    """
    capture_dir = _ensure_captures_dir()
    timestamp = int(time.time() * 1000)
    filename = f"capture_{timestamp}.png"
    filepath = capture_dir / filename
    cv2.imwrite(str(filepath), image)
    logger.info("Image saved: %s", filepath)
    return filepath


class _ProcessWorker(QObject):
    """Worker that runs capture processing in a background thread."""

    finished = Signal(int)
    error = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    @Slot()
    def process(
        self,
        region: Region,
        translator: Translator,
        settings: AppSettings,
    ) -> None:
        """Execute the full capture -> OCR -> translate -> persist pipeline.

        Called from the worker's thread.
        """
        try:
            screen = ScreenCapture()
            screen.set_region(region)

            result = screen.capture()
            image = result.image
            screen.close()

            image_path = _save_image(image)

            cap_repo = CaptureRepository()
            capture_id = cap_repo.insert(
                image_path=str(image_path),
                source_lang=settings.ocr.language,
                target_lang=settings.translation.target_language,
                region=(region.left, region.top, region.width, region.height),
            )

            engine = OCREngine(language=settings.ocr.language)
            ocr_result = engine.extract(image)

            ocr_repo = OCRRepository()
            ocr_repo.insert(
                capture_id=capture_id,
                raw_text=ocr_result.text,
                confidence=ocr_result.confidence,
                language=settings.ocr.language,
            )

            translated = translator.translate(ocr_result.text) if ocr_result.text.strip() else ""

            tl_repo = TranslationRepository()
            tl_repo.insert(
                capture_id=capture_id,
                translated_text=translated,
                engine=translator.name,
            )

            self.finished.emit(capture_id)

        except Exception as e:
            logger.exception("Capture processing failed")
            self.error.emit(str(e))


class CaptureAction(QObject):
    """Orchestrates a manual capture action.

    Signals:
        completed: Emitted with the new capture_id when processing finishes.
        failed: Emitted with an error message on failure.
    """

    completed = Signal(int)
    failed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        """Initialize the capture action."""
        super().__init__(parent)
        self._thread: QThread | None = None
        self._worker: _ProcessWorker | None = None

    def execute(
        self,
        region: Region,
        translator: Translator,
        settings: AppSettings,
    ) -> None:
        """Start the capture action in a background thread.

        Args:
            region: Screen region to capture.
            translator: Translator instance.
            settings: Application settings.
        """
        self._worker = _ProcessWorker()
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        self._thread = QThread()
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(
            lambda: self._worker.process(region, translator, settings)
        )
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.start()

    @Slot(int)
    def _on_finished(self, capture_id: int) -> None:
        """Handle processing completion."""
        self._cleanup_thread()
        self.completed.emit(capture_id)

    @Slot(str)
    def _on_error(self, error: str) -> None:
        """Handle processing error."""
        self._cleanup_thread()
        self.failed.emit(error)

    def _cleanup_thread(self) -> None:
        """Clean up the worker thread."""
        if self._thread:
            self._thread.quit()
            self._thread.wait(5000)
            self._thread = None
            self._worker = None
