"""
Generic fallback translator.

Placeholder implementation that returns the original text unchanged.
Used when no translation plugin is available.
"""

from __future__ import annotations

from translation.translator import Translator


class GenericTranslator(Translator):
    """Default translator that returns text unchanged.

    This is the fallback when no plugin is loaded. It preserves the
    original text so the application remains fully functional
    even without a translation provider.
    """

    @property
    def name(self) -> str:
        return "GenericTranslator"

    @property
    def source_language(self) -> str:
        return "en"

    @property
    def target_language(self) -> str:
        return "pt"

    def translate(self, text: str) -> str:
        """Return the original text unchanged.

        Args:
            text: Source text.

        Returns:
            The same text, unmodified.
        """
        return text
