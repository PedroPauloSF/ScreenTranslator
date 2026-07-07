"""
Region border overlay.

Draws a visible colored border around the monitored screen region
so the user always knows what area is being captured.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRect
from PySide6.QtGui import QColor, QPainter, QPen
from PySide6.QtWidgets import QWidget

from config.settings import Region


class RegionBorder(QWidget):
    """A transparent, border-only window outlining the monitored region.

    Always on top, frameless, and click-through so it doesn't
    interfere with the content being captured.
    """

    BORDER_WIDTH = 3
    BORDER_COLOR = QColor(0, 180, 255, 200)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the border overlay."""
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._region: Region | None = None

    def set_region(self, region: Region) -> None:
        """Position and size the border to match the monitored region.

        Args:
            region: The monitored screen region.
        """
        self._region = region
        self.setGeometry(region.left, region.top, region.width, region.height)
        self.show()

    def paintEvent(self, event) -> None:
        """Draw the border rectangle."""
        if self._region is None:
            return

        painter = QPainter(self)
        pen = QPen(self.BORDER_COLOR, self.BORDER_WIDTH)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self.rect().adjusted(1, 1, -1, -1))
