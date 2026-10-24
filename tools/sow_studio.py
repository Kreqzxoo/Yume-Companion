"""Soul of Waifu Studio: local helper for voice settings, GPU placement, branding and translations.

Run from the project directory with PyQt6 and PyYAML installed:
    python tools/sow_studio.py

The standalone package can also launch this tool separately; use the folder
picker to select the Soul of Waifu project/install root to edit.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import yaml
from PyQt6 import QtCore, QtGui, QtWidgets

APP_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_SETTINGS = {
    "anti_echo_mode": "half_duplex",
    "anti_echo_tail_ms": 700,
    "wake_word_enabled": False,
    "wake_word": "Alexa",
    "wake_word_timeout_sec": 30,
    "voice_silence_ms": 760,
    "voice_preroll_ms": 192,
    "whisper_device": "cuda",
    "whisper_gpu_index": 0,
    "llm_cuda_gpu_indices": "0",
    "qwen_gpu_index": 0,
    "tts_chunk_max_chars": 280,
    "tts_chunk_pause_ms": 140,
    "lipsync_smoothing": True,
}

DARK_STYLE = """
QWidget { background: #17181d; color: #e8eaf0; font-size: 10pt; }
QMainWindow, QDialog { background: #111217; }
QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QDoubleSpinBox, QTableWidget {
  background: #22242c; color: #f1f2f6; border: 1px solid #383b46; border-radius: 5px; padding: 5px;
}
QPushButton { background: #2d4158; border: 1px solid #4c7097; border-radius: 6px; padding: 7px 12px; }
QPushButton:hover { background: #385776; }
QTabWidget::pane { border: 1px solid #343742; }
QHeaderView::section { background: #252832; padding: 6px; border: 1px solid #383b46; }
QCheckBox { spacing: 8px; }
QLabel#hint { color: #b9c0ce; }
"""


def read_json(path: Path, default):
    try:
        if path.exists():
            value = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(value, type(default)):
                return value
    except Exception:
        pass
    return default.copy() if isinstance(default, dict) else default


def write_json_safely(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        backup = path.with_suffix(path.suffix + ".bak")
        try:
            shutil.copy2(path, backup)
        except Exception:
            pass
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=4) + "\n", encoding="utf-8")
    tmp.replace(path)


def read_yaml(path: Path) -> dict:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


class SowStudio(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Soul of Waifu Studio — Stimme, GPUs, Branding & Deutsch")
        self.setMinimumSize(1060, 790)
        self.setStyleSheet(DARK_STYLE)
        self.root = APP_ROOT
        self.settings_path = self.root / "app/configuration/settings.json"
        self.characters_path = self.root / "app/configuration/characters.json"
        self.branding_path = self.root / "app/configuration/branding.json"
        self.source_yaml_path = self.root / "app/translations/en.yaml"
        self.de_yaml_path = self.root / "app/translations/de.yaml"
        self.brand_logo_source: Path | None = None
        self._translation_rows = []

        center = QtWidgets.QWidget()
        outer = QtWidgets.QVBoxLayout(center)
        outer.setContentsMargins(14, 14, 14, 14)
        outer.setSpacing(10)

        root_row = QtWidgets.QHBoxLayout()
        root_row.addWidget(QtWidgets.QLabel("Soul-of-Waifu-Projektordner:"))
        self.root_edit = QtWidgets.QLineEdit(str(self.root))
        root_row.addWidget(self.root_edit, 1)
        browse_root = QtWidgets.QPushButton("Ordner…")
        browse_root.clicked.connect(self.choose_root)
        root_row.addWidget(browse_root)
        reload_btn = QtWidgets.QPushButton("Neu laden")
        reload_btn.clicked.connect(self.load_all)
        root_row.addWidget(reload_btn)
        outer.addLayout(root_row)

        self.tabs = QtWidgets.QTabWidget()
        self.voice_tab = self._build_voice_tab()
        self.gpu_tab = self._build_gpu_tab()
        self.branding_tab = self._build_branding_tab()
        self.translation_tab = self._build_translation_tab()
        self.tabs.addTab(self.voice_tab, "Stimme & Gespräch")
        self.tabs.addTab(self.gpu_tab, "GPU-Zuweisung")
        self.tabs.addTab(self.branding_tab, "Logo & Credits")
        self.tabs.addTab(self.translation_tab, "Deutsche Übersetzung")
        outer.addWidget(self.tabs, 1)

        bottom = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel("Bereit. Änderungen werden erst nach dem Speichern übernommen.")
        self.status_label.setObjectName("hint")
        bottom.addWidget(self.status_label, 1)
        self.save_btn = QtWidgets.QPushButton("Einstellungen speichern")
        self.save_btn.setStyleSheet("font-weight: bold; background: #356b4a; border-color: #4d9368;")
        self.save_btn.clicked.connect(self.save_all)
        bottom.addWidget(self.save_btn)
        outer.addLayout(bottom)
        self.setCentralWidget(center)
        self.load_all()

    def _label(self, text):
        label = QtWidgets.QLabel(text)
        label.setWordWrap(True)
        return label

    def _spin(self, low, high, value, suffix=""):
        widget = QtWidgets.QSpinBox()
        widget.setRange(low, high)
        widget.setValue(value)
        widget.setSuffix(suffix)
        return widget

    def _build_voice_tab(self):
        tab = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(tab)
        form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        self.pacing_combo = QtWidgets.QComboBox()
        self.pacing_combo.addItem("Reaktionsschnell – kurze Pausen", "snappy")
        self.pacing_combo.addItem("Natürlich – ausgewogen (empfohlen)", "natural")
        self.pacing_combo.addItem("Ruhig – längere Sprechpausen", "calm")
        self.pacing_apply_btn = QtWidgets.QPushButton("Voreinstellung anwenden")
        self.pacing_apply_btn.clicked.connect(self.apply_pacing_preset)
        pacing_row = QtWidgets.QHBoxLayout()
        pacing_row.addWidget(self.pacing_combo, 1)
        pacing_row.addWidget(self.pacing_apply_btn)

        self.echo_combo = QtWidgets.QComboBox()
        self.echo_combo.addItem("Aus", "off")
        self.echo_combo.addItem("Anti-Echo / Halbduplex (Mikro während TTS blockieren)", "half_duplex")
        self.echo_tail = self._spin(0, 3000, 700, " ms")
        self.wake_enabled = QtWidgets.QCheckBox("Wake-Word aktivieren")
        self.wake_words = QtWidgets.QLineEdit("Alexa")
        self.wake_words.setPlaceholderText("z. B. Alexa, Hey Jarvis, Yume — durch Komma trennen")
        self.wake_timeout = self._spin(5, 600, 30, " s")
        self.silence_ms = self._spin(200, 2500, 760, " ms")
        self.preroll_ms = self._spin(0, 500, 192, " ms")
        self.chunk_chars = self._spin(120, 500, 280, " Zeichen")
        self.chunk_pause = self._spin(0, 1000, 140, " ms")
        self.lipsync_smoothing = QtWidgets.QCheckBox("Lippensynchronisation weich glätten")

        form.addRow("Gesprächsrhythmus", pacing_row)
        form.addRow("Anti-Echo-Modus", self.echo_combo)
        form.addRow("Nachlauf nach TTS", self.echo_tail)
        form.addRow(self.wake_enabled)
        form.addRow("Wake-Wörter / Phrasen", self.wake_words)
        form.addRow("Nach Wake-Word aktiv bleiben", self.wake_timeout)
        form.addRow("Stille bis Satzende (VAD)", self.silence_ms)
        form.addRow("Audio-Vorlauf gegen abgeschnittene Anfangslaute", self.preroll_ms)
        form.addRow("Max. Zeichen je TTS-Segment", self.chunk_chars)
        form.addRow("Pause zwischen TTS-Segmenten", self.chunk_pause)
        form.addRow(self.lipsync_smoothing)
        form.addRow(self._label(
            "Hinweis zum Anti-Echo: Der integrierte Halbduplex-Schutz ignoriert Mikrofon-Audio, solange Soul of Waifu selbst spricht, plus Nachlaufzeit. Dadurch sollte sie sich nicht selbst auslösen; du kannst während ihrer Ausgabe aber nicht gleichzeitig hineinsprechen. Echtes Vollduplex-AEC benötigt eine AEC-fähige Audio-Engine / Loopback-Referenz."
        ))
        form.addRow(self._label(
            "Für flüssigere Sprache sind 650–900 ms Stille und 180–300 Zeichen pro Segment gute Startwerte. Zu kurze Segmente klingen abgehackt; zu lange Segmente erhöhen die Generierungszeit und können Modelle an ihre Token-Grenzen bringen."
        ))
        return tab

    def apply_pacing_preset(self):
        """Apply a coherent set of low-latency / natural / calm voice values."""
        values = {
            "snappy": {"silence": 600, "preroll": 160, "chunk": 220, "pause": 80, "tail": 500},
            "natural": {"silence": 760, "preroll": 192, "chunk": 280, "pause": 140, "tail": 700},
            "calm": {"silence": 900, "preroll": 224, "chunk": 240, "pause": 220, "tail": 850},
        }
        selected = values.get(self.pacing_combo.currentData(), values["natural"])
        self.silence_ms.setValue(selected["silence"])
        self.preroll_ms.setValue(selected["preroll"])
        self.chunk_chars.setValue(selected["chunk"])
        self.chunk_pause.setValue(selected["pause"])
        self.echo_tail.setValue(selected["tail"])
        self.status_label.setText(
            "Voreinstellung angewendet. Mit „Einstellungen speichern“ übernehmen; ein Neustart von Soul of Waifu ist erforderlich."
        )

    def _build_gpu_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        form = QtWidgets.QFormLayout()
        self.whisper_device = QtWidgets.QComboBox()
        self.whisper_device.addItem("CUDA / GPU", "cuda")
        self.whisper_device.addItem("CPU", "cpu")
        self.whisper_gpu = self._spin(0, 15, 0, " (0 = erste GPU)")
        self.llm_gpus = QtWidgets.QLineEdit("0")
        self.llm_gpus.setPlaceholderText("z. B. 1 oder 0,1 — physische CUDA-GPU-Indizes")
        self.qwen_default_gpu = self._spin(0, 15, 0, " (0 = erste GPU)")
        form.addRow("Whisper berechnen auf", self.whisper_device)
        form.addRow("Whisper-GPU-Index", self.whisper_gpu)
        form.addRow("Lokales llama.cpp: CUDA-GPUs", self.llm_gpus)
        form.addRow("Standard-GPU für Qwen3-TTS", self.qwen_default_gpu)
        layout.addLayout(form)

        layout.addWidget(self._label(
            "Pro Charakter: Wähle unten die Qwen3-TTS-GPU separat. LLM-CUDA-Auswahl wird nur für den internen llama.cpp-CUDA-Backendprozess angewendet; Remote-Ollama/llama.cpp verwendet die GPU-Zuweisung auf dem entfernten PC."
        ))
        layout.addWidget(self._label(
            "Animationen/Live2D/VRM laufen über die Grafik-Engine des Betriebssystems bzw. Qt/WebEngine und lassen sich nicht zuverlässig mit einem CUDA-Index wie Whisper oder Qwen zuweisen. Auf Windows kannst du die bevorzugte GPU für die Soul-of-Waifu-Anwendung unter Einstellungen → System → Bildschirm → Grafik festlegen."
        ))
        char_form = QtWidgets.QFormLayout()
        self.character_combo = QtWidgets.QComboBox()
        self.character_combo.currentIndexChanged.connect(self.load_selected_character_gpu)
        self.char_qwen_gpu = self._spin(0, 15, 0, " (0 = erste GPU)")
        self.char_qwen_device = QtWidgets.QComboBox()
        self.char_qwen_device.addItem("CUDA / GPU", "cuda")
        self.char_qwen_device.addItem("CPU", "cpu")
        char_form.addRow("Charakter", self.character_combo)
        char_form.addRow("Qwen3-TTS-GPU für diesen Charakter", self.char_qwen_gpu)
        char_form.addRow("Qwen3-TTS-Gerät", self.char_qwen_device)
        char_box = QtWidgets.QGroupBox("Qwen3-TTS pro Charakter")
        char_box.setLayout(char_form)
        layout.addWidget(char_box)
        layout.addStretch(1)
        return tab

    def _build_branding_tab(self):
        tab = QtWidgets.QWidget()
        form = QtWidgets.QFormLayout(tab)
        self.app_name = QtWidgets.QLineEdit("Soul of Waifu")
        self.logo_path_label = QtWidgets.QLineEdit("assets/custom_branding/app_logo.png")
        self.logo_path_label.setReadOnly(True)
        logo_row = QtWidgets.QHBoxLayout()
        logo_row.addWidget(self.logo_path_label, 1)
        self.logo_browse_btn = QtWidgets.QPushButton("Logo wählen…")
        self.logo_browse_btn.clicked.connect(self.choose_logo)
        logo_row.addWidget(self.logo_browse_btn)
        self.credits_text = QtWidgets.QPlainTextEdit()
        self.credits_text.setPlaceholderText("Zusätzliche Credits, eigene Erweiterungen, Hinweise …")
        self.credits_text.setMinimumHeight(160)
        form.addRow("App-Titel", self.app_name)
        form.addRow("Eigenes Logo", logo_row)
        form.addRow("Zusätzliche Credits / Hinweise", self.credits_text)
        form.addRow(self._label(
            "Die Original-Copyright-Hinweise und die Open-Source-Lizenz des Projekts bleiben erhalten. Hier kannst du eigene zusätzliche Credits und Hinweise ergänzen; die Auswahl eines Logos ändert die Hauptfenster-/About-Ansicht nach einem Neustart."
        ))
        return tab

    def _build_translation_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        top = QtWidgets.QHBoxLayout()
        self.translation_search = QtWidgets.QLineEdit()
        self.translation_search.setPlaceholderText("Nach Schlüssel, englischem Text oder deutscher Übersetzung suchen …")
        self.translation_search.textChanged.connect(self.filter_translations)
        top.addWidget(self.translation_search, 1)
        self.show_untranslated = QtWidgets.QCheckBox("Nur unübersetzte / englische Einträge")
        self.show_untranslated.toggled.connect(self.filter_translations)
        top.addWidget(self.show_untranslated)
        layout.addLayout(top)
        self.translation_table = QtWidgets.QTableWidget(0, 3)
        self.translation_table.setHorizontalHeaderLabels(["Schlüssel", "Englische Vorlage", "Deutsch (bearbeitbar)"])
        self.translation_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.translation_table.setAlternatingRowColors(True)
        self.translation_table.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.translation_table.horizontalHeader().setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.translation_table.horizontalHeader().setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.translation_table.verticalHeader().setDefaultSectionSize(26)
        layout.addWidget(self.translation_table, 1)
        buttons = QtWidgets.QHBoxLayout()
        reload_translations = QtWidgets.QPushButton("Übersetzungen neu laden")
        reload_translations.clicked.connect(self.load_translation_table)
        save_translations = QtWidgets.QPushButton("de.yaml speichern")
        save_translations.clicked.connect(self.save_translations)
        buttons.addWidget(reload_translations)
        buttons.addStretch(1)
        buttons.addWidget(save_translations)
        layout.addLayout(buttons)
        layout.addWidget(self._label(
            "Die Tabelle enthält alle Schlüssel der englischen Vorlage. Ein noch englischer Eintrag ist nicht automatisch übersetzt; nutze den Filter, bearbeite die fehlenden Zeilen und speichere. Platzhalter wie {name}, HTML-Tags und Zeilenumbrüche müssen erhalten bleiben."
        ))
        return tab

    def choose_root(self):
        folder = QtWidgets.QFileDialog.getExistingDirectory(self, "Projektordner wählen", self.root_edit.text())
        if folder:
            self.root_edit.setText(folder)
            self.root = Path(folder).resolve()
            self._resolve_paths()
            self.load_all()

    def _resolve_paths(self):
        self.root = Path(self.root_edit.text().strip()).resolve()
        self.settings_path = self.root / "app/configuration/settings.json"
        self.characters_path = self.root / "app/configuration/characters.json"
        self.branding_path = self.root / "app/configuration/branding.json"
        self.source_yaml_path = self.root / "app/translations/en.yaml"
        self.de_yaml_path = self.root / "app/translations/de.yaml"

    def load_all(self):
        self._resolve_paths()
        if not self.settings_path.exists():
            self.status_label.setText("Projektordner ungültig: app/configuration/settings.json wurde nicht gefunden.")
            return
        settings = read_json(self.settings_path, {"main_settings": {}})
        main = settings.setdefault("main_settings", {})
        for k, v in DEFAULT_SETTINGS.items():
            main.setdefault(k, v)
        self.echo_combo.setCurrentIndex(max(0, self.echo_combo.findData(main.get("anti_echo_mode", "half_duplex"))))
        self.echo_tail.setValue(int(main.get("anti_echo_tail_ms", 700) or 0))
        self.wake_enabled.setChecked(bool(main.get("wake_word_enabled", False)))
        self.wake_words.setText(str(main.get("wake_word", "Alexa")))
        self.wake_timeout.setValue(int(main.get("wake_word_timeout_sec", 30) or 30))
        self.silence_ms.setValue(int(main.get("voice_silence_ms", 760) or 760))
        self.preroll_ms.setValue(int(main.get("voice_preroll_ms", 192) or 0))
        self.chunk_chars.setValue(int(main.get("tts_chunk_max_chars", 280) or 280))
        self.chunk_pause.setValue(int(main.get("tts_chunk_pause_ms", 140) or 0))
        self.lipsync_smoothing.setChecked(bool(main.get("lipsync_smoothing", True)))
        self.whisper_device.setCurrentIndex(max(0, self.whisper_device.findData(main.get("whisper_device", "cuda"))))
        self.whisper_gpu.setValue(int(main.get("whisper_gpu_index", 0) or 0))
        self.llm_gpus.setText(str(main.get("llm_cuda_gpu_indices", main.get("llm_cuda_gpu_index", "0"))))
        self.qwen_default_gpu.setValue(int(main.get("qwen_gpu_index", 0) or 0))
        self._load_characters()
        branding = read_json(self.branding_path, {"app_name": "Soul of Waifu", "logo_path": "assets/custom_branding/app_logo.png", "additional_credits": ""})
        self.app_name.setText(str(branding.get("app_name", "Soul of Waifu")))
        self.logo_path_label.setText(str(branding.get("logo_path", "assets/custom_branding/app_logo.png")))
        self.credits_text.setPlainText(str(branding.get("additional_credits", "")))
        self.load_translation_table()
        self.status_label.setText("Einstellungen geladen. Prüfe die Hinweise und speichere deine Änderungen.")

    def _load_characters(self):
        data = read_json(self.characters_path, {"character_list": {}})
        chars = data.get("character_list", {}) if isinstance(data, dict) else {}
        current = self.character_combo.currentData()
        self.character_combo.blockSignals(True)
        self.character_combo.clear()
        for name in sorted(chars):
            self.character_combo.addItem(name, name)
        idx = self.character_combo.findData(current)
        if idx >= 0:
            self.character_combo.setCurrentIndex(idx)
        self.character_combo.blockSignals(False)
        self.load_selected_character_gpu()

    def load_selected_character_gpu(self, *_):
        data = read_json(self.characters_path, {"character_list": {}})
        name = self.character_combo.currentData()
        cfg = data.get("character_list", {}).get(name, {}) if name else {}
        self.char_qwen_gpu.setValue(int(cfg.get("qwen_gpu_index", 0) or 0))
        self.char_qwen_device.setCurrentIndex(max(0, self.char_qwen_device.findData(cfg.get("qwen_device", "cuda"))))

    def choose_logo(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "Eigenes Logo auswählen", str(self.root), "Bilder (*.png *.jpg *.jpeg *.bmp *.webp *.ico)"
        )
        if filename:
            self.brand_logo_source = Path(filename)
            self.logo_path_label.setText("assets/custom_branding/app_logo.png")
            self.status_label.setText("Logo ausgewählt; beim Speichern wird eine PNG-Kopie im Projekt erstellt.")

    def save_all(self):
        self._resolve_paths()
        if not self.settings_path.exists():
            self.status_label.setText("Fehler: Der Projektordner enthält keine settings.json.")
            return
        data = read_json(self.settings_path, {"main_settings": {}, "user_data": {}})
        main = data.setdefault("main_settings", {})
        main.update({
            "anti_echo_mode": self.echo_combo.currentData() or "half_duplex",
            "anti_echo_tail_ms": self.echo_tail.value(),
            "wake_word_enabled": self.wake_enabled.isChecked(),
            "wake_word": self.wake_words.text().strip() or "Alexa",
            "wake_word_timeout_sec": self.wake_timeout.value(),
            "voice_silence_ms": self.silence_ms.value(),
            "voice_preroll_ms": self.preroll_ms.value(),
            "tts_chunk_max_chars": self.chunk_chars.value(),
            "tts_chunk_pause_ms": self.chunk_pause.value(),
            "lipsync_smoothing": self.lipsync_smoothing.isChecked(),
            "whisper_device": self.whisper_device.currentData() or "cuda",
            "whisper_gpu_index": self.whisper_gpu.value(),
            "llm_cuda_gpu_indices": self.llm_gpus.text().strip() or "0",
            "qwen_gpu_index": self.qwen_default_gpu.value(),
        })
        write_json_safely(self.settings_path, data)

        chars_data = read_json(self.characters_path, {"character_list": {}})
        name = self.character_combo.currentData()
        if name:
            cfg = chars_data.setdefault("character_list", {}).setdefault(name, {})
            cfg["qwen_gpu_index"] = self.char_qwen_gpu.value()
            cfg["qwen_device"] = self.char_qwen_device.currentData() or "cuda"
            write_json_safely(self.characters_path, chars_data)

        if self.brand_logo_source and self.brand_logo_source.exists():
            target = self.root / "assets/custom_branding/app_logo.png"
            target.parent.mkdir(parents=True, exist_ok=True)
            pix = QtGui.QPixmap(str(self.brand_logo_source))
            if pix.isNull() or not pix.save(str(target), "PNG"):
                QtWidgets.QMessageBox.warning(self, "Logo", "Das Bild konnte nicht als PNG gespeichert werden.")
                return
        # Merge: keep every key this tool does not know (links, author, ...).
        branding = read_json(self.branding_path, {})
        if not isinstance(branding, dict):
            branding = {}
        branding.update({
            "app_name": self.app_name.text().strip() or "Soul of Waifu",
            "logo_path": "assets/custom_branding/app_logo.png",
            "additional_credits": self.credits_text.toPlainText().strip(),
        })
        write_json_safely(self.branding_path, branding)
        self.brand_logo_source = None
        self.status_label.setText("Gespeichert. Für geänderte GPU-/Wake-/Audio-Einstellungen Soul of Waifu neu starten.")

    def load_translation_table(self):
        self._resolve_paths()
        source = read_yaml(self.source_yaml_path)
        german = read_yaml(self.de_yaml_path)
        self._translation_rows = [(str(k), str(v) if v is not None else "", str(german.get(k, "")) if german.get(k) is not None else "") for k, v in source.items()]
        self.translation_table.setRowCount(len(self._translation_rows))
        for row, (key, src, de) in enumerate(self._translation_rows):
            key_item = QtWidgets.QTableWidgetItem(key)
            key_item.setFlags(key_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            src_item = QtWidgets.QTableWidgetItem(src)
            src_item.setFlags(src_item.flags() & ~QtCore.Qt.ItemFlag.ItemIsEditable)
            src_item.setToolTip(src)
            de_item = QtWidgets.QTableWidgetItem(de or src)
            de_item.setToolTip("Platzhalter/Englisch: bitte übersetzen" if not de or de == src else de)
            self.translation_table.setItem(row, 0, key_item)
            self.translation_table.setItem(row, 1, src_item)
            self.translation_table.setItem(row, 2, de_item)
        self.filter_translations()

    def filter_translations(self, *_):
        query = self.translation_search.text().strip().casefold()
        untranslated_only = self.show_untranslated.isChecked()
        for row in range(self.translation_table.rowCount()):
            key = self.translation_table.item(row, 0).text()
            src = self.translation_table.item(row, 1).text()
            de = self.translation_table.item(row, 2).text()
            hit = not query or query in key.casefold() or query in src.casefold() or query in de.casefold()
            untranslated = (not de.strip()) or de.strip() == src.strip()
            self.translation_table.setRowHidden(row, not hit or (untranslated_only and not untranslated))

    def save_translations(self):
        self._resolve_paths()
        source = read_yaml(self.source_yaml_path)
        out = {}
        for row in range(self.translation_table.rowCount()):
            key = self.translation_table.item(row, 0).text()
            value = self.translation_table.item(row, 2).text()
            out[key] = value if value.strip() else source.get(key, "")
        self.de_yaml_path.parent.mkdir(parents=True, exist_ok=True)
        if self.de_yaml_path.exists():
            try:
                shutil.copy2(self.de_yaml_path, self.de_yaml_path.with_suffix(".yaml.bak"))
            except Exception:
                pass
        self.de_yaml_path.write_text(yaml.safe_dump(out, allow_unicode=True, sort_keys=False, width=120), encoding="utf-8")
        self.status_label.setText(f"Deutsche Übersetzungsdatei gespeichert: {self.de_yaml_path.name}")


def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Soul of Waifu Studio")
    window = SowStudio()
    window.show()
    # When launched from the standalone Studio bundle, its directory is not
    # the Soul of Waifu root. Ask the user to select the target project once.
    if not (window.root / "app/configuration/settings.json").exists():
        QtCore.QTimer.singleShot(300, window.choose_root)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
