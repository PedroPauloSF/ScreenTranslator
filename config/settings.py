"""
Application settings management.

Single source of truth for all user-configurable parameters.
Settings are persisted as JSON in the application directory.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

from utils.paths import app_root

SETTINGS_FILENAME: str = "settings.json"


@dataclass
class Region:
    """Represents a rectangular screen region to monitor."""

    left: int = 0
    top: int = 0
    width: int = 400
    height: int = 300

    @property
    def is_valid(self) -> bool:
        """Check if the region has valid dimensions."""
        return self.width > 0 and self.height > 0

    def to_tuple(self) -> tuple[int, int, int, int]:
        """Return region as (left, top, width, height) for MSS."""
        return (self.left, self.top, self.width, self.height)


@dataclass
class OverlaySettings:
    """Visual settings for the translation overlay window."""

    opacity: float = 0.85
    font_family: str = "Segoe UI"
    font_size: int = 14
    margin_horizontal: int = 12
    margin_vertical: int = 8
    line_spacing: float = 1.4
    text_color: str = "#000000"
    background_color: str = "#FFFFFF"


@dataclass
class CaptureSettings:
    """Settings controlling the screen capture behaviour."""

    interval_ms: int = 500
    ssim_threshold: float = 0.95
    perceptual_hash_threshold: int = 5


@dataclass
class OCRSettings:
    """Settings for the OCR engine."""

    language: str = "en"
    confidence_threshold: float = 0.5
    upscale_factor: float = 2.0
    upscale_min_width: int = 200
    upscale_min_height: int = 100


@dataclass
class TranslationSettings:
    """Settings for the translation subsystem."""

    similarity_threshold: float = 95.0
    target_language: str = "pt"


@dataclass
class AppSettings:
    """Root settings container.

    All application configuration flows through this single dataclass.
    """

    region: Region = field(default_factory=Region)
    overlay: OverlaySettings = field(default_factory=OverlaySettings)
    capture: CaptureSettings = field(default_factory=CaptureSettings)
    ocr: OCRSettings = field(default_factory=OCRSettings)
    translation: TranslationSettings = field(default_factory=TranslationSettings)
    active_plugin: str = "generic"

    def to_dict(self) -> dict:
        """Serialize all settings to a flat dictionary for JSON storage."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> AppSettings:
        """Reconstruct settings from a dictionary, filling defaults for missing keys."""
        region_data = data.get("region", {})
        overlay_data = data.get("overlay", {})
        capture_data = data.get("capture", {})
        ocr_data = data.get("ocr", {})
        translation_data = data.get("translation", {})

        return cls(
            region=Region(**region_data) if region_data else Region(),
            overlay=OverlaySettings(**overlay_data) if overlay_data else OverlaySettings(),
            capture=CaptureSettings(**capture_data) if capture_data else CaptureSettings(),
            ocr=OCRSettings(**ocr_data) if ocr_data else OCRSettings(),
            translation=TranslationSettings(**translation_data) if translation_data else TranslationSettings(),
            active_plugin=data.get("active_plugin", "generic"),
        )


def _settings_path() -> Path:
    """Return the absolute path to the settings JSON file."""
    return app_root() / SETTINGS_FILENAME


def get_settings() -> AppSettings:
    """Load settings from disk.

    Returns:
        AppSettings with stored values, or defaults if the file does not exist
        or is corrupted.
    """
    path = _settings_path()
    if not path.exists():
        return AppSettings()

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return AppSettings()

    return AppSettings.from_dict(data)


def save_settings(settings: AppSettings) -> None:
    """Persist settings to disk as JSON.

    Args:
        settings: The AppSettings instance to save.
    """
    path = _settings_path()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings.to_dict(), f, indent=2, ensure_ascii=False)
