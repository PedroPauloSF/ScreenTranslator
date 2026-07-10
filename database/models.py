"""
Database entity models.

Dataclasses representing rows in the study-mode database tables.
These are pure data objects with no business logic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CaptureRecord:
    """Represents a single capture event in the study history."""

    id: int = 0
    image_path: str = ""
    source_lang: str = "en"
    target_lang: str = "pt"
    created_at: str = ""
    region_left: int | None = None
    region_top: int | None = None
    region_width: int | None = None
    region_height: int | None = None
    archived: bool = False


@dataclass
class OCRRecord:
    """Represents the OCR result for a capture."""

    id: int = 0
    capture_id: int = 0
    raw_text: str = ""
    confidence: float = 0.0
    language: str = ""
    created_at: str = ""


@dataclass
class TranslationRecord:
    """Represents a translation result for a capture."""

    id: int = 0
    capture_id: int = 0
    translated_text: str = ""
    engine: str = ""
    created_at: str = ""


@dataclass
class HighlightRecord:
    """Represents a user-created text highlight."""

    id: int = 0
    translation_id: int = 0
    start_offset: int = 0
    end_offset: int = 0
    color: str = "#FFFF00"
    created_at: str = ""
