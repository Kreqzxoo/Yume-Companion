"""Selectable list of installed programs for the 'start programs' tool (replaces typing paths by hand)."""
from __future__ import annotations

import logging
import os

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("AppPicker")

BTN = ("QPushButton { background: rgba(255,255,255,0.05); color:#E0D6EA; border:1px solid rgba(255,143,199,0.3); "
       "border-radius:8px; padding:4px 14px; } QPushButton:hover { background: rgba(255,143,199,0.18); }"
       "QPushButton:disabled { color: rgba(224,214,234,0.35); }")


class _ScanThread(QtCore.QThread):
    done = QtCore.pyqtSignal(list)

    def run(self):
        try:
            from app.utils.app_scanner import scan
            self.done.emit(scan())
        except Exception:
            logger.exception("App scan failed")
            self.done.emit([])


class AppPicker(QtWidgets.QWidget):
    """Keeps the same 'Name | path' text format the launcher tool reads; the hidden text edit stays the data store."""

    def __init__(self, store: QtWidgets.QTextEdit, translations, launch_checkbox=None, parent=None):
        super().__init__(parent)
        self.store = store
        self.launch_checkbox = launch_checkbox
        self.tr = translations.get
        self._syncing = False
        self._catalog: dict[str, dict] = {}   # casefold(name) -> entry
        self._thread = None

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(8)
        top = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(self.tr("apps_search", "Search programs ..."))
        self.search.setClearButtonEnabled(True)
        self.search.setFixedHeight(34)
        self.search.setStyleSheet("QLineEdit { background: rgba(255,255,255,0.05); border: 1px solid rgba(255,143,199,0.25); "
                                  "border-radius: 10px; padding: 4px 12px; color: #F1E8F6; } "
                                  "QLineEdit:focus { border-color: rgba(255,143,199,0.7); }")
        self.rescan = QtWidgets.QPushButton(self.tr("apps_rescan", "Scan again"))
        self.add = QtWidgets.QPushButton(self.tr("apps_add", "Add program ..."))
        for b in (self.rescan, self.add):
            b.setFixedHeight(34)
            b.setStyleSheet(BTN)
        top.addWidget(self.search, 1)
        top.addWidget(self.rescan)
        top.addWidget(self.add)
        lay.addLayout(top)

        self.list = QtWidgets.QListWidget()
        self.list.setMinimumHeight(260)
        self.list.setMaximumHeight(380)
        self.list.setUniformItemSizes(True)
        self.list.setStyleSheet(
            "QListWidget { background: rgba(14,9,22,0.5); border: 1px solid rgba(255,143,199,0.2); border-radius: 10px; color: #F1E8F6; outline: none; }"
            "QListWidget::item { padding: 7px 10px; border-bottom: 1px solid rgba(255,255,255,0.05); }"
            "QListWidget::item:hover { background: rgba(255,143,199,0.10); }"
            "QListWidget::indicator { width: 17px; height: 17px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.3); background: rgba(0,0,0,0.3); }"
            "QListWidget::indicator:checked { background: #FF8FC7; border-color: #FF8FC7; }")
        lay.addWidget(self.list)
        self.status = QtWidgets.QLabel("")
        self.status.setStyleSheet("color: #B9A9C9; font-size: 11px; background: transparent; border: none;")
        lay.addWidget(self.status)

        self.search.textChanged.connect(self._filter)
        self.rescan.clicked.connect(self.start_scan)
        self.add.clicked.connect(self._add_manual)
        self.list.itemChanged.connect(self._item_changed)
        store.textChanged.connect(self._store_changed)
        QtCore.QTimer.singleShot(600, self.start_scan)

    # ------------------------------------------------------------------ data
    def _selection_from_store(self) -> dict[str, tuple[str, str]]:
        """casefold(name) -> (name, path) for every valid line of the stored text."""
        out = {}
        for line in self.store.toPlainText().splitlines():
            if "|" not in line:
                continue
            name, path = (x.strip() for x in line.split("|", 1))
            if name and path:
                out[name.casefold()] = (name, path)
        return out

    def _write_store(self):
        lines = []
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.checkState() == QtCore.Qt.CheckState.Checked:
                entry = item.data(QtCore.Qt.ItemDataRole.UserRole)
                lines.append(f"{entry['name']} | {entry['path']}")
        self._syncing = True
        try:
            self.store.setPlainText("\n".join(lines))   # triggers the normal save handler
        finally:
            self._syncing = False
        if lines and self.launch_checkbox is not None and not self.launch_checkbox.isChecked():
            self.launch_checkbox.setChecked(True)       # picking a program implies "allow starting programs"
        self._update_status()

    def _store_changed(self):
        if not self._syncing:
            self._rebuild()

    def _item_changed(self, _item):
        if not self._syncing_list:
            self._write_store()

    _syncing_list = False

    def start_scan(self):
        if self._thread is not None and self._thread.isRunning():
            return
        self.rescan.setEnabled(False)
        self.status.setText(self.tr("apps_scanning", "Scanning installed programs ..."))
        self._thread = _ScanThread(self)
        self._thread.done.connect(self._scan_done)
        self._thread.start()

    def _scan_done(self, entries):
        self._catalog = {e["name"].casefold(): e for e in entries}
        self.rescan.setEnabled(True)
        self._rebuild()

    def _rebuild(self):
        selected = self._selection_from_store()
        catalog = dict(self._catalog)
        for key, (name, path) in selected.items():       # keep manually added / not scanned entries visible
            if key not in catalog:
                catalog[key] = {"name": name, "path": path, "source": "manual"}
            elif catalog[key]["path"] != path:
                catalog[key] = {"name": name, "path": path, "source": catalog[key]["source"]}
        self._syncing_list = True
        try:
            self.list.clear()
            ordered = sorted(catalog.values(), key=lambda e: (e["name"].casefold() not in selected, e["name"].casefold()))
            for e in ordered:
                item = QtWidgets.QListWidgetItem(e["name"] + ("   " + self.tr("apps_manual", "(manual)") if e["source"] == "manual" else ""))
                item.setData(QtCore.Qt.ItemDataRole.UserRole, e)
                item.setToolTip(e["path"])
                item.setFlags(item.flags() | QtCore.Qt.ItemFlag.ItemIsUserCheckable)
                item.setCheckState(QtCore.Qt.CheckState.Checked if e["name"].casefold() in selected else QtCore.Qt.CheckState.Unchecked)
                self.list.addItem(item)
        finally:
            self._syncing_list = False
        self._filter(self.search.text())
        self._update_status()

    def _filter(self, text):
        needle = (text or "").strip().casefold()
        for i in range(self.list.count()):
            item = self.list.item(i)
            e = item.data(QtCore.Qt.ItemDataRole.UserRole)
            item.setHidden(bool(needle) and needle not in e["name"].casefold())

    def _update_status(self):
        checked = sum(1 for i in range(self.list.count()) if self.list.item(i).checkState() == QtCore.Qt.CheckState.Checked)
        self.status.setText(self.tr("apps_status", "{found} programs found · {sel} allowed").format(found=len(self._catalog), sel=checked))

    def _add_manual(self):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, self.tr("apps_add_dialog", "Choose a program"), os.environ.get("ProgramFiles", "C:\\"),
            "Programs (*.exe *.lnk)")
        if not path:
            return
        name = os.path.splitext(os.path.basename(path))[0].replace("|", " ").strip()
        name = name[:1].upper() + name[1:]
        sel = self._selection_from_store()
        sel[name.casefold()] = (name, os.path.normpath(path))
        self._syncing = True
        try:
            self.store.setPlainText("\n".join(f"{n} | {p}" for n, p in sel.values()))
        finally:
            self._syncing = False
        self._rebuild()
