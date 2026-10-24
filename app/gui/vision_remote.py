"""Vision AI: run the vision model on another PC (Yume LLM Server) instead of this one."""
from __future__ import annotations

import logging
import threading
from urllib.parse import urlparse

import requests
from PyQt6 import QtCore, QtGui, QtWidgets

from app.gui.network_llm import BTN, FIELD, TILE

logger = logging.getLogger("VisionRemote")
DEFAULT_PORT = 8081


def build_vision_remote_card(ui, create_glass_card, font_input):
    tr = ui.translations.get
    card, l = create_glass_card(tr("vis_where_title", "Wo läuft das Vision-Modell?"))
    ui.rb_vis_local = QtWidgets.QPushButton(tr("vis_this_pc", "💻  Auf diesem PC\nYume startet das Vision-Modell selbst."))
    ui.rb_vis_net = QtWidgets.QPushButton(tr("vis_other_pc", "🌐  Auf einem anderen PC im Netzwerk\nDort läuft der Yume LLM Server."))
    for rb in (ui.rb_vis_local, ui.rb_vis_net):
        rb.setStyleSheet(TILE)
        rb.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        rb.setMinimumHeight(64)
        rb.setCheckable(True)
        rb.setAutoExclusive(True)
        rb.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        rb.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
    ui.rb_vis_local.setChecked(True)
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(14)
    row.addWidget(ui.rb_vis_local, 1)
    row.addWidget(ui.rb_vis_net, 1)
    l.addLayout(row)

    ui.vis_net_box = QtWidgets.QWidget()
    nb = QtWidgets.QVBoxLayout(ui.vis_net_box)
    nb.setContentsMargins(0, 8, 0, 0)
    nb.setSpacing(10)
    addr = QtWidgets.QHBoxLayout()
    ui.lineEdit_vis_address = QtWidgets.QLineEdit()
    ui.lineEdit_vis_address.setPlaceholderText(tr("vis_address_ph", "IP-Adresse des anderen PCs, z. B. 192.168.1.50"))
    ui.lineEdit_vis_address.setFixedHeight(40)
    ui.lineEdit_vis_address.setStyleSheet(FIELD)
    ui.spin_vis_port = QtWidgets.QSpinBox()
    ui.spin_vis_port.setRange(1, 65535)
    ui.spin_vis_port.setValue(DEFAULT_PORT)
    ui.spin_vis_port.setPrefix(tr("netllm_port", "Port") + " ")
    ui.spin_vis_port.setFixedHeight(40)
    ui.spin_vis_port.setFixedWidth(130)
    ui.spin_vis_port.setStyleSheet(FIELD)
    ui.pushButton_vis_test = QtWidgets.QPushButton(tr("netllm_test", "Verbindung testen"))
    ui.pushButton_vis_test.setFixedHeight(40)
    ui.pushButton_vis_test.setMinimumWidth(170)
    ui.pushButton_vis_test.setStyleSheet(BTN)
    addr.addWidget(ui.lineEdit_vis_address, 1)
    addr.addWidget(ui.spin_vis_port)
    addr.addWidget(ui.pushButton_vis_test)
    nb.addLayout(addr)
    ui.lineEdit_vis_key = QtWidgets.QLineEdit()
    ui.lineEdit_vis_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
    ui.lineEdit_vis_key.setPlaceholderText(tr("netllm_key", "Zugangsschlüssel (nur falls der Server einen verlangt)"))
    ui.lineEdit_vis_key.setFixedHeight(36)
    ui.lineEdit_vis_key.setStyleSheet(FIELD)
    nb.addWidget(ui.lineEdit_vis_key)
    l.addWidget(ui.vis_net_box)

    ui.label_vis_live = QtWidgets.QLabel("")
    ui.label_vis_live.setWordWrap(True)
    ui.label_vis_live.setVisible(False)
    l.addWidget(ui.label_vis_live)
    tip = QtWidgets.QLabel(tr("vis_tip", "Tipp: Im Yume LLM Server auf dem anderen PC ein Vision-Modell wählen – es läuft dort auf Port 8081."))
    tip.setWordWrap(True)
    tip.setStyleSheet("color: #8D7AA3; font-size: 11px; border: none; background: transparent;")
    l.addWidget(tip)
    ui.vision_remote_controller = VisionRemoteController(ui)
    return card


class VisionRemoteController(QtCore.QObject):
    _tested = QtCore.pyqtSignal(bool, str)

    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.tr = ui.translations.get
        self.signals = None
        self._loading = True
        self._tested.connect(self._on_tested)
        ui.rb_vis_local.toggled.connect(self._mode_changed)
        ui.lineEdit_vis_address.editingFinished.connect(self._save)
        ui.spin_vis_port.editingFinished.connect(self._save)
        ui.lineEdit_vis_key.editingFinished.connect(self._save_key)
        ui.pushButton_vis_test.clicked.connect(self.test)

    def attach(self, signals):
        self.signals = signals
        ui = self.ui
        self._loading = True
        url = str(signals.configuration_settings.get_main_setting("vision_remote_url") or "")
        if url:
            u = urlparse(url if "://" in url else "http://" + url)
            ui.lineEdit_vis_address.setText(u.hostname or "")
            ui.spin_vis_port.setValue(u.port or DEFAULT_PORT)
            ui.rb_vis_net.setChecked(True)
        else:
            ui.rb_vis_local.setChecked(True)
        ui.lineEdit_vis_key.setText(signals.configuration_api.get_token("REMOTE_VISION_API_TOKEN") or "")
        ui.vis_net_box.setVisible(bool(url))
        self._loading = False

    def _mode_changed(self, local):
        self.ui.vis_net_box.setVisible(not local)
        if self._loading or self.signals is None:
            return
        if local:
            self.signals.configuration_settings.update_main_setting("vision_remote_url", "")
            self._live(None)
        else:
            self._save()
        try:
            self.ui.vision_controller.refresh()
        except Exception:
            pass

    def _save(self):
        if self._loading or self.signals is None or self.ui.rb_vis_local.isChecked():
            return None
        host = self.ui.lineEdit_vis_address.text().strip().replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
        if not host:
            return None
        url = f"http://{host}:{self.ui.spin_vis_port.value()}"
        self.signals.configuration_settings.update_main_setting("vision_remote_url", url)
        try:
            self.ui.vision_controller.refresh()
        except Exception:
            pass
        return url

    def _save_key(self):
        if not self._loading and self.signals is not None:
            self.signals.configuration_api.save_api_token("REMOTE_VISION_API_TOKEN", self.ui.lineEdit_vis_key.text().strip())

    def _live(self, state, text=""):
        lab = self.ui.label_vis_live
        if state is None:
            lab.setVisible(False)
            return
        fg, bg, bd = {"online": ("#6EE7A0", "rgba(110,231,160,0.10)", "rgba(110,231,160,0.45)"),
                      "loading": ("#F6C177", "rgba(246,193,119,0.10)", "rgba(246,193,119,0.45)"),
                      "offline": ("#FF8FA3", "rgba(255,143,163,0.10)", "rgba(255,143,163,0.45)")}[state]
        lab.setText(text)
        lab.setStyleSheet(f"color: {fg}; background: {bg}; border: 1px solid {bd}; border-radius: 10px; padding: 8px 12px; font-weight: 600;")
        lab.setVisible(True)

    def test(self):
        url = self._save()
        if not url:
            self._live("offline", "● " + self.tr("netllm_enter_ip", "Bitte zuerst die IP-Adresse des anderen PCs eingeben."))
            return
        key = self.ui.lineEdit_vis_key.text().strip()
        self._live("loading", self.tr("vis_live_loading", "● Verbinde mit dem Vision-Server ..."))
        self.ui.pushButton_vis_test.setEnabled(False)

        def work():
            try:
                headers = {"Authorization": f"Bearer {key}"} if key else {}
                r = requests.get(url + "/health", headers=headers, timeout=6)
                if r.status_code != 200:
                    self._tested.emit(False, f"HTTP {r.status_code}")
                    return
                name = ""
                try:
                    m = requests.get(url + "/v1/models", headers=headers, timeout=6).json()
                    name = (m.get("data") or [{}])[0].get("id", "") or ""
                    name = name.replace("\\", "/").split("/")[-1]
                except Exception:
                    pass
                self._tested.emit(True, name)
            except requests.exceptions.ConnectionError:
                self._tested.emit(False, self.tr("vis_fail_conn", "Keine Antwort. Läuft der Yume LLM Server mit einem Vision-Modell, und ist die Firewall-Freigabe eingerichtet?"))
            except Exception as exc:
                self._tested.emit(False, str(exc))
        threading.Thread(target=work, daemon=True).start()

    def _on_tested(self, ok, text):
        self.ui.pushButton_vis_test.setEnabled(True)
        if ok:
            self._live("online", self.tr("vis_live_online", "● Vision-Server erreichbar{m}").format(m=(" – " + text) if text else ""))
        else:
            self._live("offline", "● " + text)
