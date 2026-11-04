"""Android Connector: QR code pairing, paired devices, phone permissions of the AI."""
from __future__ import annotations

import asyncio
import io
import logging
import subprocess
import sys
import time

from PyQt6 import QtCore, QtGui, QtWidgets

from app.gui.network_llm import BTN
from app.utils import mobile_devices

logger = logging.getLogger("AndroidPairing")
QR_LIFETIME = 150          # seconds until a fresh code is generated automatically
FW_RULE = "Yume Companion Android"


def firewall_rule_ports() -> set[str] | None:
    """Ports opened by our Windows firewall rule (None when it does not exist / cannot be read)."""
    if sys.platform != "win32":
        return {"n/a"}
    try:
        out = subprocess.run(["netsh", "advfirewall", "firewall", "show", "rule", f"name={FW_RULE}"], capture_output=True, text=True,
                             creationflags=0x08000000, timeout=8)
        if out.returncode != 0:
            return None
        ports = set()
        for line in out.stdout.splitlines():
            key, _, val = line.partition(":")
            if key.strip().lower() in ("lokaler port", "localport"):
                ports.update(x.strip() for x in val.split(",") if x.strip())
        return ports or None
    except Exception:
        return None


def open_firewall(port: int) -> bool:
    """Creates the inbound rule (Windows asks for administrator permission)."""
    cmd = (f'netsh advfirewall firewall delete rule name="{FW_RULE}" & '
           f'netsh advfirewall firewall add rule name="{FW_RULE}" dir=in action=allow protocol=TCP localport={port} profile=any')
    ps = f"Start-Process -FilePath cmd.exe -ArgumentList '/c {cmd}' -Verb RunAs -WindowStyle Hidden -Wait"
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", ps], creationflags=0x08000000, timeout=120)
    except Exception:
        return False
    return firewall_rule_ports() is not None


def build_pairing_card(ui, create_glass_card, font_input):
    tr = ui.translations.get
    card, l = create_glass_card(tr("pair_title", "Handy koppeln (Yume Companion für Android)"))
    modes = QtWidgets.QHBoxLayout()
    ui.pushButton_pair_mode_install = QtWidgets.QPushButton(tr("pair_mode_install", "App noch nicht installiert"))
    ui.pushButton_pair_mode_connect = QtWidgets.QPushButton(tr("pair_mode_connect", "App ist installiert"))
    for b in (ui.pushButton_pair_mode_install, ui.pushButton_pair_mode_connect):
        b.setCheckable(True)
        b.setAutoExclusive(True)
        b.setMinimumHeight(38)
        b.setMinimumWidth(1)
        b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(BTN + "QPushButton:checked { background: rgba(255,143,199,0.30); border: 1px solid #FF8FC7; }")
        modes.addWidget(b, 1)
    l.addLayout(modes)
    hint = QtWidgets.QLabel("")
    ui.label_pair_hint = hint
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(hint)

    row = QtWidgets.QHBoxLayout()
    row.setSpacing(18)
    ui.label_pair_qr = QtWidgets.QLabel()
    ui.label_pair_qr.setFixedSize(260, 260)
    ui.label_pair_qr.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    ui.label_pair_qr.setStyleSheet("background: white; border-radius: 14px; border: none;")
    row.addWidget(ui.label_pair_qr)

    right = QtWidgets.QVBoxLayout()
    right.setSpacing(10)
    ui.label_pair_status = QtWidgets.QLabel("")
    ui.label_pair_status.setWordWrap(True)
    ui.label_pair_status.setStyleSheet("color: #F1E8F6; border: none; background: transparent; font-weight: 600;")
    ui.label_pair_countdown = QtWidgets.QLabel("")
    ui.label_pair_countdown.setStyleSheet("color: #B69CFF; border: none; background: transparent;")
    ui.pushButton_pair_server = QtWidgets.QPushButton(tr("android_webserver_start", "Webserver starten"))
    ui.pushButton_pair_firewall = QtWidgets.QPushButton(tr("pair_fw_button", "Windows-Firewall für das Handy freigeben …"))
    ui.pushButton_pair_new = QtWidgets.QPushButton(tr("pair_new", "Neuen QR-Code erzeugen"))
    ui.pushButton_pair_apk = QtWidgets.QPushButton(tr("pair_apk", "APK für das Handy speichern …"))
    ui.pushButton_pair_copy = QtWidgets.QPushButton(tr("pair_copy", "Kopplungs-Link kopieren (statt QR)"))
    for b in (ui.pushButton_pair_server, ui.pushButton_pair_firewall, ui.pushButton_pair_new, ui.pushButton_pair_apk, ui.pushButton_pair_copy):
        b.setMinimumHeight(38)
        b.setMinimumWidth(1)
        b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet(BTN)
    right.addWidget(ui.label_pair_status)
    right.addWidget(ui.label_pair_countdown)
    right.addSpacing(6)
    right.addWidget(ui.pushButton_pair_server)
    right.addWidget(ui.pushButton_pair_firewall)
    right.addWidget(ui.pushButton_pair_new)
    right.addWidget(ui.pushButton_pair_apk)
    right.addWidget(ui.pushButton_pair_copy)
    right.addStretch()
    row.addLayout(right, 1)
    l.addLayout(row)

    dev_label = QtWidgets.QLabel(tr("pair_devices", "GEKOPPELTE GERÄTE"))
    dev_label.setStyleSheet("color: #B69CFF; font-weight: 700; border: none; background: transparent;")
    l.addWidget(dev_label)
    ui.listWidget_android_devices = QtWidgets.QListWidget()
    ui.listWidget_android_devices.setFixedHeight(110)
    ui.listWidget_android_devices.setStyleSheet(
        "QListWidget { background: rgba(14,9,22,0.55); border: 1px solid rgba(255,143,199,0.28); border-radius: 9px; color: #F1E8F6; padding: 4px; }"
        "QListWidget::item { padding: 6px; } QListWidget::item:selected { background: rgba(255,143,199,0.18); }")
    l.addWidget(ui.listWidget_android_devices)
    ui.pushButton_pair_revoke = QtWidgets.QPushButton(tr("pair_revoke", "Ausgewähltes Gerät entfernen (Zugriff entziehen)"))
    ui.pushButton_pair_revoke.setMinimumHeight(36)
    ui.pushButton_pair_revoke.setMinimumWidth(1)
    ui.pushButton_pair_revoke.setStyleSheet(BTN)
    l.addWidget(ui.pushButton_pair_revoke)

    ui.checkBox_android_phone_control = QtWidgets.QCheckBox(tr("pair_phone_control", "Die KI darf das Handy bedienen (Apps öffnen, Bildschirm lesen, anrufen …)"))
    ui.checkBox_android_call_mute_pc = QtWidgets.QCheckBox(tr("pair_call_mute", "Bei Handy-Anrufen: Stimme nur auf dem Handy, PC-Lautsprecher stumm"))
    ui.checkBox_android_autostart = QtWidgets.QCheckBox(tr("android_autostart", "Android Connector (Webserver) zusammen mit dem Programm starten"))
    ui.checkBox_android_speech_only = QtWidgets.QCheckBox(tr("android_speech_only", "Aufs Handy nur das Gesprochene senden (Text in Anführungszeichen) – ohne *Handlungen* und Beschreibungen"))
    for cb in (ui.checkBox_android_phone_control, ui.checkBox_android_call_mute_pc, ui.checkBox_android_speech_only, ui.checkBox_android_autostart):
        cb.setFont(font_input)
        cb.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        l.addWidget(cb)

    ui.android_pairing_controller = AndroidPairingController(ui)
    return card


class AndroidPairingController(QtCore.QObject):
    apk_found = QtCore.pyqtSignal(str)          # address of the newest APK, from the lookup thread

    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.tr = ui.translations.get
        self.signals = None
        self._url = ""
        self._expires = 0.0
        self._loading = True
        self._mode = ""                        # "install" = QR code downloads the app, "connect" = QR code pairs the installed app
        self._apk_url = ""
        self._apk_checked = 0.0
        self.apk_found.connect(self._on_apk_found)
        ui.pushButton_pair_mode_install.clicked.connect(lambda: self.set_mode("install"))
        ui.pushButton_pair_mode_connect.clicked.connect(lambda: self.set_mode("connect"))
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)
        ui.pushButton_pair_new.clicked.connect(self._new_clicked)
        ui.pushButton_pair_server.clicked.connect(self._toggle_server)
        ui.pushButton_pair_firewall.clicked.connect(self._open_firewall)
        self._fw_checked = 0.0
        self._fw_ports = None
        ui.pushButton_pair_copy.clicked.connect(self._copy)
        ui.pushButton_pair_apk.clicked.connect(self._save_apk)
        ui.pushButton_pair_revoke.clicked.connect(self._revoke)
        ui.checkBox_android_phone_control.toggled.connect(lambda v: self._set("android_phone_control", bool(v)))
        ui.checkBox_android_call_mute_pc.toggled.connect(lambda v: self._set("android_call_mute_pc", bool(v)))
        ui.checkBox_android_autostart.toggled.connect(lambda v: self._set("android_autostart", bool(v)))
        ui.checkBox_android_speech_only.toggled.connect(lambda v: self._set("android_speech_only", bool(v)))

    def attach(self, signals):
        self.signals = signals
        s = signals.configuration_settings
        self._loading = True
        self.ui.checkBox_android_phone_control.setChecked(s.get_main_setting("android_phone_control") is not False)
        self.ui.checkBox_android_call_mute_pc.setChecked(s.get_main_setting("android_call_mute_pc") is not False)
        self.ui.checkBox_android_autostart.setChecked(bool(s.get_main_setting("android_autostart")))
        self.ui.checkBox_android_speech_only.setChecked(s.get_main_setting("android_speech_only") is not False)
        self._loading = False
        # no phone paired yet: the app is probably not installed either -> offer the download first
        has_device = False
        try:
            has_device = bool(mobile_devices.get_registry().list_devices())
        except Exception:
            pass
        self.set_mode("connect" if has_device else "install")
        self.timer.start()
        if self.ui.checkBox_android_autostart.isChecked():
            # Not through a Qt timer: during start-up the event loop is re-entered from inside a task, and a server task created
            # there never runs ("Cannot enter into task ...") - the server then hangs in "Starting ...".
            asyncio.ensure_future(self._autostart_async())

    def _set(self, key, value):
        if not self._loading and self.signals is not None:
            self.signals.configuration_settings.update_main_setting(key, value)

    # ------------------------------------------------------------------ QR code
    def _urls(self):
        s = self.signals.configuration_settings
        port = int(s.get_main_setting("web_server_port") or 8000)
        local = mobile_devices.fresh_local_url(s.get_main_setting("android_local_url"), port)
        remote = (s.get_main_setting("android_remote_url") or "").rstrip("/")
        return local, remote

    def set_mode(self, mode: str):
        self._mode = mode
        install = mode == "install"
        self.ui.pushButton_pair_mode_install.setChecked(install)
        self.ui.pushButton_pair_mode_connect.setChecked(not install)
        self.ui.label_pair_hint.setText(self.tr(
            "pair_hint_install",
            "Scanne diesen Code mit der Handy-Kamera: Er öffnet den Download der neuesten Android-App (APK). Danach die Datei öffnen und die Installation erlauben. "
            "Ist die App installiert, oben auf „App ist installiert“ drücken.") if install else self.tr(
            "pair_hint",
            "1. App öffnen → „Mit QR-Code koppeln“.  2. Diesen Code scannen. "
            "Der Code ist nur wenige Minuten gültig und nur einmal verwendbar – er wird ständig neu erzeugt. Das Handy bekommt danach seinen eigenen, "
            "jederzeit widerrufbaren Schlüssel. Die App erkennt selbst, ob sie im Heimnetz (lokale Adresse) oder unterwegs (externe Domain, falls eingetragen) verbunden wird."))
        for b in (self.ui.pushButton_pair_new, self.ui.pushButton_pair_copy):
            b.setVisible(True)
        self.ui.pushButton_pair_new.setText(self.tr("pair_check_apk", "Download-Adresse neu suchen") if install else self.tr("pair_new", "Neuen QR-Code erzeugen"))
        self.ui.pushButton_pair_copy.setText(self.tr("pair_copy_apk", "Download-Link kopieren (statt QR)") if install else self.tr("pair_copy", "Kopplungs-Link kopieren (statt QR)"))
        self.ui.label_pair_countdown.setVisible(not install)
        self.ui.pushButton_pair_server.setVisible(not install)
        self.ui.pushButton_pair_firewall.setVisible(False if install else self.ui.pushButton_pair_firewall.isVisible())
        self.refresh_qr()

    def _new_clicked(self):
        if self._mode == "install":
            self._apk_url = ""
            self._apk_checked = 0.0
        self.refresh_qr()

    def _repo(self) -> str:
        from app.utils.branding import get_text
        from app.utils.update_checker import normalize_repo
        s = self.signals.configuration_settings
        return normalize_repo(s.get_main_setting("update_repo") or "") or normalize_repo(get_text("update_repo") or "")

    def _lookup_apk(self):
        """Finds the newest APK in the releases (in a thread, the window must not wait for GitHub)."""
        import threading
        from app.utils.apk_link import find_apk_url
        repo = self._repo()
        self._apk_checked = time.time()
        threading.Thread(target=lambda: self.apk_found.emit(find_apk_url(repo)), daemon=True).start()

    def _on_apk_found(self, url: str):
        self._apk_url = url
        if self._mode == "install":
            self.refresh_qr()

    def _draw_qr(self, data: str):
        import qrcode
        qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
        qr.add_data(data)
        qr.make(fit=True)
        image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
        buf = io.BytesIO()
        image.save(buf, format="PNG")
        pix = QtGui.QPixmap()
        pix.loadFromData(buf.getvalue(), "PNG")
        self.ui.label_pair_qr.setPixmap(pix.scaled(248, 248, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.FastTransformation))

    def _refresh_install_qr(self):
        if not self._apk_url or time.time() - self._apk_checked > 3600:
            if time.time() - self._apk_checked > 5:
                self._lookup_apk()
        if not self._apk_url:
            self.ui.label_pair_qr.setText(self.tr("pair_apk_searching", "Suche die neueste App …"))
            self.ui.label_pair_status.setText(self.tr("pair_apk_searching", "Suche die neueste App …"))
            return
        try:
            self._draw_qr(self._apk_url)
        except ImportError:
            self.ui.label_pair_qr.setText("pip install qrcode")
        is_file = self._apk_url.endswith(".apk")
        self.ui.label_pair_status.setText(self.tr("pair_apk_ready", "Neueste App: {u}").format(u=self._apk_url) if is_file else self.tr(
            "pair_apk_page", "Noch keine App-Datei gefunden oder GitHub nicht erreichbar – der Code öffnet die Release-Seite: {u}").format(u=self._apk_url))

    def refresh_qr(self):
        if self.signals is None:
            return
        if self._mode == "install":
            self._refresh_install_qr()
            return
        try:
            import qrcode
            local, remote = self._urls()
            self._url, self._expires, _code = mobile_devices.build_pair_url(self.signals.configuration_settings, local, remote)
            qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
            qr.add_data(self._url)
            qr.make(fit=True)
            image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
            buf = io.BytesIO()
            image.save(buf, format="PNG")
            pix = QtGui.QPixmap()
            pix.loadFromData(buf.getvalue(), "PNG")
            self.ui.label_pair_qr.setPixmap(pix.scaled(248, 248, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.FastTransformation))
        except ImportError:
            self.ui.label_pair_qr.setText("pip install qrcode")
        except Exception:
            logger.exception("QR code could not be created")
            self.ui.label_pair_qr.setText("QR error")
        self._update_status()

    def _port(self) -> int:
        try:
            return int(self.signals.configuration_settings.get_main_setting("web_server_port") or 8000)
        except Exception:
            return 8000

    def _open_firewall(self):
        if self.signals is None:
            return
        self.ui.pushButton_pair_firewall.setEnabled(False)
        QtWidgets.QApplication.processEvents()
        ok = open_firewall(self._port())
        self.ui.pushButton_pair_firewall.setEnabled(True)
        self._fw_checked = 0.0
        self._update_status()
        if not ok:
            QtWidgets.QMessageBox.information(self.ui.pushButton_pair_firewall.window(), "Yume Companion", self.tr(
                "pair_fw_failed", "Die Firewall-Regel wurde nicht angelegt (Administrator-Abfrage abgebrochen?)."))

    async def _autostart_async(self):
        await asyncio.sleep(4)                     # let the start-up sequence finish first
        if self.signals is not None and not getattr(self.signals, "web_server_running", False):
            self.signals.on_toggle_web_server()    # same lifecycle as the button, called from a normal loop iteration
            await asyncio.sleep(1)
            self._update_status()

    def _toggle_server(self):
        if self.signals is not None:
            self.signals._toggle_webserver_from_android()
            QtCore.QTimer.singleShot(600, self._update_status)

    def _update_status(self):
        if self._mode == "install":
            return
        s = self.signals
        running = bool(getattr(s, "web_server_running", False))
        self.ui.pushButton_pair_server.setText(self.tr("android_webserver_stop", "Webserver stoppen") if running
                                               else self.tr("android_webserver_start", "Webserver starten"))
        self.ui.pushButton_pair_server.setVisible(True)
        try:
            s._sync_android_webserver_controls()
        except Exception:
            pass
        local, remote = self._urls()
        if time.time() - self._fw_checked > 10:
            self._fw_checked = time.time()
            self._fw_ports = firewall_rule_ports()
        fw_ok = self._fw_ports is not None and ("n/a" in self._fw_ports or str(self._port()) in self._fw_ports or "Any" in self._fw_ports or "Beliebig" in self._fw_ports)
        self.ui.pushButton_pair_firewall.setVisible(not fw_ok)
        lines = []
        if not running:
            lines.append(self.tr("pair_server_off", "⚠ Der Webserver läuft nicht – rechts auf „Webserver starten“ drücken, sonst kann das Handy nicht koppeln."))
        if not fw_ok:
            lines.append(self.tr("pair_fw_missing", "⚠ Die Windows-Firewall blockiert wahrscheinlich Verbindungen vom Handy (Port {p}). Unten freigeben."
                                 ).format(p=self._port()))
        lines.append(self.tr("pair_local", "Lokal: {u}").format(u=local))
        lc = mobile_devices.LAST_CONTACT
        if lc["t"]:
            lines.append(self.tr("pair_contact", "Letzter Kontakt vom Handy: {ip} (vor {s} s)").format(ip=lc["ip"], s=int(time.time() - lc["t"])))
        elif running:
            lines.append(self.tr("pair_no_contact", "Noch kein Kontakt vom Handy – kommt nichts an, liegt es am Netzwerk (WLAN-Isolation / Gast-WLAN / VPN am Handy)."))
        lines.append(self.tr("pair_remote", "Extern: {u}").format(u=remote or self.tr("pair_remote_empty", "– (leer, jederzeit eintragbar)")))
        self.ui.label_pair_status.setText("\n".join(lines))

    def _tick(self):
        if self.signals is None:
            return
        if self._mode == "install":
            if self.ui.android_connector_tab.isVisible() and not self._apk_url:
                self.refresh_qr()
            return
        remaining = int(self._expires - time.time())
        if remaining <= 0:
            if self.ui.android_connector_tab.isVisible():
                self.refresh_qr()
            return
        self.ui.label_pair_countdown.setText(self.tr("pair_valid", "Code gültig noch {s} s – wird automatisch erneuert").format(s=remaining))
        if self.ui.android_connector_tab.isVisible() and remaining % 2 == 0:
            self._update_status()
        if remaining % 5 == 0 and self.ui.android_connector_tab.isVisible():
            self._refresh_devices()

    def _copy(self):
        text = self._apk_url if self._mode == "install" else self._url
        if text:
            QtWidgets.QApplication.clipboard().setText(text)

    def _save_apk(self):
        from app.gui.server_installer import save_apk
        save_apk(self.ui.pushButton_pair_apk.window(), self.ui.translations)

    # ------------------------------------------------------------------ devices
    def _refresh_devices(self):
        lw = self.ui.listWidget_android_devices
        selected = lw.currentItem().data(QtCore.Qt.ItemDataRole.UserRole) if lw.currentItem() else None
        lw.clear()
        online = set()
        bridge = mobile_devices.BRIDGE
        if bridge is not None:
            online = {m.get("device_id") for m in bridge.manager.meta.values() if m.get("role") == "phone"}
        for d in mobile_devices.get_registry().list_devices():
            seen = time.strftime("%d.%m. %H:%M", time.localtime(d.get("last_seen", 0)))
            item = QtWidgets.QListWidgetItem(("● " if d["id"] in online else "○ ") + f"{d['name']}   –   {self.tr('pair_last_seen', 'zuletzt')} {seen}")
            item.setData(QtCore.Qt.ItemDataRole.UserRole, d["id"])
            item.setForeground(QtGui.QColor("#6EE7A0" if d["id"] in online else "#B9A9C9"))
            lw.addItem(item)
            if d["id"] == selected:
                lw.setCurrentItem(item)

    def _revoke(self):
        item = self.ui.listWidget_android_devices.currentItem()
        if item is None:
            return
        device_id = item.data(QtCore.Qt.ItemDataRole.UserRole)
        if QtWidgets.QMessageBox.question(self.ui.pushButton_pair_revoke.window(), "Yume Companion",
                                          self.tr("pair_revoke_ask", "Dieses Gerät wirklich entfernen? Es muss danach neu gekoppelt werden.")) \
                == QtWidgets.QMessageBox.StandardButton.Yes:
            mobile_devices.get_registry().revoke(device_id)
            self._refresh_devices()
