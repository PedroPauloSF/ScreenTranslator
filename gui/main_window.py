"""
Main application window.

Orchestrates the capture → detect → OCR → translate → overlay pipeline.
Connects workers via Qt signals and manages the application lifecycle.
"""

from __future__ import annotations

import numpy as np
from PySide6.QtCore import Qt, QThread, Signal, Slot, QTimer
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QSpinBox,
    QComboBox,
    QGroupBox,
    QFormLayout,
    QStatusBar,
    QMessageBox,
)

from config.settings import (
    AppSettings,
    Region,
    OverlaySettings,
    get_settings,
    save_settings,
)
from threads.capture_worker import CaptureWorker
from threads.ocr_worker import OCRWorker
from threads.translation_worker import TranslationWorker
from gui.region_selector import RegionSelector
from overlay.overlay_window import OverlayWindow
from overlay.region_border import RegionBorder
from translation import discover_translator
from translation.translator import Translator
from utils.image_compare import ImageComparator
from utils.text_compare import TextComparator
from utils.logger import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window with controls and status display."""

    _CAPTURE_CHECK_INTERVAL = 50

    def __init__(self) -> None:
        """Initialize the main window, load settings, create sub-components."""
        super().__init__()
        self._settings = get_settings()
        self._translator: Translator | None = None
        self._overlay: OverlayWindow | None = None
        self._region_border: RegionBorder | None = None
        self._selector: RegionSelector | None = None
        self._capture_running: bool = False
        self._ocr_busy: bool = False

        self._previous_frame: np.ndarray | None = None
        self._previous_text: str = ""
        self._text_comparator = TextComparator(
            similarity_threshold=self._settings.translation.similarity_threshold,
        )
        self._image_comparator = ImageComparator(
            ssim_threshold=self._settings.capture.ssim_threshold,
            hash_threshold=self._settings.capture.perceptual_hash_threshold,
        )

        self._capture_worker: CaptureWorker | None = None
        self._capture_thread: QThread | None = None
        self._ocr_worker: OCRWorker | None = None
        self._ocr_thread: QThread | None = None
        self._translation_worker: TranslationWorker | None = None
        self._translation_thread: QThread | None = None

        self._setup_ui()
        self._load_translator()
        self._load_previous_region()

    def _setup_ui(self) -> None:
        """Build the UI layout."""
        self.setWindowTitle("Screen Translator")
        self.setMinimumSize(480, 400)
        self.resize(500, 480)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        region_group = QGroupBox("Monitor Region")
        region_layout = QVBoxLayout(region_group)
        self._region_btn = QPushButton("Select Region")
        self._region_btn.clicked.connect(self._open_region_selector)
        region_layout.addWidget(self._region_btn)
        self._region_label = QLabel("No region selected")
        self._region_label.setWordWrap(True)
        region_layout.addWidget(self._region_label)
        layout.addWidget(region_group)

        control_group = QGroupBox("Capture")
        control_layout = QHBoxLayout(control_group)
        self._toggle_btn = QPushButton("Start")
        self._toggle_btn.clicked.connect(self._toggle_capture)
        control_layout.addWidget(self._toggle_btn)

        interval_layout = QFormLayout()
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(100, 5000)
        self._interval_spin.setValue(self._settings.capture.interval_ms)
        self._interval_spin.setSuffix(" ms")
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        interval_layout.addRow("Interval:", self._interval_spin)
        control_layout.addLayout(interval_layout)
        layout.addWidget(control_group)

        overlay_group = QGroupBox("Overlay")
        overlay_form = QFormLayout(overlay_group)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(int(self._settings.overlay.opacity * 100))
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        overlay_form.addRow("Opacity:", self._opacity_slider)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 48)
        self._font_size_spin.setValue(self._settings.overlay.font_size)
        self._font_size_spin.valueChanged.connect(self._on_font_size_changed)
        overlay_form.addRow("Font Size:", self._font_size_spin)

        layout.addWidget(overlay_group)

        status_group = QGroupBox("Status")
        status_layout = QFormLayout(status_group)
        self._status_label = QLabel("Idle")
        status_layout.addRow("State:", self._status_label)
        self._ocr_text_label = QLabel("—")
        self._ocr_text_label.setWordWrap(True)
        status_layout.addRow("OCR:", self._ocr_text_label)
        layout.addWidget(status_group)

        layout.addStretch()

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Ready")

    def _load_translator(self) -> None:
        """Load the translator (plugin or fallback)."""
        try:
            self._translator = discover_translator(
                preferred=self._settings.active_plugin,
            )
            logger.info("Translator loaded: %s", self._translator.name)
        except Exception as e:
            logger.error("Failed to load translator: %s", e)
            from translation.generic_translator import GenericTranslator
            self._translator = GenericTranslator()

    def _load_previous_region(self) -> None:
        """Display the previously saved region, if any."""
        region = self._settings.region
        if region.is_valid:
            self._region_label.setText(
                f"Left: {region.left}, Top: {region.top}, "
                f"Size: {region.width} x {region.height}"
            )
        else:
            self._region_label.setText("No region selected. Click 'Select Region' to begin.")

    def _open_region_selector(self) -> None:
        """Open the fullscreen region selector overlay."""
        if self._capture_running:
            self._stop_pipeline()

        self.hide()
        QTimer.singleShot(300, self._show_selector)

    def _show_selector(self) -> None:
        """Display the region selection overlay."""
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.showFullScreen()

    @Slot(Region)
    def _on_region_selected(self, region: Region) -> None:
        """Handle the selected region from the overlay.

        Args:
            region: The selected screen region.
        """
        self._settings.region = region
        save_settings(self._settings)

        self._region_label.setText(
            f"Left: {region.left}, Top: {region.top}, "
            f"Size: {region.width} x {region.height}"
        )

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

        self.show()
        self._start_pipeline()

    def _toggle_capture(self) -> None:
        """Toggle capture on/off."""
        if self._capture_running:
            self._stop_pipeline()
        else:
            if not self._settings.region.is_valid:
                QMessageBox.warning(
                    self,
                    "No Region",
                    "Please select a screen region first.",
                )
                return
            self._start_pipeline()

    def _start_pipeline(self) -> None:
        """Initialize and start the capture → OCR → translation pipeline."""
        if not self._settings.region.is_valid:
            return

        self._create_overlay()
        self._start_capture_thread()
        self._start_ocr_thread()
        self._start_translation_thread()

        self._capture_running = True
        self._toggle_btn.setText("Stop")
        self._status_label.setText("Running")
        self._status_bar.showMessage(f"Monitoring region. Translator: {self._translator.name}")

    def _stop_pipeline(self) -> None:
        """Stop all workers and threads gracefully."""
        self._capture_running = False
        self._ocr_busy = False
        self._toggle_btn.setText("Start")

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

        self._status_label.setText("Stopped")
        self._status_bar.showMessage("Capture stopped.")
        save_settings(self._settings)

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
            self._load_translator()

        self._translation_worker = TranslationWorker(self._translator)
        self._translation_worker.translation_ready.connect(self._on_translation_ready)
        self._translation_worker.translation_error.connect(self._on_translation_error)

        self._translation_thread = QThread()
        self._translation_worker.moveToThread(self._translation_thread)
        self._translation_thread.finished.connect(
            self._translation_worker.deleteLater
        )
        self._translation_thread.start()

    @Slot(np.ndarray)
    def _on_frame_captured(self, image: np.ndarray) -> None:
        """Process a captured frame: detect change, then trigger OCR."""
        if self._ocr_busy:
            return

        if self._previous_frame is not None:
            if not self._image_comparator.has_changed(self._previous_frame, image):
                return

        self._previous_frame = image

        if self._ocr_worker:
            self._ocr_busy = True
            self._ocr_worker.process_image(image)

    @Slot(object)
    @Slot(str, float)
    def _on_ocr_completed(self, text: str, confidence: float) -> None:
        """Process OCR result: compare text, then trigger translation."""
        self._ocr_busy = False
        self._ocr_text_label.setText(text[:200] if text else "(no text)")

        if not self._text_comparator.text_has_changed(text):
            return

        self._previous_text = text

        if self._translation_worker and text.strip():
            self._translation_worker.translate_text(text)

    @Slot(str)
    def _on_translation_ready(self, translated_text: str) -> None:
        """Display the translated text in the overlay."""
        if self._overlay:
            self._overlay.set_text(translated_text)

    @Slot(str)
    def _on_capture_error(self, error: str) -> None:
        """Handle capture errors."""
        self._status_bar.showMessage(f"Capture error: {error}", 5000)
        logger.error("Capture error: %s", error)

    @Slot(str)
    def _on_ocr_error(self, error: str) -> None:
        """Handle OCR errors."""
        self._ocr_busy = False
        self._status_bar.showMessage(f"OCR error: {error}", 5000)
        logger.error("OCR error: %s", error)

    @Slot(str)
    def _on_translation_error(self, error: str) -> None:
        """Handle translation errors."""
        self._status_bar.showMessage(f"Translation error: {error}", 5000)
        logger.error("Translation error: %s", error)

    def _on_opacity_changed(self, value: int) -> None:
        """Handle opacity slider changes."""
        self._settings.overlay.opacity = value / 100.0
        if self._overlay:
            self._overlay.update_settings(self._settings.overlay)
        save_settings(self._settings)

    def _on_font_size_changed(self, value: int) -> None:
        """Handle font size changes."""
        self._settings.overlay.font_size = value
        if self._overlay:
            self._overlay.update_settings(self._settings.overlay)
        save_settings(self._settings)

    def _on_interval_changed(self, value: int) -> None:
        """Handle capture interval changes."""
        self._settings.capture.interval_ms = value
        save_settings(self._settings)

    def closeEvent(self, event) -> None:
        """Handle window close: stop pipeline and save settings."""
        self._stop_pipeline()
        if self._overlay:
            self._overlay.close()
            self._overlay = None
        if self._region_border:
            self._region_border.close()
            self._region_border = None
        save_settings(self._settings)
        super().closeEvent(event)
