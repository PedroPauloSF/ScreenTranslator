"""
Translation worker.

Runs translation in a dedicated thread.
Receives text via slots and emits translated text via signals.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot

from translation.translator import Translator
from utils.logger import get_logger

logger = get_logger(__name__)


class TranslationWorker(QObject):
    """Worker that runs translation in a background thread.

    Receives source text via the translate_text slot and emits
    translation_ready with the translated text.

    Signals:
        translation_ready: Emitted with the translated text.
        translation_error: Emitted with an error message on failure.
    """

    translation_ready = Signal(str)
    translation_error = Signal(str)

    def __init__(
        self,
        translator: Translator,
        parent: QObject | None = None,
    ) -> None:
        """Initialize the translation worker.

        Args:
            translator: A Translator instance (plugin or generic).
            parent: Optional parent QObject.
        """
        super().__init__(parent)
        self._translator = translator

    def set_translator(self, translator: Translator) -> None:
        """Replace the translator instance at runtime.

        Args:
            translator: New Translator instance.
        """
        self._translator = translator
        logger.info("Translator switched to: %s", translator.name)

    @Slot(str)
    def translate_text(self, text: str) -> None:
        """Translate the given text.

        Args:
            text: Source text to translate.
        """
        if not text.strip():
            self.translation_ready.emit("")
            return

        try:
            result = self._translator.translate(text)
            self.translation_ready.emit(result)
        except Exception as e:
            logger.error("Translation failed: %s", e)
            self.translation_error.emit(str(e))
