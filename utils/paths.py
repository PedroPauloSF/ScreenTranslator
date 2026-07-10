"""
Application path resolver.

Provides a single function that returns the correct application root
directory both during development and when running as a PyInstaller bundle.
"""

from __future__ import annotations

import sys
from pathlib import Path


def app_root() -> Path:
    """Return the application root directory.

    During development: the project root (parent of this file's package).
    As a PyInstaller bundle: the directory containing the executable.

    Returns:
        Absolute path to the application root.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def app_data_dir(name: str = "") -> Path:
    """Return a data subdirectory, creating it if it doesn't exist.

    Args:
        name: Subdirectory name (e.g. 'captures', 'logs').

    Returns:
        Absolute path to the data directory.
    """
    root = app_root()
    if name:
        root = root / name
    root.mkdir(parents=True, exist_ok=True)
    return root
