"""
Mode selector dialog.

Displays a small launcher window on startup, allowing the user
to choose between Continuous Mode and Study Mode.

Usage:
    selector = ModeSelector()
    if selector.exec() == QDialog.DialogCode.Accepted:
        mode = selector.selected_mode  # "continuous" or "study"
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
)


class ModeSelector(QDialog):
    """Launcher dialog with two mode buttons."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._selected_mode: str = ""
        self.setWindowTitle("Tradutor de Telas")
        self.setFixedSize(420, 240)
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowCloseButtonHint
            | Qt.WindowType.MSWindowsFixedSizeDialogHint
        )
        self._setup_ui()

    @property
    def selected_mode(self) -> str:
        """Return the mode the user selected ("continuous" or "study")."""
        return self._selected_mode

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(16)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("Tradutor de Telas")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        layout.addWidget(title)

        subtitle = QLabel("Escolha um modo para iniciar:")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(subtitle)

        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        continuous_btn = QPushButton("Continuo")
        continuous_btn.setToolTip(
            "Monitoramento em tempo real:\n"
            "captura, OCR, traducao e overlay.\n"
            "Sem historico - tudo e temporario."
        )
        continuous_btn.setMinimumHeight(60)
        continuous_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        continuous_btn.clicked.connect(self._on_continuous)
        btn_layout.addWidget(continuous_btn)

        study_btn = QPushButton("Estudo")
        study_btn.setToolTip(
            "Captura manual: selecione uma regiao,\n"
            "capture uma vez, traduza e salve\n"
            "no historico com anotacoes."
        )
        study_btn.setMinimumHeight(60)
        study_btn.setStyleSheet("font-size: 14px; font-weight: bold;")
        study_btn.clicked.connect(self._on_study)
        btn_layout.addWidget(study_btn)

        layout.addLayout(btn_layout)

    def _on_continuous(self) -> None:
        self._selected_mode = "continuous"
        self.accept()

    def _on_study(self) -> None:
        self._selected_mode = "study"
        self.accept()
