"""
Highlight renderer.

Applies highlight annotations to a QTextEdit widget via Qt's
ExtraSelections mechanism. Highlights are visual-only overlays;
the underlying text is never modified.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCharFormat, QTextCursor
from PySide6.QtWidgets import QTextEdit

from annotations.models import Highlight
from annotations.highlight_manager import HighlightManager
from utils.logger import get_logger

logger = get_logger(__name__)


class HighlightRenderer:
    """Applies highlight overlays on a QTextEdit widget.

    Uses QTextEdit.ExtraSelection to paint colored backgrounds
    over text ranges without altering the document content.
    """

    def __init__(
        self,
        manager: HighlightManager | None = None,
    ) -> None:
        """Initialize the renderer.

        Args:
            manager: HighlightManager instance. Created lazily if None.
        """
        self._manager = manager or HighlightManager()

    def apply(
        self,
        editor: QTextEdit,
        translation_id: int,
    ) -> None:
        """Apply all highlights for a translation to the editor.

        Args:
            editor: Target QTextEdit widget.
            translation_id: Translation ID whose highlights to render.
        """
        highlights = self._manager.get_for_translation(translation_id)
        extras = []

        for hl in highlights:
            fmt = QTextCharFormat()
            fmt.setBackground(self._parse_color(hl.color))
            fmt.setProperty(QTextCharFormat.Property.FullWidthSelection, False)

            cursor = QTextCursor(editor.document())
            cursor.setPosition(hl.start_offset)
            cursor.setPosition(hl.end_offset, QTextCursor.MoveMode.KeepAnchor)

            extra = QTextEdit.ExtraSelection()
            extra.format = fmt
            extra.cursor = cursor
            extras.append(extra)

        editor.setExtraSelections(extras)

    def apply_single(
        self,
        editor: QTextEdit,
        highlight: Highlight,
    ) -> None:
        """Apply a single highlight to the editor (adds to existing ones).

        Args:
            editor: Target QTextEdit widget.
            highlight: The highlight to apply.
        """
        extras = list(editor.extraSelections())

        fmt = QTextCharFormat()
        fmt.setBackground(self._parse_color(highlight.color))

        cursor = QTextCursor(editor.document())
        cursor.setPosition(highlight.start_offset)
        cursor.setPosition(highlight.end_offset, QTextCursor.MoveMode.KeepAnchor)

        extra = QTextEdit.ExtraSelection()
        extra.format = fmt
        extra.cursor = cursor
        extras.append(extra)

        editor.setExtraSelections(extras)

    def clear(self, editor: QTextEdit) -> None:
        """Remove all highlight overlays from the editor.

        Args:
            editor: Target QTextEdit widget.
        """
        editor.setExtraSelections([])

    @staticmethod
    def _parse_color(hex_color: str) -> QColor:
        """Parse a hex color string into a QColor with alpha.

        Args:
            hex_color: Color string like '#FFFF00'.

        Returns:
            QColor with 50% alpha for overlaying.
        """
        color = QColor(hex_color)
        color.setAlpha(80)
        return color
