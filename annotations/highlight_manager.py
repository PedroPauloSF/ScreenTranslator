"""
Highlight manager.

Handles business logic for creating, removing, and retrieving highlights.
Operates on the repository layer and produces in-memory Highlight objects.
"""

from __future__ import annotations

from annotations.models import Highlight
from database.repository import HighlightRepository
from utils.logger import get_logger

logger = get_logger(__name__)


class HighlightManager:
    """Manages text highlights for the study mode.

    Does NOT modify the original translated text.
    Highlights are stored as (start, end, color) offsets
    in a separate database table.
    """

    def __init__(self, repository: HighlightRepository | None = None) -> None:
        """Initialize the highlight manager.

        Args:
            repository: HighlightRepository instance.
                        Created lazily if not provided.
        """
        self._repo = repository or HighlightRepository()

    def highlight(
        self,
        translation_id: int,
        start_offset: int,
        end_offset: int,
        color: str = "#FFFF00",
    ) -> Highlight:
        """Create a new highlight on the translation text.

        Args:
            translation_id: ID of the translation to annotate.
            start_offset: Character position where highlight starts.
            end_offset: Character position where highlight ends.
            color: Hex color string (default yellow).

        Returns:
            The newly created Highlight.
        """
        hl_id = self._repo.insert(translation_id, start_offset, end_offset, color)
        return Highlight(
            id=hl_id,
            translation_id=translation_id,
            start_offset=start_offset,
            end_offset=end_offset,
            color=color,
        )

    def remove(self, highlight_id: int) -> None:
        """Delete a highlight by ID.

        Args:
            highlight_id: The highlight's database ID.
        """
        self._repo.delete(highlight_id)

    def remove_in_range(
        self,
        translation_id: int,
        selection_start: int,
        selection_end: int,
    ) -> None:
        """Remove all highlights that overlap with a selection range.

        Args:
            translation_id: Translation ID.
            selection_start: Start of the user's text selection.
            selection_end: End of the user's text selection.
        """
        self._repo.delete_in_range(translation_id, selection_start, selection_end)

    def get_for_translation(self, translation_id: int) -> list[Highlight]:
        """Retrieve all highlights for a translation.

        Args:
            translation_id: Translation ID.

        Returns:
            List of Highlight objects sorted by offset.
        """
        records = self._repo.get_by_translation(translation_id)
        return [
            Highlight(
                id=r.id,
                translation_id=r.translation_id,
                start_offset=r.start_offset,
                end_offset=r.end_offset,
                color=r.color,
            )
            for r in records
        ]
