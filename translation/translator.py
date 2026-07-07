"""
Abstract Translator interface.

Defines the contract that all translation plugins must implement.
The rest of the application depends ONLY on this interface,
never on concrete implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class Translator(ABC):
    """Abstract base class for all translation providers.

    All translation plugins MUST inherit from this class and
    implement the translate method.

    The application core never imports or references concrete
    translator implementations directly.
    """

    @abstractmethod
    def translate(self, text: str) -> str:
        """Translate text from the source language to the target language.

        Args:
            text: The source text to translate.

        Returns:
            The translated text.
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of this translator (e.g. 'GoogleTranslate')."""
        ...

    @property
    @abstractmethod
    def source_language(self) -> str:
        """Source language code (e.g. 'en')."""
        ...

    @property
    @abstractmethod
    def target_language(self) -> str:
        """Target language code (e.g. 'pt')."""
        ...
