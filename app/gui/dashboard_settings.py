"""Settings page 'Dashboard': start/stop the Yume performance dashboard (own port), open it, copy the link."""
from __future__ import annotations

import asyncio
import logging
import secrets
import socket
import webbrowser

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("Dashboard")

DEFAULT_PORT = 8765


def build_dashboard_page(ui, create_scroll_page, create_glass_card, font_input):
    tr = ui.translations.get
    page, layout = create_scroll_page()
    page.setObjectName("dashboard_tab")

    card, l = create_glass_card(tr("dashboard_title", "Performance dashboard"))
    intro = QtWidgets.QLabel(tr(
        "dashboard_intro",
        "A separate web page (own port, own access token) showing CPU, RAM, GPU, processes, active services and the "
        "latest log lines of Yume Companion. It is read-only and never shows chats or API keys."))
    intro.setWordWrap(True)
    intro.setStyleSheet("color: rgba(220, 220, 230, 0.78); border: none; background: transparent;")
    l.addWidget(intro)

    ui.checkBox_dashboard_autostart = QtWidgets.QCheckBox(tr("dashboard_autostart", "Start the dashboard together with the program"))
    ui.checkBox_dashboard_autostart.setFont(font_input)
    l.addWidget(ui.checkBox_dashboard_autostart)
    ui.checkBox_dashboard_lan = QtWidgets.QCheckBox(tr("dashboard_lan", "Reachable from other devices in the home network (LAN)"))
    ui.checkBox_dashboard_lan.setFont(font_input)
    l.addWidget(ui.checkBox_dashboard_lan)

    form = QtWidgets.QFormLayout()
    form.setHorizontalSpacing(22)
    ui.spinBox_dashboard_port = QtWidgets.QSpinBox()
    ui.spinBox_dashboard_port.setRange(1024, 65535)
    ui.spinBox_dashboard_port.setValue(DEFAULT_PORT)
    ui.spinBox_dashboard_port.setFixedHeight(38)
    ui.spinBox_dashboard_port.setFont(font_input)
    form.addRow(tr("dashboard_port_label", "Port"), ui.spinBox_dashboard_port)
    ui.lineEdit_dashboard_url = QtWidgets.QLineEdit()
    ui.lineEdit_dashboard_url.setReadOnly(True)
    ui.lineEdit_dashboard_url.setFixedHeight(38)
    ui.lineEdit_dashboard_url.setFont(font_input)
    form.addRow(tr("dashboard_link_label", "Link"), ui.lineEdit_dashboard_url)
    l.addLayout(form)

    row = QtWidgets.QHBoxLayout()
    ui.pushButton_dashboard_toggle = QtWidgets.QPushButton(tr("dashboard_start", "Start dashboard"))
    ui.pushButton_dashboard_open = QtWidgets.QPushButton(tr("dashboard_open", "Open in browser"))
    ui.pushButton_dashboard_copy = QtWidgets.QPushButton(tr("dashboard_copy", "Copy link"))
    ui.pushButton_dashboard_newtoken = QtWidgets.QPushButton(tr("dashboard_new_token", "New access token"))
    for b in (ui.pushButton_dashboard_toggle, ui.pushButton_dashboard_open, ui.pushButton_dashboard_copy, ui.pushButton_dashboard_newtoken):
        b.setFont(font_input)
        b.setFixedHeight(38)
        b.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        b.setStyleSheet("QPushButton { background: rgba(255,255,255,0.045); color:#e0e0e0; border:1px solid rgba(255,255,255,0.13); "
                        "border-radius:8px; padding:4px 12px; } QPushButton:hover { background: rgba(255,143,199,0.14); "
                        "border-color: rgba(255,143,199,0.5); } QPushButton:disabled { color: rgba(255,255,255,0.3); }")
        row.addWidget(b)
    l.addLayout(row)

    ui.label_dashboard_status = QtWidgets.QLabel(tr("dashboard_status_stopped", "Status: stopped"))
    ui.label_dashboard_status.setWordWrap(True)
    ui.label_dashboard_status.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(ui.label_dashboard_status)

    note = QtWidgets.QLabel(tr(
        "dashboard_note",
        "By default the dashboard is only reachable on this PC. Enable LAN access only in networks you trust. "
        "The link contains the access token - do not share it."))
    note.setWordWrap(True)
    note.setStyleSheet("color: #F6C177; font-size: 11px; border: none; background: transparent;")
    l.addWidget(note)

    layout.addWidget(card)

    # ---------------- alerts card ----------------
    acard, al = create_glass_card(tr("alerts_title", "Alerts"))
    aintro = QtWidgets.QLabel(tr(
        "alerts_intro",
        "Warns you when GPU memory, RAM, CPU, temperature or the context run full, or when AI / voice output gets slow. "
        "Alerts are shown in the dashboard and as a small message in the app."))
    aintro.setWordWrap(True)
    aintro.setStyleSheet("color: rgba(220, 220, 230, 0.78); border: none; background: transparent;")
    al.addWidget(aintro)
    ui.checkBox_alerts_enabled = QtWidgets.QCheckBox(tr("alerts_enable", "Enable alerts"))
    ui.checkBox_alerts_enabled.setFont(font_input)
    ui.checkBox_alerts_toast = QtWidgets.QCheckBox(tr("alerts_toast", "Show alerts as a message in the app"))
    ui.checkBox_alerts_toast.setFont(font_input)
    al.addWidget(ui.checkBox_alerts_enabled)
    al.addWidget(ui.checkBox_alerts_toast)
    aform = QtWidgets.QFormLayout()
    aform.setHorizontalSpacing(22)
    ui.alert_spins = {}
    for key, label, default, lo, hi, suffix in (
        ("vram", tr("alerts_vram", "GPU memory from"), 92, 50, 99, " %"),
        ("ram", tr("alerts_ram", "System memory from"), 90, 50, 99, " %"),
        ("context", tr("alerts_context", "Context from"), 85, 50, 99, " %"),
        ("temp", tr("alerts_temp", "GPU temperature from"), 85, 60, 100, " °C"),
    ):
        spin = QtWidgets.QSpinBox()
        spin.setRange(lo, hi)
        spin.setValue(default)
        spin.setSuffix(suffix)
        spin.setFixedHeight(36)
        spin.setFont(font_input)
        aform.addRow(label, spin)
        ui.alert_spins[key] = spin
    al.addLayout(aform)
    layout.addWidget(acard)
    layout.addStretch()
    ui.dashboard_controller = DashboardController(ui)
    return page


class DashboardController(QtCore.QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.signals = None
        self.server = None
        self.task = None
        self.monitor = None
        self._loading = True
        self.tr = ui.translations.get
        ui.pushButton_dashboard_toggle.clicked.connect(self.toggle)
        ui.pushButton_dashboard_open.clicked.connect(self.open_browser)
        ui.pushButton_dashboard_copy.clicked.connect(self.copy_link)
        ui.pushButton_dashboard_newtoken.clicked.connect(self.new_token)
        ui.checkBox_dashboard_autostart.toggled.connect(lambda v: self._set("dashboard_autostart", bool(v)))
        ui.checkBox_dashboard_lan.toggled.connect(self._on_lan_changed)
        ui.checkBox_alerts_enabled.toggled.connect(self._on_alerts_enabled)
        ui.checkBox_alerts_toast.toggled.connect(lambda v: self._set("alerts_toast", bool(v)))
        for key, spin in ui.alert_spins.items():
            spin.valueChanged.connect(lambda v, k=key: self._set(f"alert_{k}", int(v)))
        ui.spinBox_dashboard_port.valueChanged.connect(self._on_port_changed)
        self._refresh_buttons()

    # ------------------------------------------------------------------ plumbing
    def attach(self, signals):
        """Called by main.py once the interface signals (and configuration) exist."""
        self.signals = signals
        self._loading = True
        ui = self.ui
        ui.checkBox_dashboard_autostart.setChecked(bool(self._get("dashboard_autostart", False)))
        ui.checkBox_dashboard_lan.setChecked(bool(self._get("dashboard_lan", False)))
        ui.spinBox_dashboard_port.setValue(int(self._get("dashboard_port", DEFAULT_PORT) or DEFAULT_PORT))
        ui.checkBox_alerts_enabled.setChecked(bool(self._get("alerts_enabled", True)))
        ui.checkBox_alerts_toast.setChecked(bool(self._get("alerts_toast", True)))
        for key, spin in ui.alert_spins.items():
            from app.utils.alerts import DEFAULTS
            spin.setValue(int(self._get(f"alert_{key}", DEFAULTS.get(key, spin.value())) or spin.value()))
        self._loading = False
        self._update_link()
        if ui.checkBox_alerts_enabled.isChecked():
            self._start_monitor()
        if ui.checkBox_dashboard_autostart.isChecked():
            QtCore.QTimer.singleShot(1500, self.start)

    def _cfg(self):
        return self.signals.configuration_settings if self.signals is not None else None

    # ------------------------------------------------------------------ alerts
    def _toast(self, level, title, text):
        if not bool(self._get("alerts_toast", True)):
            return
        try:
            from app.gui.custom_widgets import sow_toast
            sow_toast(parent=getattr(self.signals, "main_window", None), title=title, text=text,
                      msg_type="error" if level == "critical" else "warning", duration=7000)
        except Exception:
            logger.debug("alert toast failed", exc_info=True)

    def _start_monitor(self):
        if self.monitor is None:
            from app.utils.alerts import AlertMonitor
            self.monitor = AlertMonitor(self._get, self._toast)
        self.monitor.start()

    def _on_alerts_enabled(self, value):
        self._set("alerts_enabled", bool(value))
        if self.signals is None:
            return
        if value:
            self._start_monitor()
        elif self.monitor is not None:
            asyncio.ensure_future(self.monitor.stop())

    def _get(self, key, default=None):
        cfg = self._cfg()
        try:
            value = cfg.get_main_setting(key) if cfg else None
        except Exception:
            value = None
        return default if value is None else value

    def _set(self, key, value):
        cfg = self._cfg()
        if cfg is not None and not self._loading:
            cfg.update_main_setting(key, value)

    def _token(self) -> str:
        token = self._get("dashboard_token", "")
        if not token:
            token = secrets.token_urlsafe(18)
            self._set("dashboard_token", token)
        return token

    def _link(self) -> str:
        host = "127.0.0.1"
        if self.ui.checkBox_dashboard_lan.isChecked() and self.signals is not None:
            try:
                host = self.signals.get_local_ip() or host
            except Exception:
                pass
        return f"http://{host}:{self.ui.spinBox_dashboard_port.value()}/?token={self._token()}"

    def _update_link(self):
        self.ui.lineEdit_dashboard_url.setText(self._link() if self.signals is not None else "")

    def _on_lan_changed(self, value):
        self._set("dashboard_lan", bool(value))
        self._update_link()
        if self.running:
            self._status(self.tr("dashboard_restart_hint", "Restart the dashboard to apply the change."), "#F6C177")

    def _on_port_changed(self, value):
        self._set("dashboard_port", int(value))
        self._update_link()
        if self.running:
            self._status(self.tr("dashboard_restart_hint", "Restart the dashboard to apply the change."), "#F6C177")

    @property
    def running(self) -> bool:
        return self.server is not None and self.server.is_running()

    def _status(self, text, color="#B9A9C9"):
        self.ui.label_dashboard_status.setText(text)
        self.ui.label_dashboard_status.setStyleSheet(f"color: {color}; border: none; background: transparent;")

    def _refresh_buttons(self):
        run = self.running
        self.ui.pushButton_dashboard_toggle.setText(self.tr("dashboard_stop", "Stop dashboard") if run else self.tr("dashboard_start", "Start dashboard"))
        self.ui.pushButton_dashboard_open.setEnabled(run)
        self.ui.pushButton_dashboard_copy.setEnabled(self.signals is not None)

    # ------------------------------------------------------------------ actions
    def toggle(self):
        if self.running:
            self.stop_now()
        else:
            self.start()

    def start(self):
        if self.signals is None or self.running:
            return
        port = self.ui.spinBox_dashboard_port.value()
        if port == int(self._get("web_server_port", 8000) or 8000):
            self._status(self.tr("dashboard_port_conflict", "This port is used by the Android web server. Choose another one."), "#f87171")
            return
        lan = self.ui.checkBox_dashboard_lan.isChecked()
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
                probe.settimeout(0.3)
                if probe.connect_ex(("127.0.0.1", port)) == 0:
                    self._status(self.tr("dashboard_port_busy", "Port {port} is already in use.").format(port=port), "#f87171")
                    return
        except OSError:
            pass
        try:
            from app.utils.dashboard_server import DashboardServer
            self.server = DashboardServer(self.signals, self._token(), host="0.0.0.0" if lan else "127.0.0.1", port=port,
                                          allow_lan=lan, monitor=self.monitor if self.ui.checkBox_alerts_enabled.isChecked() else None)
        except Exception as exc:
            logger.exception("Dashboard could not be created")
            self._status(str(exc), "#f87171")
            return
        self.server.start_in_thread()
        QtCore.QTimer.singleShot(1200, self._check_started)
        self._status(self.tr("dashboard_status_running", "Status: running on port {port}").format(port=port), "#4ade80")
        self._refresh_buttons()
        self._update_link()

    def _check_started(self):
        if self.server is not None and not self.server.is_running():
            err = getattr(self.server, "error", None)
            self._status(self.tr("dashboard_status_error", "Dashboard error: {err}").format(err=err or "?"), "#f87171")
            self.server = None
        self._refresh_buttons()

    def stop_now(self):
        if self.server is not None:
            try:
                self.server.stop_thread()
            except Exception:
                logger.exception("Dashboard stop failed")
        self.task = None
        self.server = None
        self._status(self.tr("dashboard_status_stopped", "Status: stopped"))
        self._refresh_buttons()

    async def stop(self):
        self.stop_now()

    def open_browser(self):
        webbrowser.open(self._link())

    def copy_link(self):
        QtWidgets.QApplication.clipboard().setText(self._link())
        self._status(self.tr("dashboard_link_copied", "Link copied."), "#4ade80" if self.running else "#B9A9C9")

    def new_token(self):
        self._set("dashboard_token", secrets.token_urlsafe(18))
        self._update_link()
        if self.running:
            self.stop_now()
            self.start()

    async def _restart(self):
        await self.stop()
        self.start()
