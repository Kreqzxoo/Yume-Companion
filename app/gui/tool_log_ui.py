"""Tools page card: the tool-call log (what the AI ran, approved or declined)."""
from __future__ import annotations

import logging
import os

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("ToolLogUI")

BTN = ("QPushButton { background: rgba(255,255,255,0.05); color:#E0D6EA; border:1px solid rgba(255,143,199,0.3); "
       "border-radius:8px; padding:4px 14px; } QPushButton:hover { background: rgba(255,143,199,0.18); }")


def build_tool_log_card(ui, create_glass_card, font_input):
    tr = ui.translations.get
    card, l = create_glass_card(tr("toollog_title", "Tool log"))
    intro = QtWidgets.QLabel(tr(
        "toollog_intro",
        "Shows what the AI executed through tools, whether you approved it and what came out. "
        "Secrets are masked, long texts are shortened. The file is logs/tool_log.jsonl."))
    intro.setWordWrap(True)
    intro.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(intro)

    ui.checkBox_tool_log_enabled = QtWidgets.QCheckBox(tr("toollog_enable", "Keep a tool log"))
    ui.checkBox_tool_log_enabled.setFont(font_input)
    ui.checkBox_tool_log_enabled.setChecked(True)
    l.addWidget(ui.checkBox_tool_log_enabled)

    table = QtWidgets.QTableWidget(0, 4)
    table.setHorizontalHeaderLabels([tr("toollog_col_time", "Time"), tr("toollog_col_tool", "Tool"),
                                     tr("toollog_col_status", "Status"), tr("toollog_col_details", "Details")])
    table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
    table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
    table.verticalHeader().setVisible(False)
    table.setShowGrid(False)
    table.setMinimumHeight(260)
    hh = table.horizontalHeader()
    hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
    hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.Stretch)
    table.setStyleSheet(
        "QTableWidget { background: rgba(0,0,0,0.22); border: 1px solid rgba(255,143,199,0.18); border-radius: 10px; color: #E8DDF0; }"
        "QHeaderView::section { background: rgba(255,143,199,0.10); color: #FFC2E2; border: none; padding: 6px 8px; font-weight: 600; }"
        "QTableWidget::item { padding: 5px 8px; border-bottom: 1px solid rgba(255,255,255,0.05); }"
        "QTableWidget::item:selected { background: rgba(255,143,199,0.2); color: white; }")
    l.addWidget(table)
    ui.tool_log_table = table

    row = QtWidgets.QHBoxLayout()
    ui.pushButton_tool_log_refresh = QtWidgets.QPushButton(tr("toollog_refresh", "Refresh"))
    ui.pushButton_tool_log_clear = QtWidgets.QPushButton(tr("toollog_clear", "Clear log"))
    ui.pushButton_tool_log_open = QtWidgets.QPushButton(tr("toollog_open", "Open folder"))
    for b in (ui.pushButton_tool_log_refresh, ui.pushButton_tool_log_clear, ui.pushButton_tool_log_open):
        b.setFixedHeight(36)
        b.setStyleSheet(BTN)
        row.addWidget(b)
    row.addStretch()
    l.addLayout(row)
    ui.tool_log_controller = ToolLogController(ui)
    return card


class ToolLogController(QtCore.QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.tr = ui.translations.get
        self.signals = None
        ui.pushButton_tool_log_refresh.clicked.connect(self.refresh)
        ui.pushButton_tool_log_clear.clicked.connect(self.clear)
        ui.pushButton_tool_log_open.clicked.connect(self.open_folder)
        ui.checkBox_tool_log_enabled.toggled.connect(self._on_enabled)
        self._timer = QtCore.QTimer(self)
        self._timer.setInterval(4000)
        self._timer.timeout.connect(self._auto_refresh)
        self._timer.start()
        QtCore.QTimer.singleShot(800, self.refresh)

    def attach(self, signals):
        self.signals = signals
        try:
            value = signals.configuration_settings.get_main_setting("tool_log_enabled")
            self.ui.checkBox_tool_log_enabled.blockSignals(True)
            self.ui.checkBox_tool_log_enabled.setChecked(True if value is None else bool(value))
            self.ui.checkBox_tool_log_enabled.blockSignals(False)
        except Exception:
            pass

    def _on_enabled(self, value):
        if self.signals is not None:
            self.signals.configuration_settings.update_main_setting("tool_log_enabled", bool(value))

    def _auto_refresh(self):
        if self.ui.tool_log_table.isVisible():
            self.refresh()

    def refresh(self):
        from app.utils import tool_log
        entries = tool_log.read(120)
        table = self.ui.tool_log_table
        table.setRowCount(len(entries))
        status_text = {
            ("declined", False): (self.tr("toollog_declined", "declined"), "#FFB4A8"),
            ("approved", True): (self.tr("toollog_approved_ok", "approved · ok"), "#9BE7B5"),
            ("approved", False): (self.tr("toollog_approved_fail", "approved · failed"), "#F6C177"),
            ("not_needed", True): (self.tr("toollog_ok", "ok"), "#9BE7B5"),
            ("not_needed", False): (self.tr("toollog_failed", "failed"), "#F6C177"),
        }
        for r, e in enumerate(entries):
            text, color = status_text.get((e.get("approval"), bool(e.get("success"))), ("?", "#B9A9C9"))
            detail = (e.get("args") or "")
            cells = [e.get("t", "").replace("T", " ")[5:], e.get("tool", ""), text, detail]
            for c, value in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(value)
                if c == 2:
                    item.setForeground(QtGui.QBrush(QtGui.QColor(color)))
                item.setToolTip(f"{e.get('tool')}({e.get('args')})\n→ {e.get('result')}\n{e.get('sec')} s")
                table.setItem(r, c, item)

    def clear(self):
        from app.utils import tool_log
        answer = QtWidgets.QMessageBox.question(
            self.ui.options_page, self.tr("toollog_title", "Tool log"),
            self.tr("toollog_clear_confirm", "Delete the whole tool log?"),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No)
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            tool_log.clear()
            self.refresh()

    def open_folder(self):
        from app.utils import tool_log
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(tool_log.LOG_FILE.parent)))
