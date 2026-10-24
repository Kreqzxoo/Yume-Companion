"""Tools page: recommended local models for tool calling, browser agent, code execution and screen/GUI control.

Chat tools are driven by the selected chat model (it must support function calling). This card lists verified GGUF
models that do, with a one-click download into the models folder. Screen/GUI control additionally needs the Vision AI
(which reads the screen) - the card links to that page.
"""
from __future__ import annotations

import logging
import os
import time
from pathlib import Path

import requests
from PyQt6 import QtCore, QtGui, QtWidgets

from app.configuration import configuration

logger = logging.getLogger("AgentModels")
HF = "https://huggingface.co"
SUBFOLDER = "tool-models"

# Verified repositories / file names (checked against the Hugging Face API).
AGENT_MODELS = [
    {
        "id": "qwen3-4b", "name": "Qwen3 4B", "repo": "Qwen/Qwen3-4B-GGUF", "file": "Qwen3-4B-Q4_K_M.gguf",
        "size_gb": 2.5, "min_vram_gb": 4,
        "tag": "Werkzeuge · schnell",
        "uses": ["Websuche", "Systemwerkzeuge", "einfache Browser-Aufgaben"], "level": "Einsteiger · wenig Grafikspeicher",
        "desc": "Kleines, schnelles Modell mit zuverlässigem Werkzeug-Aufruf.",
    },
    {
        "id": "qwen3-8b", "name": "Qwen3 8B (empfohlen)", "repo": "Qwen/Qwen3-8B-GGUF", "file": "Qwen3-8B-Q4_K_M.gguf",
        "size_gb": 5.0, "min_vram_gb": 8,
        "tag": "Werkzeuge · Browser-Agent", "recommended": True,
        "uses": ["Browser-Agent", "Dateiverwaltung", "mehrstufige Aufgaben"], "level": "Empfohlen · bester Kompromiss",
        "desc": "Bester Kompromiss aus Qualität und Geschwindigkeit für Agenten-Aufgaben.",
    },
    {
        "id": "qwen3-14b", "name": "Qwen3 14B", "repo": "Qwen/Qwen3-14B-GGUF", "file": "Qwen3-14B-Q4_K_M.gguf",
        "size_gb": 9.0, "min_vram_gb": 12,
        "tag": "Werkzeuge · Planung",
        "uses": ["lange Pläne", "GUI-/Computersteuerung", "komplexe Abläufe"], "level": "Fortgeschritten · viel Grafikspeicher",
        "desc": "Deutlich besser bei langen Plänen und Ketten aus vielen Schritten.",
    },
    {
        "id": "qwen25-coder-7b", "name": "Qwen2.5-Coder 7B", "repo": "Qwen/Qwen2.5-Coder-7B-Instruct-GGUF",
        "file": "qwen2.5-coder-7b-instruct-q4_k_m.gguf", "size_gb": 4.7, "min_vram_gb": 8,
        "tag": "Code ausführen",
        "uses": ["Code ausführen", "Python-Skripte", "PowerShell-Skripte"], "level": "Spezialist für Programmierung",
        "desc": "Auf Programmieren spezialisiert, schreibt die Skripte für das Werkzeug „Code ausführen“.",
    },
]


def models_dir() -> Path:
    try:
        configured = configuration.ConfigurationSettings().get_main_setting("models_directory")
    except Exception:
        configured = None
    base = Path(configured) if configured else Path("assets") / "local_llm"
    return base / SUBFOLDER


class AgentDownloadWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, str)
    done = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, entry):
        super().__init__()
        self.entry = entry
        self._cancel = False

    def cancel(self):
        self._cancel = True

    @staticmethod
    def _fmt(n):
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    def run(self):
        e = self.entry
        folder = models_dir()
        try:
            folder.mkdir(parents=True, exist_ok=True)
            url = f"{HF}/{e['repo']}/resolve/main/{e['file']}"
            head = requests.head(url, allow_redirects=True, timeout=20)
            head.raise_for_status()
            total = int(head.headers.get("content-length", 0)) or 1
            target = folder / e["file"]
            if target.is_file() and target.stat().st_size == total:
                self.done.emit(str(target))
                return
            part = folder / (e["file"] + ".part")
            started = time.time()
            got = 0
            with requests.get(url, stream=True, allow_redirects=True, timeout=30) as r:
                r.raise_for_status()
                with open(part, "wb") as fh:
                    for chunk in r.iter_content(chunk_size=1024 * 512):
                        if self._cancel:
                            break
                        if chunk:
                            fh.write(chunk)
                            got += len(chunk)
                            speed = got / max(time.time() - started, 0.001)
                            self.progress.emit(min(99, int(got * 100 / total)),
                                               f"{self._fmt(got)} / {self._fmt(total)}  -  {self._fmt(speed)}/s")
            if self._cancel:
                part.unlink(missing_ok=True)
                self.failed.emit("")
                return
            if part.stat().st_size != total:
                part.unlink(missing_ok=True)
                raise RuntimeError("Download incomplete")
            part.replace(target)
            self.done.emit(str(target))
        except Exception as exc:
            self.failed.emit(str(exc))


def build_agent_models_card(ui, create_glass_card, font_input):
    tr = ui.translations.get
    card, l = create_glass_card(tr("agent_models_title", "Recommended models for tools"))
    intro = QtWidgets.QLabel(tr(
        "agent_models_intro",
        "Werkzeuge (Browser, Dateien, Code ...) steuert dein Sprachmodell - es muss Werkzeug-Aufrufe unterstützen. "
        "Die Modelle unten sind dafür geeignet: herunterladen, danach unter „Sprachmodell & APIs“ auswählen. "
        "Welche Grafikkarte(n) ein Modell nutzt, stellst du unter „KI-Dienste“ ein."))
    intro.setWordWrap(True)
    intro.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(intro)
    need = QtWidgets.QLabel(tr(
        "agent_models_need",
        "<b>Welche brauche ich?</b> Nur EINS davon – die Modelle sind Optionen, keine Pflicht. Du brauchst kein zusätzliches Werkzeug-Modell: "
        "Dein Sprachmodell übernimmt die Werkzeuge, wenn es Werkzeug-Aufrufe kann (Qwen3 8B reicht für alles). Zusätzliche Modelle lohnen nur, wenn du sie gezielt willst:<br>"
        "• <b>4B</b> – für schwache Grafikkarten.<br>• <b>8B</b> – der Standard, für fast alles.<br>"
        "• <b>14B</b> – nur für lange Pläne und Computersteuerung, braucht viel Grafikspeicher.<br>"
        "• <b>Coder 7B</b> – Spezialist, nur fürs Werkzeug „Code ausführen“, ersetzt kein Hauptmodell.<br>"
        "• <b>Vision AI</b> (unten) – nur wenn Yume Bildschirm oder Kamera ansehen soll.<br>"
        "Ausgewählt wird immer nur eines unter „Sprachmodell &amp; APIs“; die anderen liegen nur auf der Festplatte. "
        "Willst du, dass ein anderer PC (z. B. der Yume LLM Server, Tab „Werkzeuge“) die Werkzeuge übernimmt, nutze das Feld „Werkzeug-Modell extern“ weiter unten."))
    need.setTextFormat(QtCore.Qt.TextFormat.RichText)
    need.setWordWrap(True)
    need.setStyleSheet("color: #E4D4FF; background: rgba(182,156,255,0.07); border: 1px solid rgba(182,156,255,0.28); border-radius: 10px; padding: 10px;")
    l.addWidget(need)
    gpu_btn = QtWidgets.QPushButton(tr("agent_models_open_services", "GPU-Zuweisung öffnen (KI-Dienste)"))
    gpu_btn.setFixedHeight(34)
    gpu_btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
    gpu_btn.setStyleSheet("QPushButton { background: rgba(182,156,255,0.14); color:#F1E8F6; border:1px solid rgba(182,156,255,0.45); border-radius:8px; padding: 0 14px; }"
                          "QPushButton:hover { background: rgba(182,156,255,0.26); }")
    gpu_btn.clicked.connect(lambda: ui.select_option_tab(7))
    l.addWidget(gpu_btn, 0, QtCore.Qt.AlignmentFlag.AlignLeft)
    ui.agent_model_widgets = {}
    for entry in AGENT_MODELS:
        row = QtWidgets.QFrame()
        row.setStyleSheet("QFrame { background: rgba(255,143,199,0.04); border: 1px solid rgba(255,143,199,0.16); border-radius: 12px; }")
        rl = QtWidgets.QHBoxLayout(row)
        rl.setContentsMargins(14, 10, 14, 10)
        text = QtWidgets.QVBoxLayout()
        text.setSpacing(4)
        title = QtWidgets.QLabel(entry["name"] + ("   ★" if entry.get("recommended") else ""))
        title.setStyleSheet("color: #F1E8F6; font-weight: 700; font-size: 14px; border: none; background: transparent;")
        uses = QtWidgets.QLabel("<span style='color:#B9A9C9'>Geeignet für:</span>  " + "   ".join(
            f"<span style='color:#FFC2E2'>● {u}</span>" for u in entry.get("uses", [entry["tag"]])))
        uses.setTextFormat(QtCore.Qt.TextFormat.RichText)
        uses.setWordWrap(True)
        uses.setStyleSheet("border: none; background: transparent;")
        specs = QtWidgets.QLabel(f"{entry.get('level', '')}   ·   Download ~{entry['size_gb']} GB   ·   ab {entry['min_vram_gb']} GB Grafikspeicher")
        specs.setStyleSheet("color: #8D7AA3; font-size: 11px; border: none; background: transparent;")
        desc = QtWidgets.QLabel(entry["desc"])
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
        status = QtWidgets.QLabel("")
        status.setStyleSheet("color: #ffc2e2; font-size: 11px; border: none; background: transparent;")
        text.addWidget(title)
        text.addWidget(uses)
        text.addWidget(desc)
        text.addWidget(specs)
        text.addWidget(status)
        rl.addLayout(text, 1)
        btn = QtWidgets.QPushButton()
        btn.setFixedSize(130, 36)
        btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet("QPushButton { background: rgba(255,143,199,0.14); color:#F1E8F6; border:1px solid rgba(255,143,199,0.45); "
                          "border-radius:8px; } QPushButton:hover { background: rgba(255,143,199,0.26); }")
        rl.addWidget(btn)
        l.addWidget(row)
        ui.agent_model_widgets[entry["id"]] = (entry, btn, status)

    vision_row = QtWidgets.QFrame()
    vision_row.setStyleSheet("QFrame { background: rgba(182,156,255,0.07); border: 1px solid rgba(182,156,255,0.28); border-radius: 12px; }")
    vl = QtWidgets.QHBoxLayout(vision_row)
    vl.setContentsMargins(14, 10, 14, 10)
    vtext = QtWidgets.QLabel(tr(
        "agent_models_vision",
        "GUI control & screen analysis: use a Vision AI model (recommended: Qwen2.5-VL 3B or 7B, strong at screen content)."))
    vtext.setWordWrap(True)
    vtext.setStyleSheet("color: #E4D4FF; border: none; background: transparent;")
    vl.addWidget(vtext, 1)
    vbtn = QtWidgets.QPushButton(tr("agent_models_open_vision", "Open Vision AI"))
    vbtn.setFixedSize(130, 36)
    vbtn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
    vbtn.setStyleSheet("QPushButton { background: rgba(182,156,255,0.16); color:#F1E8F6; border:1px solid rgba(182,156,255,0.5); border-radius:8px; }"
                       "QPushButton:hover { background: rgba(182,156,255,0.28); }")
    vbtn.clicked.connect(lambda: ui.select_option_tab(3))
    vl.addWidget(vbtn)
    l.addWidget(vision_row)

    ext_box = QtWidgets.QFrame()
    ext_box.setStyleSheet("QFrame { background: rgba(255,143,199,0.04); border: 1px solid rgba(255,143,199,0.16); border-radius: 12px; }"
                          "QLabel { border: none; background: transparent; color: #B9A9C9; }")
    el = QtWidgets.QVBoxLayout(ext_box)
    el.setContentsMargins(14, 10, 14, 12)
    et = QtWidgets.QLabel(tr("tool_ext_title", "Werkzeug-Modell extern (optional)"))
    et.setStyleSheet("color: #F1E8F6; font-weight: 700; font-size: 14px; border: none; background: transparent;")
    el.addWidget(et)
    ed = QtWidgets.QLabel(tr(
        "tool_ext_desc",
        "Ein zweites Sprachmodell auf einem anderen PC entscheidet nur, WELCHES Werkzeug benutzt wird (Yume LLM Server → Tab „Werkzeuge“, Port 8083). "
        "Die Antwort schreibt weiterhin dein Chat-Modell. Das entlastet die Grafikkarte des Chat-Modells und macht Werkzeuge schneller. "
        "Ist der Server nicht erreichbar, übernimmt das Chat-Modell automatisch. Auf dem Server-PC brauchen zwei Modelle gleichzeitig entsprechend Grafikspeicher."))
    ed.setWordWrap(True)
    el.addWidget(ed)
    ui.checkBox_tool_ext = QtWidgets.QCheckBox(tr("tool_ext_on", "Externes Werkzeug-Modell benutzen"))
    ui.checkBox_tool_ext.setFont(font_input)
    ui.checkBox_tool_ext.setStyleSheet("color: #F1E8F6; border: none; background: transparent;")
    el.addWidget(ui.checkBox_tool_ext)
    form = QtWidgets.QFormLayout()
    ui.lineEdit_tool_ext_url = QtWidgets.QLineEdit()
    ui.lineEdit_tool_ext_url.setPlaceholderText("http://192.168.1.50:8083")
    ui.lineEdit_tool_ext_model = QtWidgets.QLineEdit()
    ui.lineEdit_tool_ext_model.setPlaceholderText("local-model")
    ui.lineEdit_tool_ext_key = QtWidgets.QLineEdit()
    ui.lineEdit_tool_ext_key.setEchoMode(QtWidgets.QLineEdit.EchoMode.Password)
    ui.lineEdit_tool_ext_key.setPlaceholderText(tr("tool_ext_key_ph", "nur nötig, wenn du am Server einen API-Schlüssel gesetzt hast"))
    for w in (ui.lineEdit_tool_ext_url, ui.lineEdit_tool_ext_model, ui.lineEdit_tool_ext_key):
        w.setFixedHeight(34)
        w.setFont(font_input)
    form.addRow(tr("tool_ext_url", "Adresse"), ui.lineEdit_tool_ext_url)
    form.addRow(tr("tool_ext_model", "Modellname"), ui.lineEdit_tool_ext_model)
    form.addRow(tr("tool_ext_key", "API-Schlüssel"), ui.lineEdit_tool_ext_key)
    el.addLayout(form)
    trow = QtWidgets.QHBoxLayout()
    ui.pushButton_tool_ext_test = QtWidgets.QPushButton(tr("tool_ext_test", "Verbindung testen"))
    ui.pushButton_tool_ext_test.setFixedHeight(34)
    ui.label_tool_ext = QtWidgets.QLabel("")
    ui.label_tool_ext.setWordWrap(True)
    trow.addWidget(ui.pushButton_tool_ext_test)
    trow.addWidget(ui.label_tool_ext, 1)
    el.addLayout(trow)
    l.addWidget(ext_box)

    ui.agent_models_controller = AgentModelsController(ui)
    return card


class AgentModelsController(QtCore.QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.worker = None
        self.active_id = None
        for mid, (entry, btn, status) in ui.agent_model_widgets.items():
            btn.clicked.connect(lambda _=False, m=mid: self._clicked(m))
        self.refresh()
        self._load_ext()
        ui.checkBox_tool_ext.toggled.connect(self._save_ext)
        for w in (ui.lineEdit_tool_ext_url, ui.lineEdit_tool_ext_model, ui.lineEdit_tool_ext_key):
            w.editingFinished.connect(self._save_ext)
        ui.pushButton_tool_ext_test.clicked.connect(self._test_ext)

    def _load_ext(self):
        from app.utils import tool_llm
        ui = self.ui
        self._loading = True
        try:
            ui.checkBox_tool_ext.setChecked(bool(configuration.ConfigurationSettings().get_main_setting("tool_llm_external")))
            ui.lineEdit_tool_ext_url.setText(tool_llm.base_url() or tool_llm.suggested_url())
            ui.lineEdit_tool_ext_model.setText(tool_llm.model_name() if tool_llm.model_name() != "local-model" else "")
            ui.lineEdit_tool_ext_key.setText(tool_llm.api_key())
        finally:
            self._loading = False

    def _save_ext(self, *_):
        if getattr(self, "_loading", False):
            return
        from app.utils import tool_llm
        ui = self.ui
        try:
            tool_llm.save(ui.checkBox_tool_ext.isChecked(), tool_llm.normalize(ui.lineEdit_tool_ext_url.text()),
                          ui.lineEdit_tool_ext_model.text(), ui.lineEdit_tool_ext_key.text())
        except Exception:
            logger.exception("could not save the external tool model")

    def _test_ext(self):
        from app.utils import tool_llm
        ui = self.ui
        ok, text = tool_llm.test(ui.lineEdit_tool_ext_url.text(), ui.lineEdit_tool_ext_key.text())
        ui.label_tool_ext.setText(("✓ " if ok else "✗ ") + text)
        ui.label_tool_ext.setStyleSheet("border: none; background: transparent; color: " + ("#6EE7A0" if ok else "#FF8A9A") + ";")

    def _installed(self, entry) -> bool:
        return (models_dir() / entry["file"]).is_file()

    def refresh(self):
        tr = self.ui.translations.get
        for mid, (entry, btn, status) in self.ui.agent_model_widgets.items():
            busy = self.worker is not None and self.active_id == mid
            if busy:
                btn.setText(tr("agent_models_cancel", "Cancel"))
                btn.setEnabled(True)
            elif self._installed(entry):
                btn.setText(tr("agent_models_delete", "Delete"))
                btn.setEnabled(self.worker is None)
                status.setText(tr("agent_models_installed", "Installed: {p}").format(p=models_dir() / entry["file"]))
            else:
                btn.setText(tr("agent_models_download", "Download"))
                btn.setEnabled(self.worker is None)
                if not busy:
                    status.setText("")

    def _clicked(self, mid):
        entry, btn, status = self.ui.agent_model_widgets[mid]
        if self.worker is not None and self.active_id == mid:
            self.worker.cancel()
            return
        if self._installed(entry):
            try:
                (models_dir() / entry["file"]).unlink()
                status.setText("")
            except OSError as exc:
                status.setText(str(exc))
            self.refresh()
            return
        self.active_id = mid
        self.worker = AgentDownloadWorker(entry)
        self.worker.progress.connect(lambda p, t, s=status: s.setText(f"{p} %  -  {t}"))
        self.worker.done.connect(self._done)
        self.worker.failed.connect(self._failed)
        self.worker.start()
        self.refresh()

    def _finish(self):
        self.worker = None
        self.active_id = None
        self.refresh()

    def _done(self, path):
        status = self.ui.agent_model_widgets[self.active_id][2]
        self._finish()
        status.setText(self.ui.translations.get("agent_models_ready", "Ready: choose it under Local LLM. File: {p}").format(p=path))

    def _failed(self, message):
        status = self.ui.agent_model_widgets[self.active_id][2]
        self._finish()
        status.setText(message or self.ui.translations.get("agent_models_cancelled", "Cancelled."))
