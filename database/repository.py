"""
Database repository layer.

Provides CRUD operations for captures, OCR results, translations,
and highlights. All database access for study mode goes through here.
The continuous mode never imports this module.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from database.connection import get_connection
from database.models import CaptureRecord, OCRRecord, TranslationRecord, HighlightRecord
from utils.logger import get_logger

logger = get_logger(__name__)


class CaptureRepository:
    """CRUD operations for capture records."""

    def insert(
        self,
        image_path: str,
        source_lang: str = "en",
        target_lang: str = "pt",
        region: tuple[int, int, int, int] | None = None,
    ) -> int:
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO captures (image_path, source_lang, target_lang,
               region_left, region_top, region_width, region_height)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                image_path,
                source_lang,
                target_lang,
                region[0] if region else None,
                region[1] if region else None,
                region[2] if region else None,
                region[3] if region else None,
            ),
        )
        conn.commit()
        return cursor.lastrowid

    def get_by_id(self, capture_id: int) -> CaptureRecord | None:
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM captures WHERE id = ?", (capture_id,)
        ).fetchone()
        if row is None:
            return None
        return CaptureRecord(**dict(row))

    def get_all(self, archived: bool | None = False, limit: int = 100) -> list[CaptureRecord]:
        conn = get_connection()
        if archived is None:
            rows = conn.execute(
                "SELECT * FROM captures ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM captures WHERE archived = ? ORDER BY created_at DESC LIMIT ?",
                (int(archived), limit),
            ).fetchall()
        return [CaptureRecord(**dict(row)) for row in rows]

    def archive(self, capture_id: int) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE captures SET archived = 1 WHERE id = ?", (capture_id,)
        )
        conn.commit()

    def unarchive(self, capture_id: int) -> None:
        conn = get_connection()
        conn.execute(
            "UPDATE captures SET archived = 0 WHERE id = ?", (capture_id,)
        )
        conn.commit()

    def delete(self, capture_id: int) -> None:
        conn = get_connection()
        conn.execute("DELETE FROM captures WHERE id = ?", (capture_id,))
        conn.commit()


class OCRRepository:
    """CRUD operations for OCR result records."""

    def insert(
        self,
        capture_id: int,
        raw_text: str,
        confidence: float = 0.0,
        language: str = "",
    ) -> int:
        """Insert an OCR result and return its ID."""
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO ocr_results (capture_id, raw_text, confidence, language) "
            "VALUES (?, ?, ?, ?)",
            (capture_id, raw_text, confidence, language),
        )
        conn.commit()
        return cursor.lastrowid

    def get_by_capture(self, capture_id: int) -> OCRRecord | None:
        """Get the OCR result for a specific capture."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM ocr_results WHERE capture_id = ? ORDER BY id DESC LIMIT 1",
            (capture_id,),
        ).fetchone()
        if row is None:
            return None
        return OCRRecord(**dict(row))


class TranslationRepository:
    """CRUD operations for translation records."""

    def insert(
        self,
        capture_id: int,
        translated_text: str,
        engine: str = "",
    ) -> int:
        """Insert a translation result and return its ID."""
        conn = get_connection()
        cursor = conn.execute(
            "INSERT INTO translations (capture_id, translated_text, engine) "
            "VALUES (?, ?, ?)",
            (capture_id, translated_text, engine),
        )
        conn.commit()
        return cursor.lastrowid

    def get_by_capture(self, capture_id: int) -> TranslationRecord | None:
        """Get the latest translation for a specific capture."""
        conn = get_connection()
        row = conn.execute(
            "SELECT * FROM translations WHERE capture_id = ? ORDER BY id DESC LIMIT 1",
            (capture_id,),
        ).fetchone()
        if row is None:
            return None
        return TranslationRecord(**dict(row))

    def get_all(self, limit: int = 100) -> list[TranslationRecord]:
        """Retrieve all translations ordered by creation time descending."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM translations ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [TranslationRecord(**dict(row)) for row in rows]


class HighlightRepository:
    """CRUD operations for text highlight records."""

    def insert(
        self,
        translation_id: int,
        start_offset: int,
        end_offset: int,
        color: str = "#FFFF00",
    ) -> int:
        """Insert a highlight and return its ID."""
        conn = get_connection()
        cursor = conn.execute(
            """INSERT INTO highlights (translation_id, start_offset, end_offset, color)
               VALUES (?, ?, ?, ?)""",
            (translation_id, start_offset, end_offset, color),
        )
        conn.commit()
        return cursor.lastrowid

    def get_by_translation(self, translation_id: int) -> list[HighlightRecord]:
        """Retrieve all highlights for a translation, ordered by offset."""
        conn = get_connection()
        rows = conn.execute(
            "SELECT * FROM highlights WHERE translation_id = ? ORDER BY start_offset",
            (translation_id,),
        ).fetchall()
        return [HighlightRecord(**dict(row)) for row in rows]

    def delete(self, highlight_id: int) -> None:
        """Remove a highlight by ID."""
        conn = get_connection()
        conn.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
        conn.commit()

    def delete_in_range(
        self,
        translation_id: int,
        sel_start: int,
        sel_end: int,
    ) -> None:
        """Remove all highlights that overlap with a selection range.

        A highlight overlaps if its range intersects [sel_start, sel_end].
        """
        conn = get_connection()
        conn.execute(
            """DELETE FROM highlights
               WHERE translation_id = ?
                 AND start_offset < ? AND end_offset > ?""",
            (translation_id, sel_end, sel_start),
        )
        conn.commit()
