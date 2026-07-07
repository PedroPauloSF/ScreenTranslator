"""
Google Translate plugin for Screen Translator.

Uses deep-translator (Google Translate backend) for free,
no API key required. Translates English to Portuguese (Brazil).
"""

from translation.translator import Translator


class GoogleTranslator(Translator):
    """Real translation plugin using Google Translate via deep-translator."""

    def __init__(self) -> None:
        self._translator = None

    @property
    def name(self) -> str:
        return "GoogleTranslator"

    @property
    def source_language(self) -> str:
        return "en"

    @property
    def target_language(self) -> str:
        return "pt"

    def translate(self, text: str) -> str:
        """Translate English text to Portuguese (Brazil).

        Args:
            text: Source text in English.

        Returns:
            Translated text in Portuguese.
        """
        if not text.strip():
            return text

        if self._translator is None:
            from deep_translator import GoogleTranslator as GT
            self._translator = GT(source="en", target="pt")

        try:
            result = self._translator.translate(text)
            return result if result else text
        except Exception:
            return f"[translation failed] {text}"
