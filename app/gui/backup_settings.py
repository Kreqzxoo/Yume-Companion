"""Backup & Restore page: compact profile backup (choose what to include) on top of the config-only backup.

Uses app.utils.profile_backup (.yumepack packages, safety snapshot before a restore, automatic rollback).
"""
from __future__ import annotations

import datetime
import logging
import os
import sys

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("ProfileBackupUI")

PINK = "#FF8FC7"
BTN = ("QPushButton { background: rgba(255,143,199,0.14); color:#F1E8F6; border:1px solid rgba(255,143,199,0.45); "
       "border-radius:8px; padding:4px 14px; } QPushButton:hover { background: rgba(255,143,199,0.26); } "
       "QPushButton:disabled { color: rgba(241,232,246,0.35); border-color: rgba(255,143,199,0.15); }")
BTN_GHOST = ("QPushButton { background: rgba(255,255,255,0.05); color:#E0D6EA; border:1px solid rgba(255,255,255,0.13); "
             "border-radius:8px; padding:4px 12px; } QPushButton:hover { background: rgba(255,255,255,0.1); } "
             "QPushButton:disabled { color: rgba(224,214,234,0.3); }")
BTN_DANGER = ("QPushButton { background: rgba(255,120,150,0.12); color:#FFD0DC; border:1px solid rgba(255,120,150,0.4); "
              "border-radius:8px; padding:4px 14px; } QPushButton:hover { background: rgba(255,120,150,0.26); } "
              "QPushButton:disabled { color: rgba(255,208,220,0.3); border-color: rgba(255,120,150,0.15); }")
PROGRESS = ("QProgressBar { background: rgba(0,0,0,0.35); border: none; border-radius: 4px; max-height: 8px; } "
            "QProgressBar::chunk { background: qlineargradient(x1:0,y1:0,x2:1,y2:0, stop:0 #FF8FC7, stop:1 #B69CFF); border-radius: 4px; }")
CHECK = ("QCheckBox { color: #E8DDF0; spacing: 8px; background: transparent; } "
         "QCheckBox::indicator { width: 17px; height: 17px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.28); background: rgba(0,0,0,0.3); } "
         "QCheckBox::indicator:checked { background-color: rgba(255,143,199,0.8); border-color: #FF8FC7; }")


def build_profile_backup_card(ui, create_glass_card, font_input):
    tr = ui.translations.get
    from app.utils.profile_backup import BACKUP_GROUPS

    card, l = create_glass_card(tr("pbackup_title", "Profile backup"))
    intro = QtWidgets.QLabel(tr(
        "pbackup_intro",
        "Saves your whole profile as one .yumepack file: characters and chats, personas, memories, Soul Stage scenes "
        "and optionally your assets. Before a restore a safety snapshot of the current data is created automatically."))
    intro.setWordWrap(True)
    intro.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(intro)

    ui.pbackup_checks = {}
    grid = QtWidgets.QGridLayout()
    grid.setHorizontalSpacing(24)
    grid.setVerticalSpacing(6)
    for i, g in enumerate(BACKUP_GROUPS):
        text = tr(g.title_key, g.key.replace("_", " ").title())
        if g.warning == "api":
            text += "  ⚠ " + tr("pbackup_sensitive", "sensitive")
        elif g.warning == "size":
            text += "  · " + tr("pbackup_large", "large")
        cb = QtWidgets.QCheckBox(text.replace("&", "&&"))
        cb.setChecked(g.default_on)
        cb.setEnabled(not g.locked)
        cb.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        cb.setStyleSheet(CHECK)
        if g.locked:
            cb.setToolTip(tr("pbackup_locked", "Essential data - always included"))
        size = QtWidgets.QLabel("…")
        size.setStyleSheet("color: #8D7AA3; font-size: 11px; border: none; background: transparent; padding-left: 8px;")
        cell = QtWidgets.QHBoxLayout()
        cell.addWidget(cb)
        cell.addWidget(size)
        cell.addStretch()
        grid.addLayout(cell, i // 2, i % 2)
        ui.pbackup_checks[g.key] = (cb, size)
    l.addLayout(grid)

    row = QtWidgets.QHBoxLayout()
    ui.pbackup_recalc = QtWidgets.QPushButton(tr("pbackup_recalc", "Recalculate sizes"))
    ui.pbackup_recalc.setStyleSheet(BTN_GHOST)
    ui.pbackup_total = QtWidgets.QLabel("")
    ui.pbackup_total.setStyleSheet(f"color: {PINK}; font-weight: 600; border: none; background: transparent;")
    row.addWidget(ui.pbackup_recalc)
    row.addStretch()
    row.addWidget(ui.pbackup_total)
    l.addLayout(row)

    path_row = QtWidgets.QHBoxLayout()
    ui.pbackup_path = QtWidgets.QLineEdit()
    ui.pbackup_path.setFixedHeight(36)
    ui.pbackup_path.setFont(font_input)
    ui.pbackup_browse = QtWidgets.QPushButton("…")
    ui.pbackup_browse.setFixedSize(40, 36)
    ui.pbackup_browse.setStyleSheet(BTN_GHOST)
    path_row.addWidget(QtWidgets.QLabel(tr("pbackup_save_to", "Save to:")))
    path_row.addWidget(ui.pbackup_path, 1)
    path_row.addWidget(ui.pbackup_browse)
    l.addLayout(path_row)

    ui.pbackup_progress = QtWidgets.QProgressBar()
    ui.pbackup_progress.setTextVisible(False)
    ui.pbackup_progress.setFixedHeight(8)
    ui.pbackup_progress.setStyleSheet(PROGRESS)
    ui.pbackup_progress.hide()
    ui.pbackup_status = QtWidgets.QLabel("")
    ui.pbackup_status.setWordWrap(True)
    ui.pbackup_status.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    ui.pbackup_status.hide()
    l.addWidget(ui.pbackup_progress)
    l.addWidget(ui.pbackup_status)

    btns = QtWidgets.QHBoxLayout()
    ui.pbackup_create = QtWidgets.QPushButton(tr("pbackup_create", "Create backup now"))
    ui.pbackup_create.setFixedHeight(40)
    ui.pbackup_create.setStyleSheet(BTN)
    ui.pbackup_open = QtWidgets.QPushButton(tr("pbackup_open_folder", "Open backup folder"))
    ui.pbackup_open.setFixedHeight(40)
    ui.pbackup_open.setStyleSheet(BTN_GHOST)
    btns.addWidget(ui.pbackup_create, 1)
    btns.addWidget(ui.pbackup_open)
    l.addLayout(btns)

    sep0 = QtWidgets.QFrame()
    sep0.setFixedHeight(1)
    sep0.setStyleSheet("background: rgba(255,143,199,0.18); border: none;")
    l.addWidget(sep0)
    auto_title = QtWidgets.QLabel(tr("autobackup_title", "Automatic backups"))
    auto_title.setStyleSheet("color: #F1E8F6; font-weight: 600; border: none; background: transparent;")
    l.addWidget(auto_title)
    ui.pbackup_auto_enable = QtWidgets.QCheckBox(tr("autobackup_enable", "Back up automatically (characters, chats, settings, memories - without API keys)"))
    ui.pbackup_auto_enable.setStyleSheet(CHECK)
    l.addWidget(ui.pbackup_auto_enable)
    arow = QtWidgets.QHBoxLayout()
    ui.pbackup_auto_days = QtWidgets.QComboBox()
    for days, label in ((1, tr("autobackup_daily", "every day")), (3, tr("autobackup_3days", "every 3 days")), (7, tr("autobackup_weekly", "every week"))):
        ui.pbackup_auto_days.addItem(label, days)
    ui.pbackup_auto_days.setFixedHeight(34)
    ui.pbackup_auto_keep = QtWidgets.QSpinBox()
    ui.pbackup_auto_keep.setRange(2, 30)
    ui.pbackup_auto_keep.setValue(5)
    ui.pbackup_auto_keep.setFixedHeight(34)
    ui.pbackup_auto_keep.setPrefix(tr("autobackup_keep", "keep newest") + " ")
    ui.pbackup_auto_now = QtWidgets.QPushButton(tr("autobackup_now", "Back up now"))
    ui.pbackup_auto_now.setStyleSheet(BTN_GHOST)
    ui.pbackup_auto_now.setFixedHeight(34)
    ui.pbackup_auto_open = QtWidgets.QPushButton(tr("autobackup_open", "Open folder"))
    ui.pbackup_auto_open.setStyleSheet(BTN_GHOST)
    ui.pbackup_auto_open.setFixedHeight(34)
    for w in (ui.pbackup_auto_days, ui.pbackup_auto_keep, ui.pbackup_auto_now, ui.pbackup_auto_open):
        arow.addWidget(w)
    arow.addStretch()
    l.addLayout(arow)
    ui.pbackup_auto_status = QtWidgets.QLabel("")
    ui.pbackup_auto_status.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(ui.pbackup_auto_status)

    sep = QtWidgets.QFrame()
    sep.setFixedHeight(1)
    sep.setStyleSheet("background: rgba(255,143,199,0.18); border: none;")
    l.addWidget(sep)

    restore_title = QtWidgets.QLabel(tr("pbackup_restore_title", "Restore a profile backup"))
    restore_title.setStyleSheet("color: #F1E8F6; font-weight: 600; border: none; background: transparent;")
    l.addWidget(restore_title)
    rrow = QtWidgets.QHBoxLayout()
    ui.pbackup_pick = QtWidgets.QPushButton(tr("pbackup_pick", "Choose .yumepack file…"))
    ui.pbackup_pick.setFixedHeight(38)
    ui.pbackup_pick.setStyleSheet(BTN_GHOST)
    ui.pbackup_restore = QtWidgets.QPushButton(tr("pbackup_restore", "Restore"))
    ui.pbackup_restore.setFixedHeight(38)
    ui.pbackup_restore.setStyleSheet(BTN_DANGER)
    ui.pbackup_restore.setEnabled(False)
    rrow.addWidget(ui.pbackup_pick)
    rrow.addWidget(ui.pbackup_restore)
    rrow.addStretch()
    l.addLayout(rrow)
    ui.pbackup_info = QtWidgets.QLabel("")
    ui.pbackup_info.setWordWrap(True)
    ui.pbackup_info.setTextFormat(QtCore.Qt.TextFormat.RichText)
    ui.pbackup_info.setStyleSheet("background: rgba(0,0,0,0.25); border: 1px solid rgba(255,143,199,0.18); border-radius: 8px; "
                                  "padding: 10px 12px; color: #E8DDF0;")
    ui.pbackup_info.hide()
    l.addWidget(ui.pbackup_info)

    ui.profile_backup_controller = ProfileBackupController(ui)
    return card


def restart_program(root: str, target: str = None, args=None, wait_pid: int = None, extra_delay: int = 3):
    """Starts the program again ONLY AFTER this process has really ended. A new instance that starts while the old one is still shutting down
    runs into locked files / the shared web-engine profile and dies right after the start ("could not be started")."""
    import subprocess
    pid = wait_pid or os.getpid()
    if target is None:
        launcher = os.path.join(root, "Yume Companion.exe")
        if os.path.exists(launcher):
            target, args = launcher, []
        else:
            target, args = sys.executable, list(sys.argv)
    q = lambda s: "'" + str(s).replace("'", "''") + "'"
    arg_part = (" -ArgumentList " + ",".join(q(a) for a in args)) if args else ""
    script = (f"$p = Get-Process -Id {pid} -ErrorAction SilentlyContinue; if ($p) {{ [void]$p.WaitForExit(40000) }}; "
              f"Start-Sleep -Seconds {int(extra_delay)}; Start-Process -FilePath {q(target)}{arg_part} -WorkingDirectory {q(root)}")
    flags = 0x08000000 | 0x00000200      # no window, own process group (DETACHED_PROCESS would stop the helper from running)
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-WindowStyle", "Hidden", "-Command", script],
                     creationflags=flags, close_fds=True, cwd=root)


class ProfileBackupController(QtCore.QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.tr = ui.translations.get
        self.worker = None
        self.pack_path = None
        self.signals = None
        self.root = os.getcwd()
        self._set_default_path()
        ui.pbackup_recalc.clicked.connect(self.recalculate)
        ui.pbackup_browse.clicked.connect(self.browse)
        ui.pbackup_create.clicked.connect(self.start_export)
        ui.pbackup_open.clicked.connect(self.open_folder)
        ui.pbackup_pick.clicked.connect(self.pick_pack)
        ui.pbackup_restore.clicked.connect(self.start_restore)
        self.scheduler = None
        ui.pbackup_auto_enable.toggled.connect(self._auto_enable_changed)
        ui.pbackup_auto_days.currentIndexChanged.connect(self._auto_days_changed)
        ui.pbackup_auto_keep.valueChanged.connect(lambda v: self._save("autobackup_keep", int(v)))
        ui.pbackup_auto_now.clicked.connect(self.auto_now)
        ui.pbackup_auto_open.clicked.connect(self.auto_open)
        for cb, _ in ui.pbackup_checks.values():
            cb.toggled.connect(self._update_total)
        QtCore.QTimer.singleShot(1200, self.recalculate)

    def attach(self, signals):
        self.signals = signals
        from app.utils.auto_backup import AutoBackupScheduler
        cfg = signals.configuration_settings
        ui = self.ui
        self._loading = True
        ui.pbackup_auto_enable.setChecked(bool(cfg.get_main_setting("autobackup_enabled") or False))
        days = int(cfg.get_main_setting("autobackup_days") or 1)
        ui.pbackup_auto_days.setCurrentIndex(max(0, ui.pbackup_auto_days.findData(days)))
        ui.pbackup_auto_keep.setValue(int(cfg.get_main_setting("autobackup_keep") or 5))
        self._loading = False
        self.scheduler = AutoBackupScheduler(
            lambda k, d=None: (cfg.get_main_setting(k) if cfg.get_main_setting(k) is not None else d),
            lambda k, v: cfg.update_main_setting(k, v),
            busy=lambda: bool(getattr(signals, "_is_generating", False)),
            on_done=lambda p: self._auto_done(p))
        self.scheduler.start()
        self._refresh_auto_status()

    # ------------------------------------------------------------------ automatic backups
    def _save(self, key, value):
        if getattr(self, "_loading", False) or self.signals is None:
            return
        self.signals.configuration_settings.update_main_setting(key, value)

    def _auto_enable_changed(self, value):
        self._save("autobackup_enabled", bool(value))
        self._refresh_auto_status()

    def _auto_days_changed(self, _i):
        self._save("autobackup_days", int(self.ui.pbackup_auto_days.currentData() or 1))

    def _auto_done(self, path):
        self._refresh_auto_status()

    def _refresh_auto_status(self):
        from app.utils.auto_backup import list_backups
        items = list_backups()
        if items:
            when = datetime.datetime.fromtimestamp(items[0].stat().st_mtime).strftime("%d.%m.%Y %H:%M")
            text = self.tr("autobackup_last", "Last automatic backup: {when} · {n} stored").format(when=when, n=len(items))
        else:
            text = self.tr("autobackup_none", "No automatic backup yet.")
        if not self.ui.pbackup_auto_enable.isChecked():
            text += "  ·  " + self.tr("autobackup_off", "automatic backups are off")
        self.ui.pbackup_auto_status.setText(text)

    def auto_now(self):
        reason = self._busy_reason()
        if reason:
            return self._warn(reason)
        import asyncio
        from app.utils.auto_backup import create_now, prune

        async def job():
            self.ui.pbackup_auto_now.setEnabled(False)
            path = await asyncio.to_thread(create_now)
            if path is not None:
                prune(int(self.ui.pbackup_auto_keep.value()))
                self._save("autobackup_last", __import__("time").time())
            self.ui.pbackup_auto_now.setEnabled(True)
            self._refresh_auto_status()
            if path is None:
                self._warn(self.tr("autobackup_failed", "The automatic backup failed. See the log for details."))
        asyncio.ensure_future(job())

    def auto_open(self):
        from app.utils.auto_backup import auto_dir
        folder = auto_dir()
        folder.mkdir(parents=True, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(str(folder)))

    # ------------------------------------------------------------------ helpers
    def _backup_dir(self):
        d = os.path.join(self.root, "Backups")
        os.makedirs(d, exist_ok=True)
        return d

    def _set_default_path(self):
        stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
        self.ui.pbackup_path.setText(os.path.join(self._backup_dir(), f"Yume_Backup_{stamp}.yumepack"))

    def _busy_reason(self):
        if self.worker is not None and self.worker.isRunning():
            return self.tr("pbackup_busy_running", "Another backup operation is running.")
        if getattr(self.signals, "_is_generating", False):
            return self.tr("pbackup_busy_generating", "A response is being generated right now.")
        try:
            from app.utils.models_hub import DownloadCoordinator
            if DownloadCoordinator.instance().has_active():
                return self.tr("pbackup_busy_download", "A model download is in progress.")
        except Exception:
            pass
        return None

    def _warn(self, text):
        QtWidgets.QMessageBox.warning(self.ui.options_page, self.tr("pbackup_title", "Profile backup"), text)

    def _selected(self):
        return [k for k, (cb, _) in self.ui.pbackup_checks.items() if cb.isChecked()]

    def recalculate(self):
        from app.utils.profile_backup import BACKUP_GROUPS, estimate_group, format_size
        for g in BACKUP_GROUPS:
            try:
                total, count = estimate_group(g, self.root)
            except Exception:
                total, count = 0, 0
            cb, size = self.ui.pbackup_checks[g.key]
            size.setText(format_size(total) if count else "—")
            cb.setProperty("bytes", total if count else 0)
        self._update_total()

    def _update_total(self, *_):
        from app.utils.profile_backup import format_size
        total = sum(int(cb.property("bytes") or 0) for cb, _ in self.ui.pbackup_checks.values() if cb.isChecked())
        self.ui.pbackup_total.setText(f"{self.tr('pbackup_total', 'Total:')} ~{format_size(total)}" if total else
                                      self.tr("pbackup_nothing", "Nothing to save"))

    def browse(self):
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self.ui.options_page, self.tr("pbackup_save_dialog", "Save profile backup"),
            self.ui.pbackup_path.text(), "Yume profile backup (*.yumepack)")
        if path:
            self.ui.pbackup_path.setText(path if path.lower().endswith(".yumepack") else path + ".yumepack")

    def open_folder(self):
        folder = os.path.dirname(self.ui.pbackup_path.text()) or self._backup_dir()
        os.makedirs(folder, exist_ok=True)
        QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

    def _running(self, running):
        ui = self.ui
        ui.pbackup_progress.setVisible(running)
        ui.pbackup_status.setVisible(running)
        for w in (ui.pbackup_create, ui.pbackup_recalc, ui.pbackup_pick, ui.pbackup_browse):
            w.setEnabled(not running)
        ui.pbackup_restore.setEnabled((not running) and self.pack_path is not None)
        if not running:
            self.worker = None

    # ------------------------------------------------------------------ export
    def start_export(self):
        reason = self._busy_reason()
        if reason:
            return self._warn(reason)
        dest = self.ui.pbackup_path.text().strip()
        if not dest:
            return self._warn(self.tr("pbackup_need_path", "Choose where to save the backup first."))
        if not dest.lower().endswith(".yumepack"):
            dest += ".yumepack"
            self.ui.pbackup_path.setText(dest)
        keys = self._selected()
        if "characters" not in keys:
            return self._warn(self.tr("pbackup_chars_required", "Characters cannot be excluded."))
        if "api_keys" in keys:
            answer = QtWidgets.QMessageBox.question(
                self.ui.options_page, self.tr("pbackup_title", "Profile backup"),
                self.tr("pbackup_api_warning", "The backup will contain your API keys. Keep the file private. Continue?"),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        if os.path.exists(dest):
            answer = QtWidgets.QMessageBox.question(
                self.ui.options_page, self.tr("pbackup_title", "Profile backup"),
                self.tr("pbackup_overwrite", "A file already exists there. Replace it?"),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
                QtWidgets.QMessageBox.StandardButton.No)
            if answer != QtWidgets.QMessageBox.StandardButton.Yes:
                return
        from app.utils.profile_backup import ExportWorker
        try:
            from app.utils.update_checker import current_version
            version = current_version()
        except Exception:
            version = ""
        self.worker = ExportWorker(dest_path=dest, root=self.root, selected_keys=keys, app_version=version)
        self._wire(self.worker, "export")
        self.ui.pbackup_progress.setValue(0)
        self.ui.pbackup_status.setText(self.tr("pbackup_collecting", "Collecting files …"))
        self._running(True)
        self.worker.start()

    # ------------------------------------------------------------------ restore
    def pick_pack(self):
        reason = self._busy_reason()
        if reason:
            return self._warn(reason)
        start = os.path.dirname(self.pack_path or "") or self._backup_dir()
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self.ui.options_page, self.tr("pbackup_open_dialog", "Choose a profile backup"), start,
            "Profile backup (*.yumepack *.sowpack *.zip)")
        if path:
            self.load_preview(path)

    def load_preview(self, path):
        from app.utils.profile_backup import read_manifest, format_size
        manifest, err = read_manifest(path)
        if err in ("bad_zip", "unreadable", "bad_manifest", "no_manifest"):
            return self._warn(self.tr("pbackup_not_a_backup", "This file is not a valid profile backup."))
        self.pack_path = path
        lines = [f"<b>{os.path.basename(path)}</b>  ·  {format_size(os.path.getsize(path))}"]
        if manifest:
            lines.append(f"{self.tr('pbackup_created', 'Created:')} {str(manifest.get('created_at', ''))[:16].replace('T', ' ')}"
                         + (f"  ·  v{manifest['app_version'].lstrip('v')}" if manifest.get("app_version") else ""))
            names = [self.tr(f"backup_grp_{k}", k.replace('_', ' ')) for k, v in manifest.get("contents", {}).items() if v]
            if names:
                lines.append("<span style='color:#B9A9C9'>" + " · ".join(names) + "</span>")
        if err == "newer_version":
            lines.append("<span style='color:#F6C177'>⚠ " + self.tr("pbackup_newer", "Created by a newer version - restoring may cause problems.") + "</span>")
        self.ui.pbackup_info.setText("<br>".join(lines))
        self.ui.pbackup_info.show()
        self.ui.pbackup_restore.setEnabled(True)

    def start_restore(self):
        reason = self._busy_reason()
        if reason:
            return self._warn(reason)
        if not self.pack_path or not os.path.exists(self.pack_path):
            return self._warn(self.tr("pbackup_pick_first", "Choose a backup file first."))
        answer = QtWidgets.QMessageBox.question(
            self.ui.options_page, self.tr("pbackup_restore_confirm_title", "Restore backup?"),
            self.tr("pbackup_restore_confirm",
                    "Your current characters, chats, memories and the selected data will be REPLACED by the backup.\n\n"
                    "A safety snapshot of your current data is created first (folder .soul_stage/backups). "
                    "A restart is needed afterwards. Continue?"),
            QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
            QtWidgets.QMessageBox.StandardButton.No)
        if answer != QtWidgets.QMessageBox.StandardButton.Yes:
            return
        from app.utils.profile_backup import RestoreWorker
        self.worker = RestoreWorker(pack_path=self.pack_path, root=self.root)
        self._wire(self.worker, "restore")
        self.ui.pbackup_progress.setValue(0)
        self.ui.pbackup_status.setText(self.tr("pbackup_phase_validate", "Checking backup …"))
        self._running(True)
        self.worker.start()

    # ------------------------------------------------------------------ worker plumbing
    def _wire(self, worker, kind):
        status, bar = self.ui.pbackup_status, self.ui.pbackup_progress
        phases = {
            "validate": self.tr("pbackup_phase_validate", "Checking backup …"),
            "extract": self.tr("pbackup_phase_extract", "Unpacking …"),
            "safety_backup": self.tr("pbackup_phase_safety", "Creating safety snapshot …"),
            "apply": self.tr("pbackup_phase_apply", "Restoring files …"),
            "cleanup": self.tr("pbackup_phase_cleanup", "Cleaning up …"),
        }

        def on_progress(pct, text):
            bar.setValue(pct)
            status.setText(phases.get(text, text))

        def on_failed(code):
            self._running(False)
            names = {
                "permission": self.tr("pbackup_err_permission", "Access denied. Close programs using these files and try again."),
                "bad_zip": self.tr("pbackup_not_a_backup", "This file is not a valid profile backup."),
                "no_manifest": self.tr("pbackup_not_a_backup", "This file is not a valid profile backup."),
                "nothing_to_export": self.tr("pbackup_err_empty", "There was nothing to back up."),
                "apply_failed_rolled_back": self.tr("pbackup_err_rolled_back", "Restoring failed. Your previous data was restored from the safety snapshot."),
                "apply_failed_no_rollback": self.tr("pbackup_err_no_rollback", "Restoring failed and the rollback failed too. Use the snapshot in .soul_stage/backups to recover."),
            }
            code = str(code)
            text = names.get(code, code)
            if code.startswith("failed_rolled_back"):
                text = names["apply_failed_rolled_back"] + "\n" + code.split(":", 1)[-1]
            QtWidgets.QMessageBox.critical(self.ui.options_page, self.tr("pbackup_failed", "Backup failed"), text)

        def on_cancel():
            self._running(False)

        worker.progress.connect(on_progress)
        worker.failed.connect(on_failed)
        worker.cancelled.connect(on_cancel)
        if kind == "export":
            def on_ok(path):
                self._running(False)
                self._set_default_path()
                QtWidgets.QMessageBox.information(
                    self.ui.options_page, self.tr("pbackup_done_title", "Backup complete"),
                    self.tr("pbackup_done", "Backup saved to:\n{path}").format(path=path))
            worker.finished_ok.connect(on_ok)
        else:
            def on_ok(summary):
                self._running(False)
                restart = QtWidgets.QMessageBox.question(
                    self.ui.options_page, self.tr("pbackup_restored_title", "Restore complete"),
                    self.tr("pbackup_restored", "{count} files were restored.\nRestart now to load the restored data?")
                    .format(count=summary.get("applied", 0)),
                    QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
                if restart == QtWidgets.QMessageBox.StandardButton.Yes:
                    restart_program(self.root)          # starts the new instance only when this one has ended
                    QtWidgets.QApplication.quit()
                    QtCore.QTimer.singleShot(4000, lambda: os._exit(0))     # background threads must not keep the old process alive
            worker.finished_ok.connect(on_ok)
