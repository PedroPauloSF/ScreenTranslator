"""
OCR worker.

Runs OCR in a dedicated thread to keep the GUI responsive.
Receives images via slots and emits results via signals.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, Signal, Slot

from ocr.engine import OCREngine
from utils.logger import get_logger

logger = get_logger(__name__)


class OCRWorker(QObject):
    """Worker that runs OCR in a background thread.

    Receives BGR images via the process_image slot and emits
    ocr_completed with the extracted text and confidence.

    Signals:
        ocr_completed: Emitted with (text, confidence) when OCR finishes.
        ocr_error: Emitted with an error message on failure.
    """

    ocr_completed = Signal(str, float)
    ocr_error = Signal(str)

    def __init__(self, language: str = "en", parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._engine = OCREngine(language=language)

    def set_language(self, language: str) -> None:
        self._engine.set_language(language)

    @Slot(np.ndarray)
    def process_image(self, image: np.ndarray) -> None:
        """Run OCR on a captured image.

        Args:
            image: BGR image as numpy array.
        """
        try:
            result = self._engine.extract(image)
            self.ocr_completed.emit(result.text, result.confidence)
        except Exception as e:
            logger.error("OCR processing failed: %s", e)
            self.ocr_error.emit(str(e))

    def cleanup(self) -> None:
        """Release resources."""
        pass
