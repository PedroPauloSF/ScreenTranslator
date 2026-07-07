"""
Text comparison utilities.

Uses RapidFuzz for fast, tolerance-aware string comparison.
Determines whether OCR output has changed enough to warrant re-translation.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class TextComparator:
    """Compares OCR text outputs to decide if translation is needed.

    Attributes:
        similarity_threshold: Minimum partial ratio (0-100) to consider texts identical.
    """

    similarity_threshold: float = 95.0
    _last_text: str = field(default="", init=False, repr=False)

    def text_has_changed(self, new_text: str) -> bool:
        """Check whether new_text is meaningfully different from the last known text.

        Args:
            new_text: The freshly extracted OCR text.

        Returns:
            True if the text has changed enough to require translation.
        """
        if not new_text.strip():
            return False

        if not self._last_text.strip():
            self._last_text = new_text
            return True

        similarity = text_similarity(self._last_text, new_text)
        if similarity >= self.similarity_threshold:
            return False

        self._last_text = new_text
        return True

    def reset(self) -> None:
        """Clear the stored last text, forcing the next comparison to trigger."""
        self._last_text = ""


def text_similarity(text_a: str, text_b: str) -> float:
    """Compute similarity between two text strings using RapidFuzz partial ratio.

    The partial ratio finds the best alignment of the shorter string
    within the longer string, making it tolerant to added/removed content.

    Args:
        text_a: First text string.
        text_b: Second text string.

    Returns:
        Similarity score from 0.0 (completely different) to 100.0 (identical).
    """
    from rapidfuzz import fuzz

    if not text_a and not text_b:
        return 100.0
    if not text_a or not text_b:
        return 0.0

    return float(fuzz.partial_ratio(text_a, text_b))
