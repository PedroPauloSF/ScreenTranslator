"""
Region selection overlay.

Displays a fullscreen darkened overlay where the user can
click and drag to select a rectangular screen region for monitoring.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QRect, QPoint, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QBrush
from PySide6.QtWidgets import QWidget

from config.settings import Region

SELECTION_DONE = "selection_done"


class RegionSelector(QWidget):
    """Fullscreen overlay for selecting a screen region.

    The screen darkens and the user draws a rectangle by clicking
    and dragging. On release, the region is emitted via signal.

    Usage:
        selector = RegionSelector()
        selector.region_selected.connect(on_region)
        selector.showFullScreen()
    """

    region_selected = Signal(Region)

    def __init__(self, parent: QWidget | None = None) -> None:
        """Initialize the region selector overlay."""
        super().__init__(parent)
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCursor(Qt.CursorShape.CrossCursor)

        self._start_point: QPoint | None = None
        self._end_point: QPoint | None = None
        self._selecting: bool = False

        self._overlay_color = QColor(0, 0, 0, 80)
        self._border_color = QColor(0, 180, 255)
        self._fill_color = QColor(0, 180, 255, 40)

    def keyPressEvent(self, event) -> None:
        """Handle escape key to cancel selection."""
        if event.key() == Qt.Key.Key_Escape:
            self._reset_selection()
            self.close()

    def mousePressEvent(self, event) -> None:
        """Start drawing the selection rectangle."""
        if event.button() == Qt.MouseButton.LeftButton:
            self._start_point = event.position().toPoint()
            self._end_point = self._start_point
            self._selecting = True
            self.update()

    def mouseMoveEvent(self, event) -> None:
        """Update the selection rectangle while dragging."""
        if self._selecting:
            self._end_point = event.position().toPoint()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        """Finalize the selection and emit the region."""
        if event.button() == Qt.MouseButton.LeftButton and self._selecting:
            self._selecting = False
            region = self._to_region()
            if region and region.is_valid:
                self.region_selected.emit(region)
                self.close()
            else:
                self._reset_selection()

    def _to_region(self) -> Region | None:
        """Convert start/end points to a Region dataclass.

        Returns:
            Region if valid, None otherwise.
        """
        if self._start_point is None or self._end_point is None:
            return None

        x1 = min(self._start_point.x(), self._end_point.x())
        y1 = min(self._start_point.y(), self._end_point.y())
        x2 = max(self._start_point.x(), self._end_point.x())
        y2 = max(self._start_point.y(), self._end_point.y())

        width = x2 - x1
        height = y2 - y1

        if width < 10 or height < 10:
            return None

        return Region(left=x1, top=y1, width=width, height=height)

    def _reset_selection(self) -> None:
        """Reset the selection state."""
        self._start_point = None
        self._end_point = None
        self._selecting = False
        self.update()

    def paintEvent(self, event) -> None:
        """Draw the darkened overlay and the selection rectangle."""
        painter = QPainter(self)

        painter.fillRect(self.rect(), self._overlay_color)

        if self._start_point is None or self._end_point is None:
            return

        rect = QRect(self._start_point, self._end_point).normalized()

        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
        painter.fillRect(rect, Qt.GlobalColor.transparent)
        painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)

        pen = QPen(self._border_color, 2)
        pen.setStyle(Qt.PenStyle.SolidLine)
        painter.setPen(pen)
        painter.setBrush(self._fill_color)
        painter.drawRect(rect)
