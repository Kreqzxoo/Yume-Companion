"""'Yume LLM Server' installer for another PC: a button that saves the setup exe where the user wants it."""
from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from PyQt6 import QtCore, QtGui, QtWidgets

from app.gui.network_llm import BTN

logger = logging.getLogger("ServerInstaller")
INSTALLER_NAME = "Yume-LLM-Server-Setup.exe"


def installer_file():
    for base in (Path("tools") / "server", Path("assets") / "server", Path(".")):
        p = base / INSTALLER_NAME
        if p.is_file():
            return p
    return None


def build_installer_row(ui, title_key="srv_installer_hint", default_hint=None):
    """Hint text + 'save installer' button, to be placed in the LLM and the vision settings."""
    tr = ui.translations.get
    box = QtWidgets.QFrame()
    box.setStyleSheet("QFrame { background: rgba(182,156,255,0.07); border: 1px solid rgba(182,156,255,0.28); border-radius: 12px; }")
    row = QtWidgets.QHBoxLayout(box)
    row.setContentsMargins(14, 10, 14, 10)
    hint = QtWidgets.QLabel(tr(title_key, default_hint or
                               "KI auf einem anderen PC laufen lassen? Der „Yume LLM Server“ richtet dort alles ein: Engine, empfohlene Modelle passend zur Hardware, "
                               "Start-Button – mit Installer, Desktop-Verknüpfung und Deinstallation."))
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #E4D4FF; border: none; background: transparent;")
    btn = QtWidgets.QPushButton(tr("srv_installer_button", "Server-Installer speichern …"))
    btn.setMinimumHeight(38)
    btn.setMinimumWidth(1)
    btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
    btn.setStyleSheet(BTN)
    row.addWidget(hint, 1)
    row.addWidget(btn)
    btn.clicked.connect(lambda: save_installer(btn.window(), ui.translations))
    ui.pushButton_get_server = getattr(ui, "pushButton_get_server", btn)
    return box


def save_installer(parent, translations):
    tr = translations.get
    src = installer_file()
    if src is None:
        QtWidgets.QMessageBox.warning(parent, "Yume LLM Server", tr(
            "srv_installer_missing", "Der Server-Installer wurde in diesem Programmordner nicht gefunden (tools\\server\\Yume-LLM-Server-Setup.exe)."))
        return
    start = Path(os.path.expanduser("~")) / "Desktop"
    if not start.is_dir():
        start = Path(os.path.expanduser("~"))
    target, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent, tr("srv_installer_dialog", "Server-Installer speichern (z. B. auf einen USB-Stick oder in einen Netzwerkordner)"),
        str(start / INSTALLER_NAME), "Installer (*.exe)")
    if not target:
        return
    try:
        shutil.copy2(src, target)
    except OSError as exc:
        QtWidgets.QMessageBox.warning(parent, "Yume LLM Server", str(exc))
        return
    try:
        from app.gui.custom_widgets import sow_toast
        sow_toast(parent=parent, title="Yume LLM Server",
                  text=tr("srv_installer_saved", "Installer gespeichert: {p}\nAuf dem anderen PC ausführen – danach dort „Server starten“ und hier die angezeigte Adresse eintragen.").format(p=target),
                  msg_type="success", duration=9000)
    except Exception:
        logger.debug("toast failed", exc_info=True)
    try:
        subprocess.Popen(["explorer.exe", "/select,", os.path.normpath(target)])
    except Exception:
        pass


APK_NAME = "Yume-Companion.apk"


def apk_file():
    for base in (Path("tools") / "android", Path("assets") / "android", Path(".")):
        p = base / APK_NAME
        if p.is_file():
            return p
    return None


def save_apk(parent, translations):
    """Copy the Android app (APK) to a place the user chooses (USB stick, cloud folder, ...)."""
    tr = translations.get
    src = apk_file()
    if src is None:
        QtWidgets.QMessageBox.warning(parent, "Yume Companion", tr(
            "apk_missing", "Die APK wurde in diesem Programmordner nicht gefunden (tools\\android\\Yume-Companion.apk). Sie lässt sich mit dem Ordner „Yume Android“ (build-apk.bat) bauen."))
        return
    start = Path(os.path.expanduser("~")) / "Desktop"
    if not start.is_dir():
        start = Path(os.path.expanduser("~"))
    target, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent, tr("apk_dialog", "APK speichern (dann auf das Handy übertragen und installieren)"), str(start / APK_NAME), "Android (*.apk)")
    if not target:
        return
    try:
        shutil.copy2(src, target)
    except OSError as exc:
        QtWidgets.QMessageBox.warning(parent, "Yume Companion", str(exc))
        return
    try:
        from app.gui.custom_widgets import sow_toast
        sow_toast(parent=parent, title="Yume Companion",
                  text=tr("apk_saved", "APK gespeichert: {p}\nAuf dem Handy installieren (Installation aus unbekannten Quellen erlauben), dann „Mit QR-Code koppeln“.").format(p=target),
                  msg_type="success", duration=9000)
    except Exception:
        logger.debug("toast failed", exc_info=True)
    try:
        subprocess.Popen(["explorer.exe", "/select,", os.path.normpath(target)])
    except Exception:
        pass
