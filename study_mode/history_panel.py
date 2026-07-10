"""
History panel widget.

Displays a sidebar list of past captures with two tabs:
active history and archived items.  Includes buttons to archive
and delete selected entries.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QPushButton,
    QTabWidget,
)

from database.models import CaptureRecord, TranslationRecord
from utils.logger import get_logger

logger = get_logger(__name__)

_VISIBLE_COLUMNS = ("id", "image_path", "source_lang", "target_lang", "created_at",
                    "region_left", "region_top", "region_width", "region_height", "archived")


def _make_record(row) -> CaptureRecord:
    data = {k: row[k] for k in _VISIBLE_COLUMNS if k in row.keys()}
    data["archived"] = bool(data.get("archived", False))
    return CaptureRecord(**data)


def _format_timestamp(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        from datetime import datetime
        dt = datetime.strptime(iso_str, "%Y-%m-%d %H:%M:%S")
        return dt.strftime("%d/%m/%Y %H:%M")
    except (ValueError, AttributeError):
        return iso_str[:16] if len(iso_str) >= 16 else iso_str


def _format_snippet(text: str, max_len: int = 80) -> str:
    if not text:
        return "(vazio)"
    clean = text.replace("\n", " ").strip()
    if len(clean) > max_len:
        return clean[:max_len] + "..."
    return clean


class _CaptureListWidget(QListWidget):
    """QListWidget with a helper to get the selected capture ID."""

    def selected_capture_id(self) -> int | None:
        item = self.currentItem()
        if item is None:
            return None
        return item.data(Qt.ItemDataRole.UserRole)


class HistoryPanel(QWidget):
    """Sidebar with active/archived tabs and archive/delete controls.

    Signals:
        item_selected: Emitted with the capture ID when a history item is clicked.
        archive_requested: Emitted with the capture ID to archive.
        delete_requested: Emitted with the capture ID to delete.
    """

    item_selected = Signal(int)
    archive_requested = Signal(int)
    unarchive_requested = Signal(int)
    delete_requested = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._tabs: QTabWidget | None = None
        self._active_list: _CaptureListWidget | None = None
        self._archived_list: _CaptureListWidget | None = None
        self._archive_btn: QPushButton | None = None
        self._unarchive_btn: QPushButton | None = None
        self._delete_btn: QPushButton | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        header = QLabel("Historico")
        header.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(header)

        self._tabs = QTabWidget()
        self._tabs.currentChanged.connect(self._on_tab_changed)

        self._active_list = _CaptureListWidget()
        self._active_list.setAlternatingRowColors(True)
        self._active_list.itemClicked.connect(self._on_item_clicked)
        self._tabs.addTab(self._active_list, "Ativo")

        self._archived_list = _CaptureListWidget()
        self._archived_list.setAlternatingRowColors(True)
        self._archived_list.itemClicked.connect(self._on_item_clicked)
        self._tabs.addTab(self._archived_list, "Arquivado")

        layout.addWidget(self._tabs)

        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(4)

        self._archive_btn = QPushButton("Arquivar")
        self._archive_btn.setToolTip("Mover para aba Arquivado")
        self._archive_btn.clicked.connect(self._on_archive)
        btn_layout.addWidget(self._archive_btn)

        self._unarchive_btn = QPushButton("Desarquivar")
        self._unarchive_btn.setToolTip("Mover para aba Ativo")
        self._unarchive_btn.clicked.connect(self._on_unarchive)
        btn_layout.addWidget(self._unarchive_btn)

        self._delete_btn = QPushButton("Excluir")
        self._delete_btn.setStyleSheet("QPushButton { color: #cc0000; }")
        self._delete_btn.setToolTip("Remover permanentemente")
        self._delete_btn.clicked.connect(self._on_delete)
        btn_layout.addWidget(self._delete_btn)

        layout.addLayout(btn_layout)
        self._on_tab_changed(0)

    def _current_list(self) -> _CaptureListWidget | None:
        if self._tabs is None:
            return None
        return self._active_list if self._tabs.currentIndex() == 0 else self._archived_list

    def _on_tab_changed(self, index: int) -> None:
        is_active = index == 0
        if self._archive_btn:
            self._archive_btn.setVisible(is_active)
        if self._unarchive_btn:
            self._unarchive_btn.setVisible(not is_active)

    def load(
        self,
        captures: list[CaptureRecord],
        translations: dict[int, TranslationRecord],
    ) -> None:
        tab_idx = self._tabs.currentIndex() if self._tabs else 0

        if self._active_list:
            self._active_list.clear()
        if self._archived_list:
            self._archived_list.clear()

        for capture in captures:
            tl = translations.get(capture.id)
            snippet = _format_snippet(tl.translated_text) if tl else ""
            ts = _format_timestamp(capture.created_at)
            label = f"{ts}\n{snippet}" if snippet else ts

            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, capture.id)

            target = self._archived_list if capture.archived else self._active_list
            if target:
                target.addItem(item)

        if self._tabs:
            self._tabs.setCurrentIndex(tab_idx)

    def set_current(self, capture_id: int, switch_tab: bool = True) -> None:
        for lst in (self._active_list, self._archived_list):
            if lst is None:
                continue
            for i in range(lst.count()):
                item = lst.item(i)
                if item.data(Qt.ItemDataRole.UserRole) == capture_id:
                    lst.setCurrentItem(item)
                    if switch_tab and self._tabs:
                        self._tabs.setCurrentIndex(0 if lst is self._active_list else 1)
                    return

    @Slot(QListWidgetItem)
    def _on_item_clicked(self, item: QListWidgetItem) -> None:
        capture_id = item.data(Qt.ItemDataRole.UserRole)
        if capture_id is not None:
            self.item_selected.emit(capture_id)

    def _on_archive(self) -> None:
        lst = self._current_list()
        if lst is None:
            return
        capture_id = lst.selected_capture_id()
        if capture_id is not None:
            self.archive_requested.emit(capture_id)

    def _on_unarchive(self) -> None:
        lst = self._current_list()
        if lst is None:
            return
        capture_id = lst.selected_capture_id()
        if capture_id is not None:
            self.unarchive_requested.emit(capture_id)

    def _on_delete(self) -> None:
        lst = self._current_list()
        if lst is None:
            return
        capture_id = lst.selected_capture_id()
        if capture_id is not None:
            self.delete_requested.emit(capture_id)
