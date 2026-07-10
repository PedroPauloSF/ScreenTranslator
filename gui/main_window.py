"""
Main application window.

Provides the UI for the continuous translation mode (real-time).
Delegates all pipeline orchestration to ContinuousController.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSlider,
    QSpinBox,
    QGroupBox,
    QFormLayout,
    QStatusBar,
    QMessageBox,
)

from config.settings import (
    AppSettings,
    Region,
    get_settings,
    save_settings,
)
from gui.region_selector import RegionSelector
from translation import discover_translator
from translation.translator import Translator
from continuous_mode.controller import ContinuousController
from utils.logger import get_logger

logger = get_logger(__name__)


class MainWindow(QMainWindow):
    """Main application window with controls and status display."""

    def __init__(self) -> None:
        """Initialize the main window, load settings, create sub-components."""
        super().__init__()
        self._settings = get_settings()
        self._translator: Translator | None = None
        self._selector: RegionSelector | None = None
        self._capture_running: bool = False

        self._controller = ContinuousController(self._settings)
        self._controller.pipeline_state.connect(self._on_pipeline_state)
        self._controller.status_message.connect(self._on_status_message)
        self._controller.ocr_text.connect(self._on_ocr_text)

        self._setup_ui()
        self._load_translator()
        self._controller.set_translator(self._translator)
        self._load_previous_region()

    def _setup_ui(self) -> None:
        """Build the UI layout."""
        self.setWindowTitle("Tradutor de Telas")
        self.setMinimumSize(480, 400)
        self.resize(500, 480)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setSpacing(8)

        region_group = QGroupBox("Regiao de Captura")
        region_layout = QVBoxLayout(region_group)
        self._region_btn = QPushButton("Selecionar Regiao")
        self._region_btn.clicked.connect(self._open_region_selector)
        region_layout.addWidget(self._region_btn)
        self._region_label = QLabel("Nenhuma regiao selecionada")
        self._region_label.setWordWrap(True)
        region_layout.addWidget(self._region_label)
        layout.addWidget(region_group)

        control_group = QGroupBox("Captura")
        control_layout = QHBoxLayout(control_group)
        self._toggle_btn = QPushButton("Iniciar")
        self._toggle_btn.clicked.connect(self._toggle_capture)
        control_layout.addWidget(self._toggle_btn)

        interval_layout = QFormLayout()
        self._interval_spin = QSpinBox()
        self._interval_spin.setRange(100, 5000)
        self._interval_spin.setValue(self._settings.capture.interval_ms)
        self._interval_spin.setSuffix(" ms")
        self._interval_spin.valueChanged.connect(self._on_interval_changed)
        interval_layout.addRow("Intervalo:", self._interval_spin)
        control_layout.addLayout(interval_layout)
        layout.addWidget(control_group)

        overlay_group = QGroupBox("Overlay")
        overlay_form = QFormLayout(overlay_group)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(int(self._settings.overlay.opacity * 100))
        self._opacity_slider.valueChanged.connect(self._on_opacity_changed)
        overlay_form.addRow("Opacidade:", self._opacity_slider)

        self._font_size_spin = QSpinBox()
        self._font_size_spin.setRange(8, 48)
        self._font_size_spin.setValue(self._settings.overlay.font_size)
        self._font_size_spin.valueChanged.connect(self._on_font_size_changed)
        overlay_form.addRow("Tamanho da Fonte:", self._font_size_spin)

        layout.addWidget(overlay_group)

        status_group = QGroupBox("Status")
        status_layout = QFormLayout(status_group)
        self._status_label = QLabel("Parado")
        status_layout.addRow("Estado:", self._status_label)
        self._ocr_text_label = QLabel("—")
        self._ocr_text_label.setWordWrap(True)
        status_layout.addRow("OCR:", self._ocr_text_label)
        layout.addWidget(status_group)

        layout.addStretch()

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Pronto")

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
                f"Esquerda: {region.left}, Topo: {region.top}, "
                f"Tamanho: {region.width} x {region.height}"
            )
        else:
            self._region_label.setText("Nenhuma regiao selecionada. Clique em 'Selecionar Regiao' para comecar.")

    def _open_region_selector(self) -> None:
        """Open the fullscreen region selector overlay."""
        if self._capture_running:
            self._controller.stop()

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

        regiao_text = (
            f"Esquerda: {region.left}, Topo: {region.top}, "
            f"Tamanho: {region.width} x {region.height}"
        )
        self._region_label.setText(regiao_text)

        self._controller.configure_region(region)

        self.show()
        self._controller.start()

    def _toggle_capture(self) -> None:
        """Toggle capture on/off."""
        if self._capture_running:
            self._controller.stop()
        else:
            if not self._settings.region.is_valid:
                QMessageBox.warning(
                    self,
                    "Nenhuma Regiao",
                    "Selecione uma regiao da tela primeiro.",
                )
                return
            self._controller.start()

    @Slot(str)
    def _on_pipeline_state(self, state: str) -> None:
        """Update UI in response to pipeline state changes.

        Args:
            state: "Running" or "Stopped".
        """
        self._status_label.setText(state)
        if state == "Running":
            self._capture_running = True
            self._toggle_btn.setText("Parar")
        else:
            self._capture_running = False
            self._toggle_btn.setText("Iniciar")

    @Slot(str)
    def _on_status_message(self, message: str) -> None:
        """Display a message in the status bar.

        Args:
            message: Status message to display.
        """
        self._status_bar.showMessage(message, 5000)

    @Slot(str)
    def _on_ocr_text(self, text: str) -> None:
        """Update the OCR text preview label.

        Args:
            text: Raw OCR output.
        """
        self._ocr_text_label.setText(text)

    def _on_opacity_changed(self, value: int) -> None:
        """Handle opacity slider changes."""
        self._settings.overlay.opacity = value / 100.0
        self._controller.update_overlay_settings(self._settings.overlay)
        save_settings(self._settings)

    def _on_font_size_changed(self, value: int) -> None:
        """Handle font size changes."""
        self._settings.overlay.font_size = value
        self._controller.update_overlay_settings(self._settings.overlay)
        save_settings(self._settings)

    def _on_interval_changed(self, value: int) -> None:
        """Handle capture interval changes."""
        self._settings.capture.interval_ms = value
        save_settings(self._settings)

    def closeEvent(self, event) -> None:
        """Handle window close: stop pipeline and save settings."""
        self._controller.cleanup()
        save_settings(self._settings)
        super().closeEvent(event)
