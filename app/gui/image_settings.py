"""Settings page 'Bildgenerierung': the image AI treated like the language model - local, on another PC in the network, or cloud API."""
from __future__ import annotations

import ipaddress
import logging
import os
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
from PyQt6 import QtCore, QtGui, QtWidgets

from app.gui.network_llm import BTN, FIELD, TILE, local_ip

logger = logging.getLogger("ImageSettings")

PROVIDERS = ["Automatic1111", "ComfyUI (A1111 API)", "DALL-E 3", "NovelAI", "FLUX"]
LOCAL_PROVIDERS = ("Automatic1111", "ComfyUI (A1111 API)")
CLOUD_KEYS = {"NovelAI": "NOVELAI_API_TOKEN", "FLUX": "FAL_API_TOKEN"}
SCAN_PORTS = (7860, 7861, 7865, 8188, 8082)
PROVIDER_PORT = {"Automatic1111": 7860, "ComfyUI (A1111 API)": 8188}


def probe_image(host: str, port: int, timeout: float = 0.6):
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        return None
    base = f"http://{host}:{port}"
    for path, kind, provider in (("/sdapi/v1/options", "Automatic1111 / Forge / SD.Next", "Automatic1111"),
                                 ("/system_stats", "ComfyUI", "ComfyUI (A1111 API)")):
        try:
            if requests.get(base + path, timeout=1.5).status_code == 200:
                return {"host": host, "port": port, "kind": kind, "provider": provider}
        except requests.RequestException:
            continue
    return None


def scan_image_servers():
    ip = local_ip()
    if not ip:
        return []
    try:
        net = ipaddress.ip_network(ip + "/24", strict=False)
    except ValueError:
        return []
    hosts = [str(h) for h in net.hosts() if str(h) != ip] + ["127.0.0.1"]
    jobs = [(h, p) for h in hosts for p in SCAN_PORTS]
    found = []
    with ThreadPoolExecutor(max_workers=96) as pool:
        for res in pool.map(lambda hp: probe_image(*hp), jobs):
            if res:
                found.append(res)
    return found


def build_image_page(ui, create_scroll_page, create_glass_card, font_label, font_input):
    tr = ui.translations.get
    page, layout = create_scroll_page()
    page.setObjectName("image_gen_tab")

    # ------------------------------------------------------------------ card 1: enable + provider + where
    card, l = create_glass_card(tr("img_card_title", "Anbieter (lokal oder Cloud-API)"))
    hint = QtWidgets.QLabel(tr("img_intro", "Die Bild-KI erzeugt Bilder zur aktuellen Szene (Nachrichtenmenü → „Bild generieren“). "
                               "Sie läuft wie das Sprachmodell entweder auf diesem PC, auf einem anderen PC im Netzwerk oder als Cloud-Dienst."))
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(hint)
    ui.checkBox_img_enabled = QtWidgets.QCheckBox(tr("img_enable", "Bildgenerierung aktivieren"))
    ui.checkBox_img_enabled.setFont(font_input)
    ui.checkBox_img_enabled.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    l.addWidget(ui.checkBox_img_enabled)

    form = QtWidgets.QFormLayout()
    form.setVerticalSpacing(12)
    ui.comboBox_img_provider = QtWidgets.QComboBox()
    ui.comboBox_img_provider.setFixedHeight(40)
    ui.comboBox_img_provider.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    ui.comboBox_img_provider.addItems(PROVIDERS)
    lab = QtWidgets.QLabel(tr("img_provider", "Dienst"))
    lab.setFont(font_label)
    form.addRow(lab, ui.comboBox_img_provider)
    l.addLayout(form)
    ui.label_img_provider_hint = QtWidgets.QLabel(tr("img_provider_hint",
        "Cloud-Dienste (DALL-E, NovelAI, FLUX): Dienst wählen und Zugangsschlüssel eintragen. A1111 / Forge / ComfyUI: lokal oder auf einem anderen PC – siehe Karte darunter."))
    ui.label_img_provider_hint.setWordWrap(True)
    ui.label_img_provider_hint.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(ui.label_img_provider_hint)

    ui.img_cloud_box = QtWidgets.QWidget()
    cb = QtWidgets.QHBoxLayout(ui.img_cloud_box)
    cb.setContentsMargins(0, 6, 0, 0)
    ui.lineEdit_img_key = QtWidgets.QLineEdit()
    ui.lineEdit_img_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
    ui.lineEdit_img_key.setFixedHeight(40)
    ui.lineEdit_img_key.setStyleSheet(FIELD)
    ui.label_img_key_hint = QtWidgets.QLabel("")
    ui.label_img_key_hint.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    cb.addWidget(ui.lineEdit_img_key, 1)
    cb.addWidget(ui.label_img_key_hint)
    l.addWidget(ui.img_cloud_box)
    layout.addWidget(card)

    ui.img_where_card, l = create_glass_card(tr("img_where_title", "Wo läuft die Bild-KI?"))
    from app.gui.server_installer import build_installer_row
    l.addWidget(build_installer_row(ui, "srv_installer_hint_image",
        "Bild-KI auf einem anderen PC? Der „Yume LLM Server“ installiert dort die Bild-Engine und empfohlene Anime-Modelle – dann „Automatic1111“ wählen und die angezeigte Adresse (Port 8082) eintragen."))
    ui.img_local_box = QtWidgets.QWidget()
    lb = QtWidgets.QVBoxLayout(ui.img_local_box)
    lb.setContentsMargins(0, 6, 0, 0)
    lb.setSpacing(10)
    ui.rb_img_local = QtWidgets.QPushButton(tr("img_this_pc", "💻  Auf diesem PC\nA1111 / Forge / ComfyUI läuft hier."))
    ui.rb_img_net = QtWidgets.QPushButton(tr("img_other_pc", "🌐  Auf einem anderen PC im Netzwerk\nDort läuft A1111 / Forge / ComfyUI."))
    for rb in (ui.rb_img_local, ui.rb_img_net):
        rb.setStyleSheet(TILE)
        rb.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        rb.setMinimumHeight(64)
        rb.setCheckable(True)
        rb.setAutoExclusive(True)
        rb.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        rb.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
    ui.rb_img_local.setChecked(True)
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(14)
    row.addWidget(ui.rb_img_local, 1)
    row.addWidget(ui.rb_img_net, 1)
    lb.addLayout(row)

    addr = QtWidgets.QHBoxLayout()
    ui.lineEdit_img_address = QtWidgets.QLineEdit()
    ui.lineEdit_img_address.setPlaceholderText(tr("img_address_ph", "IP-Adresse des anderen PCs, z. B. 192.168.1.50"))
    ui.lineEdit_img_address.setFixedHeight(40)
    ui.lineEdit_img_address.setStyleSheet(FIELD)
    ui.spin_img_port = QtWidgets.QSpinBox()
    ui.spin_img_port.setRange(1, 65535)
    ui.spin_img_port.setValue(7860)
    ui.spin_img_port.setPrefix(tr("netllm_port", "Port") + " ")
    ui.spin_img_port.setFixedHeight(40)
    ui.spin_img_port.setFixedWidth(130)
    ui.spin_img_port.setStyleSheet(FIELD)
    ui.pushButton_img_test = QtWidgets.QPushButton(tr("netllm_test", "Verbindung testen"))
    ui.pushButton_img_test.setFixedHeight(40)
    ui.pushButton_img_test.setStyleSheet(BTN)
    addr.addWidget(ui.lineEdit_img_address, 1)
    addr.addWidget(ui.spin_img_port)
    ui.pushButton_img_test.setMinimumWidth(170)
    addr.addWidget(ui.pushButton_img_test)
    addr.addStretch(0)
    lb.addLayout(addr)

    srow = QtWidgets.QHBoxLayout()
    ui.pushButton_img_scan = QtWidgets.QPushButton(tr("img_scan", "🔍  Netzwerk nach Bild-Servern durchsuchen"))
    ui.pushButton_img_scan.setFixedHeight(36)
    ui.pushButton_img_scan.setStyleSheet(BTN)
    ui.comboBox_img_found = QtWidgets.QComboBox()
    ui.comboBox_img_found.setFixedHeight(36)
    ui.comboBox_img_found.setStyleSheet(FIELD)
    ui.comboBox_img_found.setVisible(False)
    srow.addWidget(ui.pushButton_img_scan)
    srow.addWidget(ui.comboBox_img_found, 1)
    lb.addLayout(srow)
    mrow = QtWidgets.QHBoxLayout()
    mlabel = QtWidgets.QLabel(tr("img_model", "Modell auf dem Server"))
    mlabel.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    ui.comboBox_img_model = QtWidgets.QComboBox()
    ui.comboBox_img_model.setEditable(True)
    ui.comboBox_img_model.setFixedHeight(36)
    ui.comboBox_img_model.setStyleSheet(FIELD)
    ui.comboBox_img_model.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
    ui.comboBox_img_model.setMinimumContentsLength(12)
    ui.comboBox_img_model.lineEdit().setPlaceholderText(tr("img_model_ph", "wird nach dem Verbindungstest automatisch gefüllt"))
    mrow.addWidget(mlabel)
    mrow.addWidget(ui.comboBox_img_model, 1)
    lb.addLayout(mrow)
    l.addWidget(ui.img_local_box)

    ui.label_img_live = QtWidgets.QLabel("")
    ui.label_img_live.setWordWrap(True)
    ui.label_img_live.setVisible(False)
    l.addWidget(ui.label_img_live)
    ui.label_img_status = QtWidgets.QLabel("")
    ui.label_img_status.setWordWrap(True)
    ui.label_img_status.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(ui.label_img_status)
    ui.label_img_tip = QtWidgets.QLabel(tr("img_tip",
        "Tipp: Starte den Bild-Server auf dem anderen PC mit aktivierter API und Netzwerkzugriff (A1111 / Forge: --api --listen, ComfyUI: --listen) "
        "und gib den Port in der Firewall frei."))
    ui.label_img_tip.setWordWrap(True)
    ui.label_img_tip.setStyleSheet("color: #8D7AA3; font-size: 11px; border: none; background: transparent;")
    l.addWidget(ui.label_img_tip)
    layout.addWidget(ui.img_where_card)

    # ------------------------------------------------------------------ card 2: model + style
    card2, l2 = create_glass_card(tr("img_style_title", "Modell, Stil & Größe"))
    form2 = QtWidgets.QFormLayout()
    form2.setVerticalSpacing(12)
    ui.lineEdit_img_prefix = QtWidgets.QLineEdit()
    ui.lineEdit_img_prefix.setFixedHeight(40)
    ui.lineEdit_img_negative = QtWidgets.QLineEdit()
    ui.lineEdit_img_negative.setFixedHeight(40)
    ui.spin_img_width = QtWidgets.QSpinBox(); ui.spin_img_width.setRange(256, 2048); ui.spin_img_width.setSingleStep(64)
    ui.spin_img_height = QtWidgets.QSpinBox(); ui.spin_img_height.setRange(256, 2048); ui.spin_img_height.setSingleStep(64)
    ui.spin_img_steps = QtWidgets.QSpinBox(); ui.spin_img_steps.setRange(1, 150)
    for w in (ui.spin_img_width, ui.spin_img_height, ui.spin_img_steps):
        w.setFixedHeight(40)
    for text, widget in ((tr("img_prefix", "Stil-Präfix (immer vorangestellt)"), ui.lineEdit_img_prefix),
                         (tr("img_negative", "Negativ-Prompt"), ui.lineEdit_img_negative),
                         (tr("img_width", "Breite"), ui.spin_img_width), (tr("img_height", "Höhe"), ui.spin_img_height),
                         (tr("img_steps", "Schritte"), ui.spin_img_steps)):
        lab = QtWidgets.QLabel(text)
        lab.setFont(font_label)
        form2.addRow(lab, widget)
    l2.addLayout(form2)
    note = QtWidgets.QLabel(tr("img_gpu_note", "Die Grafikkarte(n) für die Bild-KI legst du im Bildserver selbst fest (z. B. Startoption --device-id bei A1111 oder "
                               "--cuda-device bei ComfyUI). Läuft er auf einem anderen PC, entlastet das automatisch deine GPU."))
    note.setWordWrap(True)
    note.setStyleSheet("color: #F6C177; border: none; background: transparent;")
    l2.addWidget(note)
    layout.addWidget(card2)

    # ------------------------------------------------------------------ card 3: test image
    card3, l3 = create_glass_card(tr("img_test_title", "Testbild"))
    trow = QtWidgets.QHBoxLayout()
    ui.pushButton_img_generate = QtWidgets.QPushButton(tr("img_test_btn", "Testbild erzeugen"))
    ui.pushButton_img_generate.setFixedHeight(40)
    ui.pushButton_img_generate.setStyleSheet(BTN)
    ui.pushButton_img_cancel = QtWidgets.QPushButton(tr("img_cancel_btn", "Abbrechen"))
    ui.pushButton_img_cancel.setFixedHeight(40)
    ui.pushButton_img_cancel.setStyleSheet(BTN)
    ui.pushButton_img_cancel.setEnabled(False)
    trow.addWidget(ui.pushButton_img_generate)
    trow.addWidget(ui.pushButton_img_cancel)
    trow.addStretch()
    l3.addLayout(trow)
    ui.label_img_preview = QtWidgets.QLabel("")
    ui.label_img_preview.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
    ui.label_img_preview.setMinimumHeight(120)
    ui.label_img_preview.setStyleSheet("border: 1px dashed rgba(255,143,199,0.3); border-radius: 12px; background: rgba(0,0,0,0.2); color: #B9A9C9;")
    l3.addWidget(ui.label_img_preview)
    layout.addWidget(card3)
    layout.addStretch()

    ui.image_settings_controller = ImageSettingsController(ui)
    return page


class ImageSettingsController(QtCore.QObject):
    _tested = QtCore.pyqtSignal(object)
    _scanned = QtCore.pyqtSignal(object)
    _generated = QtCore.pyqtSignal(object)

    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.tr = ui.translations.get
        self.signals = None
        self._loading = True
        self._worker_loop = None
        self._tested.connect(self._on_tested)
        self._scanned.connect(self._on_scanned)
        self._generated.connect(self._on_generated)
        ui.checkBox_img_enabled.toggled.connect(lambda v: self._set("image_gen_enabled", bool(v)))
        ui.comboBox_img_provider.currentTextChanged.connect(self._provider_changed)
        ui.rb_img_local.toggled.connect(self._target_changed)
        ui.lineEdit_img_address.editingFinished.connect(self._save_url)
        ui.spin_img_port.editingFinished.connect(self._save_url)
        ui.pushButton_img_test.clicked.connect(self.test)
        ui.pushButton_img_scan.clicked.connect(self.scan)
        ui.comboBox_img_found.activated.connect(self._pick_found)
        ui.comboBox_img_model.currentTextChanged.connect(lambda t: self._set("image_checkpoint", t.strip()))
        ui.lineEdit_img_prefix.editingFinished.connect(lambda: self._set("image_prefix_prompt", ui.lineEdit_img_prefix.text().strip()))
        ui.lineEdit_img_negative.editingFinished.connect(lambda: self._set("image_negative_prompt", ui.lineEdit_img_negative.text().strip()))
        ui.spin_img_width.valueChanged.connect(lambda v: self._set("image_width", int(v)))
        ui.spin_img_height.valueChanged.connect(lambda v: self._set("image_height", int(v)))
        ui.spin_img_steps.valueChanged.connect(lambda v: self._set("image_steps", int(v)))
        ui.lineEdit_img_key.editingFinished.connect(self._save_key)
        ui.pushButton_img_generate.clicked.connect(self.generate_test)
        ui.pushButton_img_cancel.clicked.connect(self.cancel)

    # ------------------------------------------------------------------ settings
    def _set(self, key, value):
        if not self._loading and self.signals is not None:
            self.signals.configuration_settings.update_main_setting(key, value)

    def _get(self, key, default=None):
        value = self.signals.configuration_settings.get_main_setting(key) if self.signals is not None else None
        return default if value is None or value == "" else value

    def attach(self, signals):
        self.signals = signals
        ui = self.ui
        self._loading = True
        ui.checkBox_img_enabled.setChecked(bool(self._get("image_gen_enabled", False)))
        provider = str(self._get("image_provider", "Automatic1111"))
        idx = ui.comboBox_img_provider.findText(provider)
        ui.comboBox_img_provider.setCurrentIndex(idx if idx >= 0 else 0)
        provider = ui.comboBox_img_provider.currentText()
        url = str(self._get("image_api_url", ""))
        host, port = "127.0.0.1", PROVIDER_PORT.get(provider, 7860)
        if url:
            u = urlparse(url if "://" in url else "http://" + url)
            host, port = u.hostname or host, u.port or port
        ui.lineEdit_img_address.setText("" if host in ("127.0.0.1", "localhost") else host)
        ui.spin_img_port.setValue(port)
        (ui.rb_img_local if host in ("127.0.0.1", "localhost") else ui.rb_img_net).setChecked(True)
        ui.comboBox_img_model.setEditText(str(self._get("image_checkpoint", "")))
        ui.lineEdit_img_prefix.setText(str(self._get("image_prefix_prompt", "masterpiece, best quality, very aesthetic, vivid colors, depth of field")))
        ui.lineEdit_img_negative.setText(str(self._get("image_negative_prompt", "worst quality, low quality, lowres, blurry, bad anatomy, bad hands, watermark, text")))
        ui.spin_img_width.setValue(int(self._get("image_width", 512)))
        ui.spin_img_height.setValue(int(self._get("image_height", 768)))
        ui.spin_img_steps.setValue(int(self._get("image_steps", 20)))
        self._loading = False
        ui.lineEdit_img_address.setVisible(ui.rb_img_net.isChecked())
        self._provider_changed(provider, initial=True)

    def _provider_changed(self, provider, initial=False):
        ui = self.ui
        local = provider in LOCAL_PROVIDERS
        ui.img_where_card.setVisible(local)
        ui.img_cloud_box.setVisible(not local)
        if local:
            if not initial and not self._loading:
                ui.spin_img_port.setValue(PROVIDER_PORT.get(provider, 7860))
        else:
            key = CLOUD_KEYS.get(provider)
            if key and self.signals is not None:
                ui.lineEdit_img_key.setEnabled(True)
                ui.lineEdit_img_key.setText(self.signals.configuration_api.get_token(key) or "")
                ui.lineEdit_img_key.setPlaceholderText(self.tr("img_key_ph", "API-Schlüssel für {p}").format(p=provider))
                ui.label_img_key_hint.setText("")
            else:                                                  # DALL-E uses the OpenAI key of the language-model settings
                ui.lineEdit_img_key.setEnabled(False)
                ui.lineEdit_img_key.clear()
                ui.lineEdit_img_key.setPlaceholderText(self.tr("img_dalle_key", "Nutzt den OpenAI-Schlüssel (Sprachmodell & APIs)"))
        if not initial:                                    # loading the page must not rewrite the saved settings
            self._set("image_provider", provider)
            if local:
                self._save_url()
        self._show_live(None)

    def _target_changed(self, local_checked):
        self.ui.lineEdit_img_address.setVisible(not local_checked)
        self.ui.pushButton_img_scan.setVisible(True)
        self._save_url()

    def _save_url(self):
        if self._loading or self.signals is None:
            return
        local = self.ui.rb_img_local.isChecked()
        host = "127.0.0.1" if local else (self.ui.lineEdit_img_address.text().strip() or "127.0.0.1")
        host = host.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0]
        url = f"http://{host}:{self.ui.spin_img_port.value()}"
        self.signals.configuration_settings.update_main_setting("image_api_url", url)
        return url

    def _save_key(self):
        provider = self.ui.comboBox_img_provider.currentText()
        key = CLOUD_KEYS.get(provider)
        if key and self.signals is not None:
            self.signals.configuration_api.save_api_token(key, self.ui.lineEdit_img_key.text().strip())

    # ------------------------------------------------------------------ status
    def _status(self, text, color="#B9A9C9"):
        self.ui.label_img_status.setText(text)
        self.ui.label_img_status.setStyleSheet(f"color: {color}; border: none; background: transparent;")

    def _show_live(self, state, text=""):
        lab = self.ui.label_img_live
        if state is None:
            lab.setVisible(False)
            return
        colors = {"online": ("#6EE7A0", "rgba(110,231,160,0.10)", "rgba(110,231,160,0.45)"),
                  "loading": ("#F6C177", "rgba(246,193,119,0.10)", "rgba(246,193,119,0.45)"),
                  "offline": ("#FF8FA3", "rgba(255,143,163,0.10)", "rgba(255,143,163,0.45)")}
        fg, bg, bd = colors[state]
        lab.setText(text)
        lab.setStyleSheet(f"color: {fg}; background: {bg}; border: 1px solid {bd}; border-radius: 10px; padding: 8px 12px; font-weight: 600;")
        lab.setVisible(True)

    # ------------------------------------------------------------------ test connection
    def test(self):
        provider = self.ui.comboBox_img_provider.currentText()
        url = self._save_url()
        if not url:
            return
        self._show_live("loading", self.tr("img_live_loading", "● Verbinde mit dem Bildserver ..."))
        self.ui.pushButton_img_test.setEnabled(False)
        threading.Thread(target=self._test_worker, args=(provider, url), daemon=True).start()

    def _test_worker(self, provider, base):
        try:
            if provider == "Automatic1111":
                r = requests.get(base + "/sdapi/v1/sd-models", timeout=8)
                r.raise_for_status()
                models = [m.get("title") or m.get("model_name") for m in r.json() if (m.get("title") or m.get("model_name"))]
                cur = ""
                try:
                    cur = requests.get(base + "/sdapi/v1/options", timeout=5).json().get("sd_model_checkpoint", "") or ""
                except Exception:
                    pass
                self._tested.emit({"ok": True, "models": models, "current": cur, "kind": "Automatic1111 / Forge"})
            else:
                r = requests.get(base + "/object_info/CheckpointLoaderSimple", timeout=8)
                r.raise_for_status()
                models = r.json()["CheckpointLoaderSimple"]["input"]["required"]["ckpt_name"][0]
                self._tested.emit({"ok": True, "models": list(models), "current": "", "kind": "ComfyUI"})
        except requests.exceptions.ConnectionError:
            self._tested.emit({"ok": False, "err": self.tr("img_fail_conn", "Keine Antwort von {url}. Läuft der Bildserver mit aktivierter API (A1111: --api, bei Netzwerkzugriff zusätzlich --listen)?").format(url=base)})
        except Exception as exc:
            self._tested.emit({"ok": False, "err": str(exc)})

    def _on_tested(self, res):
        ui = self.ui
        ui.pushButton_img_test.setEnabled(True)
        if not res.get("ok"):
            self._show_live("offline", "● " + res.get("err", "?"))
            return
        combo = ui.comboBox_img_model
        current = combo.currentText().strip() or res.get("current", "")
        self._loading = True
        combo.clear()
        combo.addItems(res["models"])
        combo.setEditText(current if current in res["models"] else (res.get("current") or (res["models"][0] if res["models"] else current)))
        self._loading = False
        self._set("image_checkpoint", combo.currentText().strip())
        self._show_live("online", self.tr("img_live_online", "● Bild-KI erreichbar ({kind}) – Modell: {model}").format(
            kind=res.get("kind", ""), model=combo.currentText() or "?"))

    # ------------------------------------------------------------------ network search
    def scan(self):
        self.ui.pushButton_img_scan.setEnabled(False)
        self._status(self.tr("img_scanning", "Suche im Netzwerk nach Bild-Servern (A1111, Forge, ComfyUI) ... (ca. 10 Sekunden)"))
        if self.signals is not None:
            try:
                from app.gui.custom_widgets import sow_toast
                sow_toast(parent=self.signals.main_window, title=self.tr("netllm_scan_toast_title", "Netzwerksuche"),
                          text=self.tr("img_scan_toast", "Suche nach Bild-Servern im lokalen Netzwerk ..."), msg_type="info")
            except Exception:
                logger.debug("toast failed", exc_info=True)
        threading.Thread(target=lambda: self._scanned.emit(scan_image_servers()), daemon=True).start()

    def _on_scanned(self, found):
        ui = self.ui
        ui.pushButton_img_scan.setEnabled(True)
        ui.comboBox_img_found.clear()
        for f in found:
            ui.comboBox_img_found.addItem(f"{f['host']}:{f['port']}  -  {f['kind']}", f)
        ui.comboBox_img_found.setVisible(bool(found))
        if found:
            self._status(self.tr("img_found", "{n} Server gefunden – einen auswählen, dann „Verbindung testen“.").format(n=len(found)), "#6EE7A0")
            self._pick_found(0)
        else:
            self._status(self.tr("img_none", "Kein Bild-Server gefunden. Starte A1111/Forge mit --api --listen (ComfyUI mit --listen) oder trage die IP von Hand ein."), "#F6C177")

    def _pick_found(self, index):
        f = self.ui.comboBox_img_found.itemData(index)
        if not f:
            return
        self._loading = True
        self.ui.comboBox_img_provider.setCurrentText(f["provider"])
        if f["host"] in ("127.0.0.1", "localhost"):
            self.ui.rb_img_local.setChecked(True)
        else:
            self.ui.rb_img_net.setChecked(True)
            self.ui.lineEdit_img_address.setText(f["host"])
        self.ui.spin_img_port.setValue(f["port"])
        self._loading = False
        self._provider_changed(f["provider"], initial=True)
        self._save_url()
        self.test()

    # ------------------------------------------------------------------ test image
    def generate_test(self):
        if self.signals is None:
            return
        ui = self.ui
        ui.pushButton_img_generate.setEnabled(False)
        ui.pushButton_img_cancel.setEnabled(True)
        ui.label_img_preview.setPixmap(QtGui.QPixmap())
        ui.label_img_preview.setText(self.tr("img_generating", "🖼 Bild wird erzeugt ..."))
        threading.Thread(target=self._generate_worker, daemon=True).start()

    def _generate_worker(self):
        import asyncio
        from app.utils.image_generator import ImageGenerator
        loop = asyncio.new_event_loop()
        self._worker_loop = loop
        try:
            path = loop.run_until_complete(ImageGenerator().generate_image(
                "1girl, anime style, smiling, cherry blossoms, soft light", "_test"))
            self._generated.emit({"path": path})
        except BaseException as exc:                              # includes cancellation
            self._generated.emit({"path": None, "err": str(exc)})
        finally:
            self._worker_loop = None
            loop.close()

    def cancel(self):
        try:
            from app.utils.image_generator import cancel_all
            cancel_all()
        except Exception:
            logger.debug("cancel failed", exc_info=True)

    def _on_generated(self, res):
        ui = self.ui
        ui.pushButton_img_generate.setEnabled(True)
        ui.pushButton_img_cancel.setEnabled(False)
        path = res.get("path")
        if path:
            full = os.path.join(os.getcwd(), "app", "data", ".soul", "_test", path)
            pix = QtGui.QPixmap(full)
            if not pix.isNull():
                ui.label_img_preview.setPixmap(pix.scaledToHeight(320, QtCore.Qt.TransformationMode.SmoothTransformation))
                return
        ui.label_img_preview.setText(self.tr("img_test_failed", "⚠ Kein Bild erhalten (abgebrochen oder Server nicht erreichbar)."))
