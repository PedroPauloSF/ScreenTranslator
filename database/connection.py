"""
Database connection manager.

Manages a single SQLite connection used exclusively by study mode.
The continuous mode never imports or accesses this module.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from threading import Lock

from utils.logger import get_logger
from utils.paths import app_root

logger = get_logger(__name__)

_connection: sqlite3.Connection | None = None
_db_path: Path | None = None
_lock = Lock()

_DEFAULT_DB_NAME = "study_history.db"

_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS captures (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    image_path      TEXT    NOT NULL,
    source_lang     TEXT    NOT NULL DEFAULT 'en',
    target_lang     TEXT    NOT NULL DEFAULT 'pt',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime')),
    region_left     INTEGER,
    region_top      INTEGER,
    region_width    INTEGER,
    region_height   INTEGER,
    archived        INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS ocr_results (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id      INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    raw_text        TEXT    NOT NULL,
    confidence      REAL,
    language        TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS translations (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    capture_id      INTEGER NOT NULL REFERENCES captures(id) ON DELETE CASCADE,
    translated_text TEXT    NOT NULL,
    engine          TEXT,
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

CREATE TABLE IF NOT EXISTS highlights (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    translation_id  INTEGER NOT NULL REFERENCES translations(id) ON DELETE CASCADE,
    start_offset    INTEGER NOT NULL,
    end_offset      INTEGER NOT NULL,
    color           TEXT    NOT NULL DEFAULT '#FFFF00',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now','localtime'))
);

PRAGMA foreign_keys = ON;
"""


def _migrate(conn: sqlite3.Connection) -> None:
    """Apply schema migrations for existing databases."""
    try:
        conn.execute(
            "ALTER TABLE captures ADD COLUMN archived INTEGER NOT NULL DEFAULT 0"
        )
    except sqlite3.OperationalError:
        pass


def set_db_path(path: str | Path) -> None:
    """Set the path for the SQLite database file.

    Args:
        path: Absolute or relative path to the .db file.
    """
    global _db_path
    _db_path = Path(path)


def get_connection() -> sqlite3.Connection:
    """Return the singleton SQLite connection, creating it if needed.

    The database file is created at the path set via set_db_path(),
    defaulting to ``study_history.db`` alongside settings.json.

    Returns:
        An sqlite3.Connection with foreign keys enabled and WAL mode.
    """
    global _connection

    with _lock:
        if _connection is not None:
            return _connection

        path = _db_path or (app_root() / _DEFAULT_DB_NAME)
        path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Opening database at: %s", path)
        _connection = sqlite3.connect(str(path), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL;")
        _connection.execute("PRAGMA foreign_keys=ON;")
        _connection.executescript(_SCHEMA_SQL)
        _migrate(_connection)
        _connection.commit()

    return _connection


def close_connection() -> None:
    """Close the database connection if open."""
    global _connection
    with _lock:
        if _connection is not None:
            _connection.close()
            _connection = None
            logger.info("Database connection closed.")
