"""
Study reader widget.

A read-only text viewer that displays translated text with
highlight annotations support. Users can select, copy, and
search text but cannot edit it.

Includes a toolbar with highlight color buttons, font size controls,
and a right-click context menu for additional options.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot, QSize
from PySide6.QtGui import QAction, QKeySequence, QTextCursor, QColor, QIcon, QPixmap, QPainter, QFont
from PySide6.QtWidgets import (
    QTextEdit,
    QMenu,
    QWidget,
    QVBoxLayout,
    QLineEdit,
    QHBoxLayout,
    QToolButton,
    QLabel,
    QSpinBox,
)

from annotations.models import AVAILABLE_COLORS
from utils.logger import get_logger

logger = get_logger(__name__)


def _make_color_icon(hex_color: str) -> QIcon:
    """Create a small filled square icon for a color button."""
    pixmap = QPixmap(18, 18)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setBrush(QColor(hex_color))
    painter.setPen(QColor(100, 100, 100))
    painter.drawRoundedRect(1, 1, 16, 16, 3, 3)
    painter.end()
    return QIcon(pixmap)


class StudyReader(QWidget):
    """Read-only text viewer with highlight toolbar and search support.

    Signals:
        highlight_requested: Emitted when user selects text and picks a color.
        highlight_removed: Emitted when user removes a highlight at position.
    """

    highlight_requested = Signal(int, int, str)
    highlight_removed = Signal(int, int)

    _DEFAULT_FONT_SIZE = 14
    _MIN_FONT_SIZE = 8
    _MAX_FONT_SIZE = 48

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._editor: QTextEdit | None = None
        self._search_bar: QWidget | None = None
        self._search_input: QLineEdit | None = None
        self._highlight_bar: QWidget | None = None
        self._font_bar: QWidget | None = None
        self._color_buttons: list = []
        self._remove_btn: QToolButton | None = None
        self._font_spin: QSpinBox | None = None
        self._font_size: int = self._DEFAULT_FONT_SIZE
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        search_layout = QHBoxLayout()
        search_layout.setContentsMargins(0, 0, 0, 2)
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Buscar na traducao...")
        self._search_input.setClearButtonEnabled(True)
        self._search_input.textChanged.connect(self._on_search)
        search_layout.addWidget(self._search_input)
        close_btn = QToolButton()
        close_btn.setText("x")
        close_btn.clicked.connect(self._hide_search)
        search_layout.addWidget(close_btn)
        self._search_bar = QWidget()
        self._search_bar.setLayout(search_layout)
        self._search_bar.hide()
        layout.addWidget(self._search_bar)

        toolbar_layout = QHBoxLayout()
        toolbar_layout.setContentsMargins(0, 2, 0, 2)
        toolbar_layout.setSpacing(2)

        hl_label = QLabel("Destaque:")
        hl_label.setFixedWidth(55)
        hl_label.setStyleSheet("color: #888;")
        toolbar_layout.addWidget(hl_label)

        for hex_color, name in AVAILABLE_COLORS:
            btn = QToolButton()
            btn.setIcon(_make_color_icon(hex_color))
            btn.setToolTip(f"Destaque {name}")
            btn.setIconSize(QSize(18, 18))
            btn.setFixedSize(26, 26)
            btn.setEnabled(False)
            btn.clicked.connect(
                lambda checked=False, c=hex_color: self._request_highlight(c)
            )
            toolbar_layout.addWidget(btn)
            self._color_buttons.append((btn, hex_color))

        toolbar_layout.addSpacing(8)

        self._remove_btn = QToolButton()
        self._remove_btn.setText("Remover")
        self._remove_btn.setToolTip("Remover destaque da selecao")
        self._remove_btn.setEnabled(False)
        self._remove_btn.clicked.connect(self._request_remove_highlight)
        toolbar_layout.addWidget(self._remove_btn)

        toolbar_layout.addStretch()

        font_label = QLabel("Fonte:")
        font_label.setStyleSheet("color: #888;")
        toolbar_layout.addWidget(font_label)

        decrease_btn = QToolButton()
        decrease_btn.setText("A-")
        decrease_btn.setToolTip("Diminuir tamanho da fonte")
        decrease_btn.setFixedSize(30, 26)
        decrease_btn.clicked.connect(self._decrease_font)
        toolbar_layout.addWidget(decrease_btn)

        increase_btn = QToolButton()
        increase_btn.setText("A+")
        increase_btn.setToolTip("Aumentar tamanho da fonte")
        increase_btn.setFixedSize(30, 26)
        increase_btn.clicked.connect(self._increase_font)
        toolbar_layout.addWidget(increase_btn)

        self._highlight_bar = QWidget()
        self._highlight_bar.setLayout(toolbar_layout)
        layout.addWidget(self._highlight_bar)

        self._editor = QTextEdit()
        self._editor.setReadOnly(True)
        self._editor.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self._editor.customContextMenuRequested.connect(self._on_context_menu)
        self._editor.selectionChanged.connect(self._on_selection_changed)
        self._apply_font()
        layout.addWidget(self._editor)

    def _apply_font(self) -> None:
        if self._editor:
            font = QFont()
            font.setPointSize(self._font_size)
            font.setStyleHint(QFont.StyleHint.SansSerif)
            self._editor.setFont(font)

    def _decrease_font(self) -> None:
        if self._font_size > self._MIN_FONT_SIZE:
            self._font_size = max(self._MIN_FONT_SIZE, self._font_size - 2)
            self._apply_font()

    def _increase_font(self) -> None:
        if self._font_size < self._MAX_FONT_SIZE:
            self._font_size = min(self._MAX_FONT_SIZE, self._font_size + 2)
            self._apply_font()

    def set_text(self, text: str) -> None:
        if self._editor:
            self._editor.setPlainText(text)
            self._apply_font()

    def text(self) -> str:
        return self._editor.toPlainText() if self._editor else ""

    def clear(self) -> None:
        if self._editor:
            self._editor.clear()
            self._editor.setExtraSelections([])

    @property
    def editor(self) -> QTextEdit | None:
        return self._editor

    def show_search(self) -> None:
        if self._search_bar:
            self._search_bar.show()
            self._search_input.setFocus()
            self._search_input.selectAll()

    def _hide_search(self) -> None:
        if self._search_bar:
            self._search_bar.hide()

    @Slot(str)
    def _on_search(self, text: str) -> None:
        if not self._editor:
            return
        cursor = self._editor.textCursor()
        cursor.clearSelection()
        self._editor.setTextCursor(cursor)
        if not text:
            return
        found = self._editor.find(text)
        if not found:
            cursor.movePosition(QTextCursor.MoveOperation.Start)
            self._editor.setTextCursor(cursor)
            self._editor.find(text)

    def _on_selection_changed(self) -> None:
        if not self._editor:
            return
        has_selection = self._editor.textCursor().hasSelection()
        for btn, _ in self._color_buttons:
            btn.setEnabled(has_selection)
        if self._remove_btn:
            self._remove_btn.setEnabled(has_selection)

    def _on_context_menu(self, pos) -> None:
        if not self._editor:
            return
        cursor = self._editor.textCursor()
        if not cursor.hasSelection():
            return

        menu = QMenu(self)

        copy_action = QAction("Copiar", menu)
        copy_action.setShortcut(QKeySequence.StandardKey.Copy)
        copy_action.triggered.connect(self._editor.copy)
        menu.addAction(copy_action)

        highlight_menu = menu.addMenu("Cor do destaque")

        for hex_color, name in AVAILABLE_COLORS:
            action = QAction(name, menu)
            pixmap = QPixmap(16, 16)
            pixmap.fill(QColor(hex_color))
            action.setIcon(QIcon(pixmap))
            action.triggered.connect(
                lambda checked=False, c=hex_color: self._request_highlight(c)
            )
            highlight_menu.addAction(action)

        remove_action = QAction("Remover destaque", menu)
        remove_action.triggered.connect(self._request_remove_highlight)
        menu.addAction(remove_action)

        menu.exec_(self._editor.viewport().mapToGlobal(pos))

    def _request_highlight(self, color: str) -> None:
        if not self._editor:
            return
        cursor = self._editor.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        if start < end:
            self.highlight_requested.emit(start, end, color)

    def _request_remove_highlight(self) -> None:
        if not self._editor:
            return
        cursor = self._editor.textCursor()
        start = cursor.selectionStart()
        end = cursor.selectionEnd()
        if start < end:
            self.highlight_removed.emit(start, end)

    def keyPressEvent(self, event) -> None:
        if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
            if event.key() == Qt.Key.Key_F:
                self.show_search()
                return
        super().keyPressEvent(event)
