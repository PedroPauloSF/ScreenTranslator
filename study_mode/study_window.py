"""
Study mode main window.

Provides the user interface for the manual capture study mode:
history sidebar, translation reader, highlight controls, and navigation.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal, Slot
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QSplitter,
    QStatusBar,
    QMessageBox,
)

from config.settings import AppSettings, Region
from translation.translator import Translator
from gui.region_selector import RegionSelector
from study_mode.controller import StudyController
from study_mode.study_reader import StudyReader
from study_mode.history_panel import HistoryPanel
from utils.logger import get_logger

logger = get_logger(__name__)


class StudyWindow(QMainWindow):
    """Main window for the manual capture study mode."""

    def __init__(
        self,
        settings: AppSettings,
        translator: Translator,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._settings = settings
        self._translator = translator
        self._selector: RegionSelector | None = None
        self._current_translation_id: int = 0

        self._controller = StudyController(settings, translator)
        self._controller.translation_loaded.connect(self._on_translation_loaded)
        self._controller.history_updated.connect(self._on_history_updated)
        self._controller.status_message.connect(self._on_status_message)
        self._controller.navigation_changed.connect(self._on_navigation_changed)
        self._controller.capture_completed.connect(self._on_capture_completed)

        self._reader: StudyReader | None = None
        self._history_panel: HistoryPanel | None = None
        self._prev_btn: QPushButton | None = None
        self._capture_btn: QPushButton | None = None
        self._next_btn: QPushButton | None = None

        self._setup_ui()
        self._setup_shortcuts()
        self._controller.load_history()
        self._update_nav_buttons(False, False)

    def _setup_ui(self) -> None:
        self.setWindowTitle("Tradutor de Telas - Modo Estudo")
        self.setMinimumSize(900, 550)
        self.resize(1000, 650)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        self._history_panel = HistoryPanel()
        self._history_panel.item_selected.connect(self._on_history_item_selected)
        self._history_panel.archive_requested.connect(self._on_archive_requested)
        self._history_panel.unarchive_requested.connect(self._on_unarchive_requested)
        self._history_panel.delete_requested.connect(self._on_delete_requested)
        self._history_panel.setMinimumWidth(200)
        self._history_panel.setMaximumWidth(300)
        splitter.addWidget(self._history_panel)

        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(6)

        self._reader = StudyReader()
        self._reader.highlight_requested.connect(self._on_highlight_requested)
        self._reader.highlight_removed.connect(self._on_highlight_removed)
        right_layout.addWidget(self._reader)

        nav_layout = QHBoxLayout()
        nav_layout.setSpacing(8)

        self._prev_btn = QPushButton("Anterior (Alt+←)")
        self._prev_btn.clicked.connect(self._on_previous)
        nav_layout.addWidget(self._prev_btn)

        nav_layout.addStretch()

        self._capture_btn = QPushButton("Capturar")
        self._capture_btn.setStyleSheet(
            "QPushButton { font-weight: bold; padding: 6px 16px; }"
        )
        self._capture_btn.clicked.connect(self._open_capture_selector)
        nav_layout.addWidget(self._capture_btn)

        nav_layout.addStretch()

        self._next_btn = QPushButton("Proximo (Alt+→)")
        self._next_btn.clicked.connect(self._on_next)
        nav_layout.addWidget(self._next_btn)

        right_layout.addLayout(nav_layout)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)

        layout.addWidget(splitter)

        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_bar.showMessage("Pronto - Clique em 'Capturar' para iniciar.")

    def _setup_shortcuts(self) -> None:
        prev_sc = QShortcut(QKeySequence(Qt.Modifier.ALT | Qt.Key.Key_Left), self)
        prev_sc.activated.connect(self._on_previous)
        next_sc = QShortcut(QKeySequence(Qt.Modifier.ALT | Qt.Key.Key_Right), self)
        next_sc.activated.connect(self._on_next)

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def _open_capture_selector(self) -> None:
        self.hide()
        QTimer.singleShot(300, self._show_selector)

    def _show_selector(self) -> None:
        self._selector = RegionSelector()
        self._selector.region_selected.connect(self._on_region_selected)
        self._selector.showFullScreen()

    @Slot(Region)
    def _on_region_selected(self, region: Region) -> None:
        self.show()
        self._controller.start_capture(region)

    @Slot(int)
    def _on_capture_completed(self, capture_id: int) -> None:
        self._status_bar.showMessage("Captura concluida.", 5000)

    # ------------------------------------------------------------------
    # History & Navigation
    # ------------------------------------------------------------------

    @Slot(int)
    def _on_history_item_selected(self, capture_id: int) -> None:
        self._controller.load_capture(capture_id)

    @Slot(int)
    def _on_archive_requested(self, capture_id: int) -> None:
        self._controller.archive_capture(capture_id)

    @Slot(int)
    def _on_unarchive_requested(self, capture_id: int) -> None:
        self._controller.unarchive_capture(capture_id)

    @Slot(int)
    def _on_delete_requested(self, capture_id: int) -> None:
        self._controller.delete_capture(capture_id)

    @Slot()
    def _on_previous(self) -> None:
        self._controller.go_previous()

    @Slot()
    def _on_next(self) -> None:
        self._controller.go_next()

    @Slot(bool, bool)
    def _on_navigation_changed(self, has_prev: bool, has_next: bool) -> None:
        self._update_nav_buttons(has_prev, has_next)

    def _update_nav_buttons(self, has_prev: bool, has_next: bool) -> None:
        if self._prev_btn:
            self._prev_btn.setEnabled(has_prev)
        if self._next_btn:
            self._next_btn.setEnabled(has_next)

    # ------------------------------------------------------------------
    # Translation display
    # ------------------------------------------------------------------

    @Slot(str, int, int)
    def _on_translation_loaded(
        self,
        text: str,
        capture_id: int,
        translation_id: int,
    ) -> None:
        if self._reader:
            self._reader.set_text(text)
            self._controller.apply_highlights(self._reader.editor, translation_id)

        self._current_translation_id = translation_id

        if self._history_panel:
            self._history_panel.set_current(capture_id, switch_tab=False)

        self._status_bar.showMessage(
            f"Carregada captura #{capture_id} - {len(text)} caracteres",
            5000,
        )

    # ------------------------------------------------------------------
    # Highlights
    # ------------------------------------------------------------------

    @Slot(int, int, str)
    def _on_highlight_requested(self, start: int, end: int, color: str) -> None:
        hl = self._controller.add_highlight(
            self._current_translation_id, start, end, color
        )
        if hl and self._reader:
            self._controller.highlight_renderer.apply_single(
                self._reader.editor, hl
            )
            self._status_bar.showMessage(
                f"Destaque adicionado ({color}).", 3000
            )

    @Slot(int, int)
    def _on_highlight_removed(self, start: int, end: int) -> None:
        self._controller.remove_highlight(
            self._current_translation_id, start, end
        )
        if self._reader:
            self._controller.apply_highlights(
                self._reader.editor, self._current_translation_id
            )
            self._status_bar.showMessage("Destaque removido.", 3000)

    # ------------------------------------------------------------------
    # Status messages
    # ------------------------------------------------------------------

    @Slot(str)
    def _on_status_message(self, message: str) -> None:
        self._status_bar.showMessage(message, 5000)

    @Slot(object)
    def _on_history_updated(
        self,
        data: tuple,
    ) -> None:
        if self._history_panel:
            captures, translations = data
            self._history_panel.load(captures, translations)

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def closeEvent(self, event) -> None:
        self._controller.cleanup()
        super().closeEvent(event)
