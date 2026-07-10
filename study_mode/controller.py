"""
Study mode controller.

Orchestrates the manual capture -> OCR -> translate -> persist
pipeline for the study mode. Manages navigation between history
entries and coordinates the reader, history panel, and highlights.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from config.settings import AppSettings, Region
from translation.translator import Translator
from database.models import CaptureRecord, OCRRecord, TranslationRecord
from database.repository import (
    CaptureRepository,
    OCRRepository,
    TranslationRepository,
)
from annotations.highlight_manager import HighlightManager
from annotations.highlight_renderer import HighlightRenderer
from annotations.models import Highlight
from study_mode.capture_action import CaptureAction
from utils.logger import get_logger

logger = get_logger(__name__)


class StudyController(QObject):
    """Controls the study mode workflow.

    Manages capture actions, history navigation, and highlight
    rendering on the study reader widget.

    Signals:
        translation_loaded: Emitted when a translation is ready to display.
                            (text, capture_id, translation_id)
        history_updated: Emitted when the history list should be refreshed.
        status_message: Emitted with status bar messages.
        capture_completed: Emitted with the new capture_id.
        navigation_changed: Emitted when prev/next availability changes.
                            (has_previous, has_next)
    """

    translation_loaded = Signal(str, int, int)
    history_updated = Signal(object)
    status_message = Signal(str)
    capture_completed = Signal(int)
    navigation_changed = Signal(bool, bool)

    def __init__(
        self,
        settings: AppSettings,
        translator: Translator,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the study controller.

        Args:
            settings: Application settings.
            translator: Translator instance.
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._settings = settings
        self._translator = translator

        self._capture_repo = CaptureRepository()
        self._ocr_repo = OCRRepository()
        self._translation_repo = TranslationRepository()
        self._highlight_manager = HighlightManager()
        self._highlight_renderer = HighlightRenderer(self._highlight_manager)

        self._captures: list[CaptureRecord] = []
        self._current_index: int = -1
        self._current_capture: CaptureRecord | None = None
        self._current_translation: TranslationRecord | None = None

        self._capture_action: CaptureAction | None = None

    @property
    def highlight_renderer(self) -> HighlightRenderer:
        """Return the highlight renderer for applying to the reader."""
        return self._highlight_renderer

    @property
    def highlight_manager(self) -> HighlightManager:
        """Return the highlight manager for creating/removing highlights."""
        return self._highlight_manager

    # ------------------------------------------------------------------
    # Capture
    # ------------------------------------------------------------------

    def start_capture(self, region: Region) -> None:
        """Begin a new manual capture.

        Args:
            region: Screen region to capture.
        """
        self._capture_action = CaptureAction()
        self._capture_action.completed.connect(self._on_capture_done)
        self._capture_action.failed.connect(self._on_capture_failed)
        self._capture_action.execute(region, self._translator, self._settings)
        self.status_message.emit("Capturando e traduzindo...")

    @Slot(int)
    def _on_capture_done(self, capture_id: int) -> None:
        """Handle successful capture completion.

        Args:
            capture_id: The new capture's ID.
        """
        self.status_message.emit("Captura concluida.")
        self._load_history()
        self.load_capture(capture_id)
        self.capture_completed.emit(capture_id)

    @Slot(str)
    def _on_capture_failed(self, error: str) -> None:
        """Handle capture failure.

        Args:
            error: Error message.
        """
        self.status_message.emit(f"Falha na captura: {error}")
        logger.error("Capture failed: %s", error)

    # ------------------------------------------------------------------
    # History & Navigation
    # ------------------------------------------------------------------

    def _load_history(self) -> None:
        self._captures = self._capture_repo.get_all(archived=None)
        translations: dict[int, TranslationRecord] = {}
        for capture in self._captures:
            tl = self._translation_repo.get_by_capture(capture.id)
            if tl:
                translations[capture.id] = tl
        self.history_updated.emit((self._captures, translations))
        self._update_navigation_state()

    def load_history(self) -> None:
        self._load_history()

    def archive_capture(self, capture_id: int) -> None:
        self._capture_repo.archive(capture_id)
        self._load_history()
        if self._current_capture and self._current_capture.id == capture_id:
            self._current_capture = self._capture_repo.get_by_id(capture_id)
        self.status_message.emit("Captura arquivada.")

    def unarchive_capture(self, capture_id: int) -> None:
        self._capture_repo.unarchive(capture_id)
        self._load_history()
        if self._current_capture and self._current_capture.id == capture_id:
            self._current_capture = self._capture_repo.get_by_id(capture_id)
        self.status_message.emit("Captura restaurada.")

    def delete_capture(self, capture_id: int) -> None:
        was_current = self._current_capture and self._current_capture.id == capture_id
        self._capture_repo.delete(capture_id)
        self._load_history()
        if was_current:
            active = self._capture_repo.get_all()
            if active:
                self.load_capture(active[0].id)
            else:
                self._current_capture = None
                self._current_translation = None
                self.translation_loaded.emit("", 0, 0)
        self.status_message.emit("Captura excluida.")

    def load_capture(self, capture_id: int) -> None:
        """Load and display a specific capture by ID.

        Args:
            capture_id: The capture ID to load.
        """
        for idx, capture in enumerate(self._captures):
            if capture.id == capture_id:
                self._current_index = idx
                self._current_capture = capture
                break
        else:
            capture = self._capture_repo.get_by_id(capture_id)
            if capture:
                self._current_capture = capture
                self._current_index = -1

        if self._current_capture is None:
            return

        translation = self._translation_repo.get_by_capture(capture_id)
        self._current_translation = translation

        text = translation.translated_text if translation else ""
        translation_id = translation.id if translation else 0
        self.translation_loaded.emit(text, capture_id, translation_id)
        self._update_navigation_state()

    def go_previous(self) -> None:
        active = [c for c in self._captures if not c.archived]
        if self._current_capture is None:
            return
        try:
            idx = active.index(self._current_capture)
        except ValueError:
            return
        if idx < len(active) - 1:
            self.load_capture(active[idx + 1].id)

    def go_next(self) -> None:
        active = [c for c in self._captures if not c.archived]
        if self._current_capture is None:
            return
        try:
            idx = active.index(self._current_capture)
        except ValueError:
            return
        if idx > 0:
            self.load_capture(active[idx - 1].id)

    def _update_navigation_state(self) -> None:
        active = [c for c in self._captures if not c.archived]
        try:
            current_active_idx = active.index(self._current_capture) if self._current_capture and not self._current_capture.archived else -1
        except ValueError:
            current_active_idx = -1
        has_prev = current_active_idx < len(active) - 1
        has_next = current_active_idx > 0
        self.navigation_changed.emit(has_prev, has_next)

    @property
    def current_capture(self) -> CaptureRecord | None:
        """Return the currently loaded capture."""
        return self._current_capture

    @property
    def current_translation(self) -> TranslationRecord | None:
        """Return the currently loaded translation."""
        return self._current_translation

    # ------------------------------------------------------------------
    # Highlights
    # ------------------------------------------------------------------

    def add_highlight(self, translation_id: int, start: int, end: int, color: str) -> Highlight | None:
        """Create a highlight for the given translation.

        Args:
            translation_id: Translation ID to annotate.
            start: Start offset in text.
            end: End offset in text.
            color: Hex color string.

        Returns:
            The created Highlight, or None if no translation is loaded.
        """
        if translation_id <= 0:
            return None
        return self._highlight_manager.highlight(translation_id, start, end, color)

    def remove_highlight(self, translation_id: int, start: int, end: int) -> None:
        """Remove highlights that overlap the given range.

        Args:
            translation_id: Translation ID.
            start: Start offset of selection.
            end: End offset of selection.
        """
        if translation_id > 0:
            self._highlight_manager.remove_in_range(translation_id, start, end)

    def apply_highlights(self, editor, translation_id: int) -> None:
        """Apply saved highlights to the editor widget.

        Args:
            editor: QTextEdit widget.
            translation_id: Translation ID.
        """
        if translation_id > 0:
            self._highlight_renderer.apply(editor, translation_id)

    def cleanup(self) -> None:
        """Release resources."""
        pass
