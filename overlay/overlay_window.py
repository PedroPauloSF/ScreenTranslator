"""
Transparent overlay window.

Displays translated text as a floating, borderless window
that follows the monitored screen region.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRect, Signal, Slot, QPoint
from PySide6.QtGui import (
    QColor,
    QFont,
    QPainter,
    QTextOption,
    QMouseEvent,
)
from PySide6.QtWidgets import QWidget, QApplication

from config.settings import OverlaySettings, Region
from utils.logger import get_logger

logger = get_logger(__name__)

_PLACEHOLDER = "Waiting for text..."


class OverlayWindow(QWidget):
    """A frameless, translucent window that displays translated text.

    Shows a placeholder immediately so the user knows where the
    translation will appear.

    Signals:
        text_updated: Emitted when the displayed text changes (str).
    """

    text_updated = Signal(str)

    def __init__(
        self,
        overlay_settings: OverlaySettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Initialize the overlay window.

        Args:
            overlay_settings: Visual configuration for the overlay.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._settings = overlay_settings or OverlaySettings()
        self._translated_text: str = _PLACEHOLDER
        self._monitor_region: Region = Region()

        self._dragging: bool = False
        self._drag_offset: QPoint = QPoint()

        self._setup_window()
        self._apply_settings()
        self._show_placeholder()

    def _setup_window(self) -> None:
        """Configure the window flags and attributes for transparency."""
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setMinimumSize(200, 40)

    def _show_placeholder(self) -> None:
        """Display the placeholder text so the user sees where the overlay is."""
        self._translated_text = _PLACEHOLDER
        self._recalculate_size()
        self.show()

    def _apply_settings(self) -> None:
        """Apply visual settings to the overlay."""
        s = self._settings

        self._font = QFont(s.font_family, s.font_size)
        self._font.setStyleHint(QFont.StyleHint.SansSerif)

        self._text_color = QColor(s.text_color)
        self._bg_color = QColor(s.background_color)
        self._bg_color.setAlphaF(s.opacity)

        self._margins = (s.margin_horizontal, s.margin_vertical)
        self._line_spacing = s.line_spacing

    def update_settings(self, settings: OverlaySettings) -> None:
        """Apply new overlay settings at runtime."""
        self._settings = settings
        self._apply_settings()
        self._recalculate_size()
        self.update()

    def set_monitor_region(self, region: Region) -> None:
        """Set the screen region that the overlay should follow."""
        self._monitor_region = region
        self._reposition()

    @Slot(str)
    def set_text(self, text: str) -> None:
        """Update the displayed translated text."""
        if text == self._translated_text:
            return

        self._translated_text = text
        self._recalculate_size()
        self.update()
        self.text_updated.emit(text)

    def _get_screen_geometry(self) -> QRect:
        """Get the screen geometry, handling the case where self.screen() is None."""
        screen = self.screen()
        if screen is not None:
            return screen.availableGeometry()

        app = QApplication.instance()
        if app is not None and app.primaryScreen() is not None:
            return app.primaryScreen().availableGeometry()

        return QRect(0, 0, 1920, 1080)

    def _reposition(self) -> None:
        """Move the overlay to the right (or below) the monitored region."""
        region = self._monitor_region
        if not region.is_valid:
            return

        screen_geo = self._get_screen_geometry()
        gap = 8

        pref_x = region.left + region.width + gap
        pref_y = region.top

        if pref_x + self.width() > screen_geo.right():
            pref_x = max(screen_geo.left(), region.left)
            pref_y = region.top + region.height + gap
            if pref_y + self.height() > screen_geo.bottom():
                pref_y = max(screen_geo.top(), region.top - self.height() - gap)

        pref_x = max(screen_geo.left(), min(pref_x, screen_geo.right() - self.width()))
        pref_y = max(screen_geo.top(), min(pref_y, screen_geo.bottom() - self.height()))

        self.move(pref_x, pref_y)

    def _recalculate_size(self) -> None:
        """Adjust window size to fit the current text."""
        if not self._translated_text.strip():
            self.resize(0, 0)
            self.hide()
            return

        s = self._settings
        self.setFont(QFont(self._font))
        fm = self.fontMetrics()
        max_width = 700

        text_rect = fm.boundingRect(
            QRect(0, 0, max_width, 10000),
            Qt.TextFlag.TextWordWrap,
            self._translated_text,
        )

        width = max(
            min(text_rect.width() + s.margin_horizontal * 2, max_width),
            self.minimumWidth(),
        )
        height = max(
            text_rect.height() + s.margin_vertical * 2,
            self.minimumHeight(),
        )

        self.resize(width, height + 4)
        self._reposition()
        self.show()

    def mousePressEvent(self, event: QMouseEvent) -> None:
        """Begin dragging the overlay."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._drag_offset = event.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        """Move the overlay while dragging."""
        if self._dragging:
            new_pos = event.globalPosition().toPoint() - self._drag_offset
            self.move(new_pos)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        """End dragging."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = False

    def paintEvent(self, event) -> None:
        """Paint the transparent background and text."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing)

        if self._translated_text.strip():
            painter.setBrush(self._bg_color)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawRoundedRect(self.rect(), 8, 8)

            painter.setFont(self._font)
            painter.setPen(self._text_color)

            s = self._settings
            text_rect = self.rect().adjusted(
                s.margin_horizontal, s.margin_vertical,
                -s.margin_horizontal, -s.margin_vertical,
            )

            option = QTextOption()
            option.setWrapMode(QTextOption.WrapMode.WordWrap)
            painter.drawText(text_rect, Qt.TextFlag.TextWordWrap, self._translated_text)
