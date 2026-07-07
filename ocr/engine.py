"""
EasyOCR engine wrapper.

Handles initialization, inference, and text extraction from images.
Operates entirely offline after initial model download.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class OCRResult:
    """Result of a single OCR operation.

    Attributes:
        text: Extracted text with lines joined by spaces.
        confidence: Average confidence across all detected text blocks.
        elapsed_ms: Time spent on OCR inference.
        raw_lines: Individual detected lines with confidence scores.
    """

    text: str
    confidence: float
    elapsed_ms: float
    raw_lines: list[tuple[str, float]] = field(default_factory=list)


class OCREngine:
    """Offline OCR engine powered by EasyOCR.

    The engine is lazily initialized on first use to avoid loading
    the model until it is actually needed.

    EasyOCR handles preprocessing internally (grayscale, threshold, etc.).
    Pass raw BGR images directly.

    Usage:
        engine = OCREngine(language="en")
        result = engine.extract(bgr_image)
        print(result.text)
    """

    _LANG_MAP: dict[str, str] = {
        "en": "en",
        "pt": "pt",
        "es": "es",
        "fr": "fr",
        "de": "de",
        "ch": "ch_sim",
        "jp": "ja",
        "kr": "ko",
    }

    def __init__(self, language: str = "en", max_size: int = 640) -> None:
        """Initialize the OCR engine.

        Args:
            language: Language code (e.g. 'en', 'pt', 'ch' for Chinese simplified).
            max_size: Maximum dimension for OCR input. Larger images are downscaled.
        """
        self._language = language
        self._ocr = None
        self._initialized = False
        self._max_size = max_size

    def _ensure_initialized(self) -> None:
        """Lazy-load the EasyOCR model on first use."""
        if self._initialized:
            return

        easyocr_lang = self._LANG_MAP.get(self._language, self._language)
        logger.info("Initializing EasyOCR (language=%s)...", easyocr_lang)

        try:
            import easyocr

            self._ocr = easyocr.Reader(
                [easyocr_lang],
                gpu=False,
                verbose=False,
            )
            self._initialized = True
            logger.info("EasyOCR initialized successfully.")
        except Exception as e:
            logger.error("Failed to initialize EasyOCR: %s", e)
            raise

    def set_language(self, language: str) -> None:
        """Change the OCR language. Triggers re-initialization.

        Args:
            language: New language code.
        """
        if language != self._language:
            self._language = language
            self._initialized = False
            self._ocr = None
            logger.info("OCR language changed to '%s'. Will reinitialize.", language)

    def _resize_if_needed(self, image: np.ndarray) -> np.ndarray:
        """Downscale image if any dimension exceeds max_size.

        Maintains aspect ratio using INTER_AREA interpolation for
        optimal quality when shrinking text images.

        Args:
            image: BGR image to potentially resize.

        Returns:
            Resized image, or original if already within limits.
        """
        import cv2

        h, w = image.shape[:2]
        max_dim = max(h, w)

        if max_dim <= self._max_size:
            return image

        scale = self._max_size / max_dim
        new_w = int(w * scale)
        new_h = int(h * scale)

        return cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_AREA)

    def extract(self, image: np.ndarray) -> OCRResult:
        """Run OCR on a BGR image.

        Images exceeding max_size are downscaled to improve speed while
        maintaining sufficient resolution for screen text recognition.

        Args:
            image: Raw BGR image as a numpy array (height, width, 3).

        Returns:
            OCRResult with extracted text, confidence, and timing.
        """
        self._ensure_initialized()

        image = self._resize_if_needed(image)

        start = time.perf_counter()

        raw_results = self._ocr.readtext(image)

        elapsed_ms = (time.perf_counter() - start) * 1000.0

        raw_lines: list[tuple[str, float]] = []
        for _bbox, text, confidence in raw_results:
            if confidence > 0.0:
                raw_lines.append((text, confidence))

        text_parts = [line for line, _ in raw_lines if line.strip()]
        combined_text = " ".join(text_parts)

        if raw_lines:
            avg_confidence = sum(conf for _, conf in raw_lines) / len(raw_lines)
        else:
            avg_confidence = 0.0

        logger.debug(
            "OCR completed in %.1fms | confidence=%.2f | text_len=%d",
            elapsed_ms,
            avg_confidence,
            len(combined_text),
        )

        return OCRResult(
            text=combined_text,
            confidence=avg_confidence,
            elapsed_ms=elapsed_ms,
            raw_lines=raw_lines,
        )
