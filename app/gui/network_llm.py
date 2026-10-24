"""'Where does the language model run?' - the simple way to use a llama.cpp / Ollama server on another PC.

Pick "another PC in the network", type its IP address (or press Search), press Test. Everything else - base URL, model
name, switching the route - is filled in automatically.
"""
from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import requests
from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("NetworkLLM")

DEFAULT_PORT = 8080
SCAN_PORTS = (8080, 11434, 8000, 1234)   # llama.cpp, Ollama, vLLM/others, LM Studio

TILE = ("QPushButton { background: rgba(255,143,199,0.05); border: 1px solid rgba(255,143,199,0.22); border-radius: 12px; "
        "padding: 14px 18px; color: #F1E8F6; font-size: 13px; text-align: left; } "
        "QPushButton:checked { background: rgba(255,143,199,0.18); border: 2px solid rgba(255,143,199,0.8); } "
        "QPushButton:hover { background: rgba(255,143,199,0.10); }")
BTN = ("QPushButton { background: rgba(255,143,199,0.15); color:#F6EAF6; border:1px solid rgba(255,143,199,0.5); "
       "border-radius:9px; padding: 4px 16px; font-weight: 600; } QPushButton:hover { background: rgba(255,143,199,0.3); } "
       "QPushButton:disabled { color: rgba(246,234,246,0.35); border-color: rgba(255,143,199,0.15); }")
FIELD = ("QLineEdit, QComboBox { background: rgba(14,9,22,0.55); color: #F1E8F6; border: 1px solid rgba(255,143,199,0.28); "
         "border-radius: 9px; padding: 6px 10px; } QLineEdit:focus, QComboBox:focus { border-color: rgba(255,143,199,0.75); }")


def normalize_endpoint(text: str, default_port: int = DEFAULT_PORT) -> tuple[str, str]:
    """'192.168.1.50' | '192.168.1.50:8080' | 'http://host:11434' | 'http://host:8080/v1' -> (host, base_url)."""
    raw = (text or "").strip()
    if not raw:
        return "", ""
    if "://" not in raw:
        raw = "http://" + raw
    u = urlparse(raw)
    host = u.hostname or ""
    if not host:
        return "", ""
    port = u.port or default_port
    path = (u.path or "").rstrip("/")
    if not path.endswith("/v1"):
        path = (path + "/v1") if path in ("", "/") else path
    host_part = f"[{host}]" if ":" in host else host
    return host, f"{u.scheme}://{host_part}:{port}{path}"


def local_ip() -> str:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return ""


def probe(host: str, port: int, timeout: float = 0.6) -> dict | None:
    """Is an OpenAI-compatible LLM server answering on host:port? Returns {'host','port','kind'} or None."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            pass
    except OSError:
        return None
    base = f"http://{host}:{port}"
    for path, kind in (("/health", "llama.cpp"), ("/v1/models", "OpenAI-kompatibel"), ("/api/tags", "Ollama")):
        try:
            r = requests.get(base + path, timeout=1.5)
            if r.status_code == 200:
                if path == "/health" and "ok" not in r.text.lower():
                    continue
                return {"host": host, "port": port, "kind": "Ollama" if port == 11434 or path == "/api/tags" else kind}
        except requests.RequestException:
            continue
    return None


def _scan_targets(include_self: bool) -> list[str]:
    """Every host of the /24 networks of the real LAN adapters (VPN / VMware / Hyper-V adapters are skipped)."""
    own = set()
    try:
        from app.utils import mobile_devices
        own = mobile_devices.own_ip_addresses()
        ips = mobile_devices.lan_addresses()
    except Exception:
        ips = []
    if not ips and local_ip():
        ips = [local_ip()]
    hosts: list[str] = []
    for ip in ips:
        try:
            net = ipaddress.ip_network(ip + "/24", strict=False)
        except ValueError:
            continue
        hosts += [str(h) for h in net.hosts() if str(h) not in own]
    if include_self:
        hosts.append("127.0.0.1")
    return list(dict.fromkeys(hosts))


def scan_network(progress=None, include_self: bool = True) -> list[dict]:
    hosts = _scan_targets(include_self)
    if not hosts:
        return []
    jobs = [(h, p) for h in hosts for p in SCAN_PORTS]
    found = []
    with ThreadPoolExecutor(max_workers=96) as pool:
        for i, res in enumerate(pool.map(lambda hp: probe(*hp), jobs)):
            if res:
                found.append(res)
            if progress and i % 40 == 0:
                progress(int(100 * i / len(jobs)))
    return found


def describe_server(f: dict) -> dict:
    """Adds the host name and the first model name of a found server (best effort, runs in a worker thread)."""
    out = dict(f)
    base = f"http://{f['host']}:{f['port']}"
    try:
        out["hostname"] = socket.gethostbyaddr(f["host"])[0].split(".")[0]
    except Exception:
        out["hostname"] = ""
    try:
        if f.get("kind") == "Ollama":
            data = requests.get(base + "/api/tags", timeout=2).json()
            names = [m.get("name") or m.get("model") for m in data.get("models", [])]
        else:
            data = requests.get(base + "/v1/models", timeout=2).json()
            names = [m.get("id") for m in data.get("data", [])]
        out["model"] = next((n for n in names if n), "")
    except Exception:
        out["model"] = ""
    return out


def build_network_llm_card(ui, create_glass_card, font_input):
    tr = ui.translations.get
    card, l = create_glass_card(tr("netllm_title", "Where does the language model run?"))
    ui.rb_llm_local = QtWidgets.QPushButton(tr("netllm_this_pc", "💻  On this PC\nYume starts llama.cpp itself."))
    ui.rb_llm_net = QtWidgets.QPushButton(tr("netllm_other_pc", "🌐  On another PC in my network\nllama.cpp or Ollama runs there."))
    for rb in (ui.rb_llm_local, ui.rb_llm_net):
        rb.setStyleSheet(TILE)
        rb.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        rb.setMinimumHeight(64)
        rb.setCheckable(True)
        rb.setAutoExclusive(True)
        rb.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    ui.rb_llm_local.setChecked(True)
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(14)
    row.addWidget(ui.rb_llm_local, 1)
    row.addWidget(ui.rb_llm_net, 1)
    l.addLayout(row)
    from app.gui.server_installer import build_installer_row
    l.addWidget(build_installer_row(ui))

    arow = QtWidgets.QHBoxLayout()
    ui.checkBox_netllm_autoscan = QtWidgets.QCheckBox(tr("netllm_auto_check", "Netzwerk automatisch nach LLM-Servern durchsuchen (beim Start und regelmäßig) und Bescheid geben"))
    ui.checkBox_netllm_autoscan.setFont(font_input)
    ui.checkBox_netllm_autoscan.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    ui.spin_netllm_autoscan = QtWidgets.QSpinBox()
    ui.spin_netllm_autoscan.setRange(1, 240)
    ui.spin_netllm_autoscan.setValue(5)
    ui.spin_netllm_autoscan.setSuffix(" " + tr("netllm_auto_minutes", "Min"))
    ui.spin_netllm_autoscan.setPrefix(tr("netllm_auto_every", "alle") + " ")
    ui.spin_netllm_autoscan.setFixedWidth(130)
    ui.spin_netllm_autoscan.setStyleSheet(FIELD)
    arow.addWidget(ui.checkBox_netllm_autoscan, 1)
    arow.addWidget(ui.spin_netllm_autoscan)
    l.addLayout(arow)

    ui.netllm_box = QtWidgets.QWidget()
    nb = QtWidgets.QVBoxLayout(ui.netllm_box)
    nb.setContentsMargins(0, 8, 0, 0)
    nb.setSpacing(10)
    addr = QtWidgets.QHBoxLayout()
    ui.lineEdit_netllm_address = QtWidgets.QLineEdit()
    ui.lineEdit_netllm_address.setPlaceholderText(tr("netllm_placeholder", "IP address of the other PC, e.g. 192.168.1.50"))
    ui.lineEdit_netllm_address.setFixedHeight(40)
    ui.lineEdit_netllm_address.setStyleSheet(FIELD)
    ui.lineEdit_netllm_address.setFont(font_input)
    ui.spin_netllm_port = QtWidgets.QSpinBox()
    ui.spin_netllm_port.setRange(1, 65535)
    ui.spin_netllm_port.setValue(DEFAULT_PORT)
    ui.spin_netllm_port.setPrefix(tr("netllm_port", "Port") + " ")
    ui.spin_netllm_port.setFixedHeight(40)
    ui.spin_netllm_port.setFixedWidth(130)
    ui.spin_netllm_port.setStyleSheet(FIELD)
    ui.pushButton_netllm_test = QtWidgets.QPushButton(tr("netllm_test", "Test connection"))
    ui.pushButton_netllm_test.setFixedHeight(40)
    ui.pushButton_netllm_test.setStyleSheet(BTN)
    addr.addWidget(ui.lineEdit_netllm_address, 1)
    addr.addWidget(ui.spin_netllm_port)
    addr.addWidget(ui.pushButton_netllm_test)
    nb.addLayout(addr)

    srow = QtWidgets.QHBoxLayout()
    ui.pushButton_netllm_scan = QtWidgets.QPushButton(tr("netllm_scan", "🔍  Search the network automatically"))
    ui.pushButton_netllm_scan.setFixedHeight(36)
    ui.pushButton_netllm_scan.setStyleSheet(BTN)
    ui.comboBox_netllm_found = QtWidgets.QComboBox()
    ui.comboBox_netllm_found.setFixedHeight(36)
    ui.comboBox_netllm_found.setStyleSheet(FIELD)
    ui.comboBox_netllm_found.setVisible(False)
    srow.addWidget(ui.pushButton_netllm_scan)
    srow.addWidget(ui.comboBox_netllm_found, 1)
    nb.addLayout(srow)

    mrow = QtWidgets.QHBoxLayout()
    mlabel = QtWidgets.QLabel(tr("netllm_model", "Model on the server"))
    mlabel.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    ui.comboBox_netllm_model = QtWidgets.QComboBox()
    ui.comboBox_netllm_model.setEditable(True)
    ui.comboBox_netllm_model.setFixedHeight(36)
    ui.comboBox_netllm_model.setStyleSheet(FIELD)
    ui.comboBox_netllm_model.lineEdit().setPlaceholderText(tr("netllm_model_auto", "detected automatically after the test"))
    ui.lineEdit_netllm_key = QtWidgets.QLineEdit()
    ui.lineEdit_netllm_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
    ui.lineEdit_netllm_key.setPlaceholderText(tr("netllm_key", "Access key (only if the server needs one)"))
    ui.lineEdit_netllm_key.setFixedHeight(36)
    ui.lineEdit_netllm_key.setStyleSheet(FIELD)
    for combo in (ui.comboBox_netllm_model, ui.comboBox_netllm_found):      # long model ids must not widen the page
        combo.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        combo.setMinimumContentsLength(12)
    for rb in (ui.rb_llm_local, ui.rb_llm_net):
        rb.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
    mrow.addWidget(mlabel)
    mrow.addWidget(ui.comboBox_netllm_model, 1)
    nb.addLayout(mrow)
    nb.addWidget(ui.lineEdit_netllm_key)
    l.addWidget(ui.netllm_box)

    ui.label_netllm_live = QtWidgets.QLabel("")
    ui.label_netllm_live.setWordWrap(True)
    ui.label_netllm_live.setVisible(False)
    l.addWidget(ui.label_netllm_live)
    ui.label_netllm_status = QtWidgets.QLabel("")
    ui.label_netllm_status.setWordWrap(True)
    ui.label_netllm_status.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(ui.label_netllm_status)
    hint = QtWidgets.QLabel(tr(
        "netllm_hint",
        "Tip: start the server on the other PC with  llama-server -m model.gguf --host 0.0.0.0 --port 8080  "
        "(without --host 0.0.0.0 it only listens on that PC itself). Allow the port in the firewall of that PC."))
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #8D7AA3; font-size: 11px; border: none; background: transparent;")
    l.addWidget(hint)
    ui.netllm_box.setVisible(False)
    ui.network_llm_controller = NetworkLLMController(ui)
    return card


class NetworkLLMController(QtCore.QObject):
    _remote_state = QtCore.pyqtSignal(int, str, str)       # seq, state, model  (emitted from a worker thread)

    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.tr = ui.translations.get
        self.signals = None
        self._loading = True
        self._remote_state.connect(self._apply_remote_state)
        ui.rb_llm_local.toggled.connect(self._mode_changed)
        ui.pushButton_netllm_test.clicked.connect(self.test)
        ui.pushButton_netllm_scan.clicked.connect(self.scan)
        ui.checkBox_netllm_autoscan.toggled.connect(self._autoscan_toggled)
        ui.spin_netllm_autoscan.editingFinished.connect(self._autoscan_minutes_changed)
        self._known: set[str] = set()
        self._autoscan_task = None
        ui.comboBox_netllm_found.activated.connect(self._pick_found)
        ui.lineEdit_netllm_address.editingFinished.connect(self._address_edited)
        ui.spin_netllm_port.editingFinished.connect(self._address_edited)
        ui.comboBox_netllm_model.currentTextChanged.connect(self._model_edited)
        ui.comboBox_netllm_model.activated.connect(lambda _i: self.refresh_remote_status())
        ui.lineEdit_netllm_key.editingFinished.connect(self._key_edited)
        if hasattr(ui, "comboBox_service_llm_route"):
            ui.comboBox_service_llm_route.currentIndexChanged.connect(self._service_route_changed)

    # ------------------------------------------------------------------ state
    def attach(self, signals):
        self.signals = signals
        ui = self.ui
        self._loading = True
        route = signals.configuration_settings.get_main_setting("local_llm_route") or "local"
        base = (signals.configuration_api.get_token("REMOTE_LLM_BASE_URL") or "").strip()
        if base:
            u = urlparse(base if "://" in base else "http://" + base)
            ui.lineEdit_netllm_address.setText(u.hostname or "")
            ui.spin_netllm_port.setValue(u.port or DEFAULT_PORT)
        ui.comboBox_netllm_model.setEditText(signals.configuration_settings.get_main_setting("remote_llm_model") or "")
        ui.lineEdit_netllm_key.setText(signals.configuration_api.get_token("REMOTE_LLM_API_TOKEN") or "")
        (ui.rb_llm_net if route == "remote" else ui.rb_llm_local).setChecked(True)
        ui.netllm_box.setVisible(route == "remote")
        cfg = signals.configuration_settings
        auto = cfg.get_main_setting("netllm_autoscan")
        ui.checkBox_netllm_autoscan.setChecked(True if auto is None else bool(auto))
        ui.spin_netllm_autoscan.setValue(int(cfg.get_main_setting("netllm_autoscan_minutes") or 5))
        self._loading = False
        self._autoscan_restart()
        self._lock_service_route(route == "remote")
        if route == "remote" and base:
            QtCore.QTimer.singleShot(1500, self.refresh_remote_status)
        if route == "remote" and base:
            self._status(self.tr("netllm_saved", "Saved: {url}").format(url=base))


    # ------------------------------------------------------------------ automatic search
    def _autoscan_toggled(self, on):
        if self._loading or self.signals is None:
            return
        self.signals.configuration_settings.update_main_setting("netllm_autoscan", bool(on))
        self._autoscan_restart()

    def _autoscan_minutes_changed(self):
        if self._loading or self.signals is None:
            return
        self.signals.configuration_settings.update_main_setting("netllm_autoscan_minutes", int(self.ui.spin_netllm_autoscan.value()))
        self._autoscan_restart()

    def _autoscan_restart(self):
        if self._autoscan_task is not None:
            self._autoscan_task.cancel()
            self._autoscan_task = None
        if self.ui.checkBox_netllm_autoscan.isChecked():
            self._autoscan_task = asyncio.ensure_future(self._autoscan_loop())

    async def _autoscan_loop(self):
        """Searches the network shortly after the start and then every few minutes; reports servers that appeared."""
        try:
            await asyncio.sleep(25)                       # let the program finish starting first
            while True:
                try:
                    found = await asyncio.to_thread(lambda: [describe_server(f) for f in scan_network(include_self=False)])
                    self._autoscan_report(found)
                except asyncio.CancelledError:
                    raise
                except Exception:
                    logger.exception("automatic network search failed")
                await asyncio.sleep(max(1, int(self.ui.spin_netllm_autoscan.value())) * 60)
        except asyncio.CancelledError:
            pass

    def _autoscan_report(self, found):
        keys = {f"{f['host']}:{f['port']}" for f in found}
        new = [f for f in found if f"{f['host']}:{f['port']}" not in self._known]
        self._known = keys                                  # servers that vanished are announced again when they come back
        if not found:
            return
        combo = self.ui.comboBox_netllm_found
        combo.clear()
        for f in found:
            combo.addItem(f"{f['host']}:{f['port']}  -  {f['kind']}", f)
        combo.setVisible(True)
        if not new or self.signals is None:
            return
        lines = []
        for f in new[:4]:
            name = f" ({f['hostname']})" if f.get("hostname") else ""
            model = f"  –  {f['model']}" if f.get("model") else ""
            lines.append(f"{f['host']}:{f['port']}{name}  –  {f['kind']}{model}")
        if len(new) > 4:
            lines.append(self.tr("netllm_auto_more", "… und {n} weitere").format(n=len(new) - 4))
        title = self.tr("netllm_auto_found_title", "LLM-Server im Netzwerk gefunden")
        hint = self.tr("netllm_auto_found_hint", "Auswählen unter Sprachmodell → „Anderer PC“.")
        logger.info("LLM server(s) found: %s", "; ".join(lines))
        try:
            from app.gui.custom_widgets import sow_toast
            sow_toast(parent=self.signals.main_window, title=title, text="\n".join(lines) + "\n" + hint, msg_type="success", duration=12000)
        except Exception:
            logger.exception("toast failed")

    def _status(self, text, color="#B9A9C9"):
        self.ui.label_netllm_status.setText(text)
        self.ui.label_netllm_status.setStyleSheet(f"color: {color}; border: none; background: transparent;")

    def _mode_changed(self, local_checked):
        self.ui.netllm_box.setVisible(not local_checked)
        if self._loading or self.signals is None:
            return
        route = "local" if local_checked else "remote"
        self._lock_service_route(route == "remote", announce=True)
        QtCore.QTimer.singleShot(300, self.refresh_remote_status)
        combo = getattr(self.ui, "comboBox_local_llm_route", None)
        if combo is not None:
            idx = combo.findData(route)
            if idx >= 0 and combo.currentIndex() != idx:
                combo.setCurrentIndex(idx)          # existing handler stores the route and stops/starts local llama.cpp
                return
        self.signals.configuration_settings.update_main_setting("local_llm_route", route)

    def _service_route_changed(self, _index):
        """The AI-services page changed the target (only possible while unlocked): mirror it in the card."""
        if self._loading or self.signals is None:
            return
        route = self.ui.comboBox_service_llm_route.currentData() or "local"
        self._loading = True
        (self.ui.rb_llm_net if route == "remote" else self.ui.rb_llm_local).setChecked(True)
        self.ui.netllm_box.setVisible(route == "remote")
        self._loading = False
        self._lock_service_route(route == "remote", announce=True)

    def _lock_service_route(self, remote: bool, announce: bool = False):
        """Remote PC active -> AI services shows 'Entfernter PC' and cannot be changed; characters follow automatically."""
        ui = self.ui
        combo = getattr(ui, "comboBox_service_llm_route", None)
        hint = getattr(ui, "label_service_route_hint", None)
        if combo is not None:
            combo.blockSignals(True)
            idx = combo.findData("remote" if remote else "local")
            if idx >= 0:
                combo.setCurrentIndex(idx)
            combo.blockSignals(False)
            combo.setEnabled(not remote)
        n = 0
        if remote and self.signals is not None:
            try:
                chars = self.signals.configuration_characters.load_configuration().get("character_list", {}) or {}
                n = sum(1 for c in chars.values() if (c.get("conversation_method") or "Local LLM") in ("Local LLM", "Remote LLM"))
            except Exception:
                n = 0
        if remote:
            text = self.tr("netllm_locked_hint",
                           "Entfernter PC aktiv: Das Ausführungsziel ist gesperrt. Alle Charaktere mit lokalem LLM ({n}) nutzen automatisch das LLM auf dem entfernten PC. "
                           "Zum Ändern im Netzwerk-Bereich oben auf 'Dieser PC' wechseln.").format(n=n)
            if combo is not None:
                combo.setToolTip(text)
        else:
            text = ""
            if combo is not None:
                combo.setToolTip("")
        if hint is not None:
            hint.setText(text)
            hint.setVisible(bool(text))
        if announce and self.signals is not None:
            from app.gui.custom_widgets import sow_toast
            try:
                sow_toast(parent=self.signals.main_window,
                          title=self.tr("netllm_remote_on_title", "Entfernter PC aktiv") if remote else self.tr("netllm_remote_off_title", "Dieser PC aktiv"),
                          text=(self.tr("netllm_remote_on_toast", "Alle Charaktere mit lokalem LLM ({n}) wurden automatisch auf den entfernten PC umgestellt. Das Ausführungsziel ist gesperrt.").format(n=n)
                                if remote else self.tr("netllm_remote_off_toast", "Charaktere nutzen wieder das lokale llama.cpp auf diesem PC.")),
                          msg_type="info")
            except Exception:
                logger.exception("toast failed")

    def _save_endpoint(self) -> str:
        host, base = normalize_endpoint(self.ui.lineEdit_netllm_address.text(), self.ui.spin_netllm_port.value())
        if not base or self.signals is None:
            return ""
        parsed = urlparse(base)
        if parsed.port:
            self.ui.spin_netllm_port.blockSignals(True)
            self.ui.spin_netllm_port.setValue(parsed.port)
            self.ui.spin_netllm_port.blockSignals(False)
        self.ui.lineEdit_netllm_address.setText(host)
        self.signals.configuration_api.save_api_token("REMOTE_LLM_BASE_URL", base)
        return base

    def _address_edited(self):
        if not self._loading:
            self._save_endpoint()

    def _model_edited(self, text):
        if not self._loading and self.signals is not None:
            self.signals.configuration_settings.update_main_setting("remote_llm_model", text.strip())

    def _key_edited(self):
        if not self._loading and self.signals is not None:
            self.signals.configuration_api.save_api_token("REMOTE_LLM_API_TOKEN", self.ui.lineEdit_netllm_key.text().strip())

    # ------------------------------------------------------------------ status / model loading
    def refresh_remote_status(self):
        """Top-left status: show the remote model and make the server load it (Ollama loads on first request)."""
        widget = getattr(self.ui, "connection_status_widget", None)
        if widget is None or self.signals is None:
            return
        if (self.signals.configuration_settings.get_main_setting("local_llm_route") or "local") != "remote":
            widget.clear_remote()
            self._show_live(None)
            return
        base = (self.signals.configuration_api.get_token("REMOTE_LLM_BASE_URL") or "").strip()
        if not base:
            widget.clear_remote()
            self._show_live(None)
            return
        model = (self.signals.configuration_settings.get_main_setting("remote_llm_model") or "").strip()
        widget.set_remote("loading", model or "...")
        self._show_live("loading", model or "...")
        self._load_seq = getattr(self, "_load_seq", 0) + 1
        key = (self.signals.configuration_api.get_token("REMOTE_LLM_API_TOKEN") or "").strip()
        threading.Thread(target=self._load_remote_worker, args=(base, model, key, self._load_seq), daemon=True).start()

    def _load_remote_worker(self, base, model, key, seq):
        headers = {"Authorization": f"Bearer {key}"} if key else {}

        def work():
            url = base.rstrip("/")
            name = model
            if not name:
                r = requests.get(url + "/models", headers=headers, timeout=6)
                r.raise_for_status()
                data = r.json()
                ids = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
                name = ids[0] if ids else ""
            # one-token request: makes Ollama / router-mode llama.cpp actually load the selected model
            r = requests.post(url + "/chat/completions", headers=headers, timeout=180,
                              json={"model": name, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1, "stream": False})
            r.raise_for_status()
            return name
        try:
            self._remote_state.emit(seq, "online", work())
        except Exception as exc:
            logger.warning("remote model load failed: %s", exc)
            self._remote_state.emit(seq, "offline", "")

    def _show_live(self, state, model=""):
        """Persistent coloured state line inside the card: green = remote model loaded."""
        lab = self.ui.label_netllm_live
        if state is None:
            lab.setVisible(False)
            return
        colors = {"online": ("#6EE7A0", "rgba(110,231,160,0.10)", "rgba(110,231,160,0.45)"),
                  "loading": ("#F6C177", "rgba(246,193,119,0.10)", "rgba(246,193,119,0.45)"),
                  "offline": ("#FF8FA3", "rgba(255,143,163,0.10)", "rgba(255,143,163,0.45)")}
        fg, bg, bd = colors[state]
        text = {"online": self.tr("netllm_live_online", "● Remote-Modell geladen und bereit: {model}"),
                "loading": self.tr("netllm_live_loading", "● Remote-Modell wird geladen: {model}"),
                "offline": self.tr("netllm_live_offline", "● Remote-Server nicht erreichbar - läuft llama-server dort mit --host 0.0.0.0?")}[state]
        lab.setText(text.format(model=model or "?"))
        lab.setStyleSheet(f"color: {fg}; background: {bg}; border: 1px solid {bd}; border-radius: 10px; padding: 8px 12px; font-weight: 600;")
        lab.setVisible(True)

    def _apply_remote_state(self, seq, state, model):
        if seq != getattr(self, "_load_seq", 0):
            return                                  # a newer request superseded this one
        self._show_live(state, model)
        widget = getattr(self.ui, "connection_status_widget", None)
        if widget is not None and (self.signals.configuration_settings.get_main_setting("local_llm_route") or "local") == "remote":
            widget.set_remote(state, model)

    # ------------------------------------------------------------------ test
    def test(self):
        base = self._save_endpoint()
        if not base:
            self._status(self.tr("netllm_enter_ip", "Please enter the IP address of the other PC first."), "#F6C177")
            return
        self._key_edited()
        self._status(self.tr("netllm_testing", "Testing {url} ...").format(url=base))
        self.ui.pushButton_netllm_test.setEnabled(False)
        asyncio.ensure_future(self._test_async(base))

    async def _test_async(self, base):
        key = self.ui.lineEdit_netllm_key.text().strip()

        def work():
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            r = requests.get(base.rstrip("/") + "/models", headers=headers, timeout=6)
            r.raise_for_status()
            data = r.json()
            ids = [m.get("id") for m in (data.get("data") or []) if m.get("id")]
            if not ids and data.get("models"):
                ids = [m.get("name") or m.get("model") for m in data["models"] if (m.get("name") or m.get("model"))]
            return ids
        try:
            ids = await asyncio.to_thread(work)
            combo = self.ui.comboBox_netllm_model
            current = combo.currentText().strip()
            self._loading = True
            combo.clear()
            combo.addItems(ids)
            combo.setEditText(current if current in ids else (ids[0] if ids else current))
            self._loading = False
            self._model_edited(combo.currentText())
            self._status(self.tr("netllm_ok", "✓ Connected. Model: {model}").format(model=combo.currentText() or "?"), "#6EE7A0")
            if not self.ui.rb_llm_net.isChecked():
                self.ui.rb_llm_net.setChecked(True)
            else:
                self.refresh_remote_status()
        except requests.exceptions.ConnectionError:
            self._status(self.tr("netllm_fail_conn",
                                 "No answer from {url}. Is the server running with --host 0.0.0.0, and is the port allowed in the firewall?").format(url=base), "#FF8FA3")
        except requests.exceptions.Timeout:
            self._status(self.tr("netllm_fail_timeout", "The server did not answer in time."), "#FF8FA3")
        except Exception as exc:
            self._status(self.tr("netllm_fail", "Connection failed: {err}").format(err=exc), "#FF8FA3")
        finally:
            self.ui.pushButton_netllm_test.setEnabled(True)

    # ------------------------------------------------------------------ search
    def scan(self):
        self.ui.pushButton_netllm_scan.setEnabled(False)
        if self.signals is not None:
            from app.gui.custom_widgets import sow_toast
            try:
                sow_toast(parent=self.signals.main_window, title=self.tr("netllm_scan_toast_title", "Netzwerksuche"),
                          text=self.tr("netllm_scan_toast", "Suche nach llama.cpp / Ollama im lokalen Netzwerk ... (ca. 10 Sekunden)"), msg_type="info")
            except Exception:
                logger.exception("toast failed")
        self._status(self.tr("netllm_scanning", "Searching your network for llama.cpp / Ollama servers ... (about 10 seconds)"))
        asyncio.ensure_future(self._scan_async())

    async def _scan_async(self):
        try:
            found = await asyncio.to_thread(scan_network)
        except Exception as exc:
            logger.exception("network scan failed")
            self._status(str(exc), "#FF8FA3")
            self.ui.pushButton_netllm_scan.setEnabled(True)
            return
        combo = self.ui.comboBox_netllm_found
        combo.clear()
        for f in found:
            combo.addItem(f"{f['host']}:{f['port']}  -  {f['kind']}", f)
        combo.setVisible(bool(found))
        self.ui.pushButton_netllm_scan.setEnabled(True)
        if found:
            self._status(self.tr("netllm_found", "{n} server(s) found - pick one from the list, then press Test.").format(n=len(found)), "#6EE7A0")
            self._pick_found(0)
        else:
            self._status(self.tr("netllm_none", "No server found. Start llama-server on the other PC with --host 0.0.0.0 or type the IP address manually."), "#F6C177")

    def _pick_found(self, index):
        f = self.ui.comboBox_netllm_found.itemData(index)
        if not f:
            return
        self.ui.lineEdit_netllm_address.setText(f["host"])
        self.ui.spin_netllm_port.setValue(f["port"])
        self._save_endpoint()
        self.test()
