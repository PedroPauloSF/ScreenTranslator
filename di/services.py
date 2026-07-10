"""
Dependency injection — Service Provider.

Provides a single entry point for creating and caching shared service
instances. Used by both continuous mode and study mode to obtain the
core capture, OCR, and translation services without importing each
other's modules.
"""

from __future__ import annotations

from config.settings import AppSettings
from capture.screen_capture import ScreenCapture
from ocr.engine import OCREngine
from translation.translator import Translator


class ServiceProvider:
    """Factory that creates and provides shared service instances.

    Shared services (ScreenCapture, Translator) are cached.
    OCREngine is recreated on demand since the language may change.
    Study-mode-only services (repositories, highlight manager) are
    lazily imported to avoid coupling continuous mode to the database.
    """

    def __init__(self, settings: AppSettings) -> None:
        """Initialize the service provider.

        Args:
            settings: Application settings containing OCR, translation config.
        """
        self._settings = settings
        self._screen_capture: ScreenCapture | None = None
        self._translator: Translator | None = None

    @property
    def screen_capture(self) -> ScreenCapture:
        """Return a cached ScreenCapture instance."""
        if self._screen_capture is None:
            self._screen_capture = ScreenCapture()
        return self._screen_capture

    def create_ocr_engine(self, language: str | None = None) -> OCREngine:
        """Create a new OCREngine instance.

        Not cached because the language may be changed at runtime.

        Args:
            language: OCR language code (defaults to settings value).

        Returns:
            A new OCREngine instance.
        """
        lang = language or self._settings.ocr.language
        return OCREngine(language=lang)

    @property
    def settings(self) -> AppSettings:
        """Return the application settings."""
        return self._settings

    def set_translator(self, translator: Translator) -> None:
        """Store a Translator instance for retrieval by either mode.

        Args:
            translator: A Translator instance.
        """
        self._translator = translator

    @property
    def translator(self) -> Translator | None:
        """Return the cached Translator instance."""
        return self._translator
