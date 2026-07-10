"""
Continuous mode controller.

Orchestrates the capture -> detect change -> OCR -> translate -> overlay
pipeline for real-time screen translation. Manages all worker threads,
image/text comparators, and the transparent overlay.

This module has NO knowledge of study mode, history, database, or annotations.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import QObject, QThread, Signal, Slot

from config.settings import AppSettings, Region, OverlaySettings
from threads.capture_worker import CaptureWorker
from threads.ocr_worker import OCRWorker
from threads.translation_worker import TranslationWorker
from overlay.overlay_window import OverlayWindow
from overlay.region_border import RegionBorder
from translation.translator import Translator
from utils.image_compare import ImageComparator
from utils.text_compare import TextComparator
from utils.logger import get_logger

logger = get_logger(__name__)


class ContinuousController(QObject):
    """Orchestrates the continuous translation pipeline.

    Owns the lifecycle of all pipeline components:
    capture, OCR, translation workers, overlay, and region border.

    Signals:
        status_message: Emitted with status bar messages.
        ocr_text: Emitted with the latest OCR text for UI display.
        pipeline_state: Emitted when the pipeline transitions (Running/Stopped).
    """

    status_message = Signal(str)
    ocr_text = Signal(str)
    pipeline_state = Signal(str)

    def __init__(
        self,
        settings: AppSettings,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the continuous controller.

        Args:
            settings: Application settings (region, overlay, capture, etc.).
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._settings = settings
        self._translator: Translator | None = None
        self._overlay: OverlayWindow | None = None
        self._region_border: RegionBorder | None = None
        self._running: bool = False
        self._ocr_busy: bool = False

        self._previous_frame: np.ndarray | None = None
        self._previous_text: str = ""

        self._text_comparator = TextComparator(
            similarity_threshold=settings.translation.similarity_threshold,
        )
        self._image_comparator = ImageComparator(
            ssim_threshold=settings.capture.ssim_threshold,
            hash_threshold=settings.capture.perceptual_hash_threshold,
        )

        self._capture_worker: CaptureWorker | None = None
        self._capture_thread: QThread | None = None
        self._ocr_worker: OCRWorker | None = None
        self._ocr_thread: QThread | None = None
        self._translation_worker: TranslationWorker | None = None
        self._translation_thread: QThread | None = None

    def set_translator(self, translator: Translator) -> None:
        """Set the translator instance to use for the pipeline.

        Args:
            translator: A Translator instance (plugin or generic).
        """
        self._translator = translator

    def is_running(self) -> bool:
        """Return whether the pipeline is currently active."""
        return self._running

    def start(self) -> None:
        """Start the capture -> OCR -> translation pipeline."""
        if not self._settings.region.is_valid:
            return

        self._create_overlay()
        self._start_capture_thread()
        self._start_ocr_thread()
        self._start_translation_thread()

        self._running = True
        self.pipeline_state.emit("Running")
        translator_name = self._translator.name if self._translator else "none"
        self.status_message.emit(f"Monitoring region. Translator: {translator_name}")

    def stop(self) -> None:
        """Stop all workers and threads gracefully."""
        self._running = False
        self._ocr_busy = False

        if self._capture_worker:
            self._capture_worker.stop_capture()
        if self._capture_thread:
            self._capture_thread.requestInterruption()
            self._capture_thread.quit()
            self._capture_thread.wait(5000)
            self._capture_thread = None
            self._capture_worker = None

        if self._ocr_worker:
            self._ocr_thread = self._ocr_worker.thread()
        if self._ocr_thread:
            self._ocr_thread.requestInterruption()
            self._ocr_thread.quit()
            self._ocr_thread.wait(5000)
            self._ocr_thread = None
            self._ocr_worker = None

        if self._translation_worker:
            self._translation_thread = self._translation_worker.thread()
        if self._translation_thread:
            self._translation_thread.requestInterruption()
            self._translation_thread.quit()
            self._translation_thread.wait(5000)
            self._translation_thread = None
            self._translation_worker = None

        if self._overlay:
            self._overlay.set_text("")
            self._overlay.hide()

        if self._region_border:
            self._region_border.hide()

        self.pipeline_state.emit("Stopped")
        self.status_message.emit("Capture stopped.")

    def configure_region(self, region: Region) -> None:
        """Update the monitored region and reset change detection state.

        Args:
            region: The new screen region to monitor.
        """
        self._settings.region = region

        if self._overlay:
            self._overlay.set_monitor_region(region)
        if self._region_border:
            self._region_border.set_region(region)

        self._image_comparator = ImageComparator(
            ssim_threshold=self._settings.capture.ssim_threshold,
            hash_threshold=self._settings.capture.perceptual_hash_threshold,
        )
        self._text_comparator.reset()
        self._previous_frame = None

    def update_overlay_settings(self, overlay_settings: OverlaySettings) -> None:
        """Apply new overlay visual settings at runtime.

        Args:
            overlay_settings: Updated overlay configuration.
        """
        if self._overlay:
            self._overlay.update_settings(overlay_settings)

    def cleanup(self) -> None:
        """Release all resources: stop pipeline, close overlay and border."""
        self.stop()
        if self._overlay:
            self._overlay.close()
            self._overlay = None
        if self._region_border:
            self._region_border.close()
            self._region_border = None

    # ------------------------------------------------------------------
    # Private: overlay management
    # ------------------------------------------------------------------

    def _create_overlay(self) -> None:
        """Create or reconfigure the overlay window and region border."""
        if self._overlay is None:
            self._overlay = OverlayWindow(self._settings.overlay)
        else:
            self._overlay.update_settings(self._settings.overlay)

        self._overlay.set_monitor_region(self._settings.region)

        if self._region_border is None:
            self._region_border = RegionBorder()
        self._region_border.set_region(self._settings.region)

    # ------------------------------------------------------------------
    # Private: thread management
    # ------------------------------------------------------------------

    def _start_capture_thread(self) -> None:
        """Start the capture worker in a background thread."""
        self._capture_worker = CaptureWorker()
        self._capture_worker.configure(
            self._settings.region,
            self._settings.capture.interval_ms,
        )

        self._capture_thread = QThread()
        self._capture_worker.moveToThread(self._capture_thread)
        self._capture_worker.frame_captured.connect(self._on_frame_captured)
        self._capture_worker.capture_error.connect(self._on_capture_error)
        self._capture_thread.started.connect(self._capture_worker.start_capture)
        self._capture_thread.finished.connect(self._capture_worker.deleteLater)
        self._capture_thread.start()

    def _start_ocr_thread(self) -> None:
        """Start the OCR worker in a background thread."""
        self._ocr_worker = OCRWorker(language=self._settings.ocr.language)
        self._ocr_worker.ocr_completed.connect(self._on_ocr_completed)
        self._ocr_worker.ocr_error.connect(self._on_ocr_error)

        self._ocr_thread = QThread()
        self._ocr_worker.moveToThread(self._ocr_thread)
        self._ocr_thread.finished.connect(self._ocr_worker.deleteLater)
        self._ocr_thread.start()

    def _start_translation_thread(self) -> None:
        """Start the translation worker in a background thread."""
        if self._translator is None:
            return

        self._translation_worker = TranslationWorker(self._translator)
        self._translation_worker.translation_ready.connect(self._on_translation_ready)
        self._translation_worker.translation_error.connect(self._on_translation_error)

        self._translation_thread = QThread()
        self._translation_worker.moveToThread(self._translation_thread)
        self._translation_thread.finished.connect(self._translation_worker.deleteLater)
        self._translation_thread.start()

    # ------------------------------------------------------------------
    # Private: pipeline signal handlers
    # ------------------------------------------------------------------

    @Slot(np.ndarray)
    def _on_frame_captured(self, image: np.ndarray) -> None:
        """Process a captured frame: detect change, then trigger OCR.

        Args:
            image: Captured BGR image as numpy array.
        """
        if self._ocr_busy:
            return

        if self._previous_frame is not None:
            if not self._image_comparator.has_changed(self._previous_frame, image):
                return

        self._previous_frame = image

        if self._ocr_worker:
            self._ocr_busy = True
            self._ocr_worker.process_image(image)

    @Slot(str, float)
    def _on_ocr_completed(self, text: str, confidence: float) -> None:
        """Process OCR result: compare text, then trigger translation.

        Args:
            text: Extracted OCR text.
            confidence: OCR confidence score.
        """
        self._ocr_busy = False
        self.ocr_text.emit(text[:200] if text else "(no text)")

        if not self._text_comparator.text_has_changed(text):
            return

        self._previous_text = text

        if self._translation_worker and text.strip():
            self._translation_worker.translate_text(text)

    @Slot(str)
    def _on_translation_ready(self, translated_text: str) -> None:
        """Display the translated text in the overlay.

        Args:
            translated_text: The translated output.
        """
        if self._overlay:
            self._overlay.set_text(translated_text)

    @Slot(str)
    def _on_capture_error(self, error: str) -> None:
        """Handle capture errors.

        Args:
            error: Error message string.
        """
        self.status_message.emit(f"Capture error: {error}")
        logger.error("Capture error: %s", error)

    @Slot(str)
    def _on_ocr_error(self, error: str) -> None:
        """Handle OCR errors.

        Args:
            error: Error message string.
        """
        self._ocr_busy = False
        self.status_message.emit(f"OCR error: {error}")
        logger.error("OCR error: %s", error)

    @Slot(str)
    def _on_translation_error(self, error: str) -> None:
        """Handle translation errors.

        Args:
            error: Error message string.
        """
        self.status_message.emit(f"Translation error: {error}")
        logger.error("Translation error: %s", error)
