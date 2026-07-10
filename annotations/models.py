"""
Annotations domain models.

Pure data objects for the highlight/annotation system.
"""

from __future__ import annotations

from dataclasses import dataclass

AVAILABLE_COLORS = [
    ("#FFFF00", "Amarelo"),
    ("#FF9999", "Vermelho"),
    ("#99FF99", "Verde"),
    ("#99CCFF", "Azul"),
    ("#FFCC99", "Laranja"),
    ("#CC99FF", "Roxo"),
    ("#FF99CC", "Rosa"),
    ("#99FFFF", "Ciano"),
]


@dataclass
class Highlight:
    """Represents a user-created text highlight in memory.

    The offsets are character positions within the translated text.
    """

    id: int = 0
    translation_id: int = 0
    start_offset: int = 0
    end_offset: int = 0
    color: str = "#FFFF00"
