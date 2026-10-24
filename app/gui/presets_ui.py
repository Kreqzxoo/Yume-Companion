"""Quick templates (Fast / Balanced / Best quality) for the local LLM page, chosen to fit the detected graphics card."""
from __future__ import annotations

import logging

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("Presets")

PRESETS = {
    "fast": {
        "title": ("Fast", "Schnell"), "icon": "⚡",
        "desc": ("Short answers, little memory, quick voice start. Best for weak or busy graphics cards.",
                 "Kurze Antworten, wenig Speicher, schneller Sprachstart. Ideal für schwache oder ausgelastete Grafikkarten."),
        "ctx": 8192, "max_tokens": 1024, "reasoning_mode": False, "reasoning_effort": "none", "batch": 512,
        "tts_chars": 200, "tts_pause": 90, "vision_px": 768,
    },
    "balanced": {
        "title": ("Balanced", "Ausgewogen"), "icon": "❀",
        "desc": ("Good mix of speed and quality for everyday chats and role play.",
                 "Guter Mix aus Tempo und Qualität für Alltag und Rollenspiel."),
        "ctx": 16384, "max_tokens": 2048, "reasoning_mode": True, "reasoning_effort": "low", "batch": 512,
        "tts_chars": 280, "tts_pause": 140, "vision_px": 1024,
    },
    "quality": {
        "title": ("Best quality", "Beste Qualität"), "icon": "✦",
        "desc": ("Long memory, long answers, careful thinking. Needs a strong graphics card.",
                 "Langes Gedächtnis, lange Antworten, gründliches Nachdenken. Braucht eine starke Grafikkarte."),
        "ctx": 32768, "max_tokens": 4096, "reasoning_mode": True, "reasoning_effort": "high", "batch": 1024,
        "tts_chars": 400, "tts_pause": 180, "vision_px": 1536,
    },
}

BTN = ("QPushButton { background: rgba(255,143,199,0.15); color:#F6EAF6; border:1px solid rgba(255,143,199,0.5); "
       "border-radius:10px; font-weight:600; } QPushButton:hover { background: rgba(255,143,199,0.3); }")


def detect_vram_gb() -> tuple[float, str]:
    try:
        from app.utils.dashboard_server import _gpu_info
        gpus = _gpu_info()
        if gpus:
            best = max(gpus, key=lambda g: g.get("mem_total") or 0)
            return (best.get("mem_total") or 0) / 1024.0, best.get("name", "GPU")
    except Exception:
        pass
    return 0.0, ""


def context_cap(vram_gb: float) -> int:
    if vram_gb >= 11.5:
        return 32768
    if vram_gb >= 7.5:
        return 16384
    if vram_gb >= 5.5:
        return 12288
    return 8192


def recommended(vram_gb: float) -> str:
    if vram_gb >= 11.5:
        return "quality"
    if vram_gb >= 7.5:
        return "balanced"
    return "fast"


def build_presets_card(ui, create_glass_card, font_input):
    german = int(_setting("program_language", 0) or 0) == 2
    idx = 1 if german else 0
    tr = ui.translations.get
    card, l = create_glass_card(tr("presets_title", "Quick templates"))
    vram, gpu_name = detect_vram_gb()
    if gpu_name:
        info = tr("presets_detected", "Detected: {gpu} · {vram:.0f} GB graphics memory").format(gpu=gpu_name, vram=vram)
    else:
        info = tr("presets_no_gpu", "No NVIDIA graphics card detected - the templates use conservative values.")
    intro = QtWidgets.QLabel(tr("presets_intro", "One click sets context size, answer length, thinking depth, voice chunks and image size. "
                                "You can still fine-tune everything afterwards.") + "\n" + info)
    intro.setWordWrap(True)
    intro.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(intro)
    row = QtWidgets.QHBoxLayout()
    row.setSpacing(12)
    rec = recommended(vram)
    ui.preset_buttons = {}
    for key, p in PRESETS.items():
        box = QtWidgets.QFrame()
        box.setStyleSheet("QFrame { background: rgba(255,143,199,0.05); border: 1px solid rgba(255,143,199,0.2); border-radius: 14px; }"
                          "QLabel { background: transparent; border: none; }")
        v = QtWidgets.QVBoxLayout(box)
        v.setContentsMargins(16, 14, 16, 14)
        head = QtWidgets.QLabel(f"{p['icon']}  {p['title'][idx]}" + (("   ★ " + tr("presets_recommended", "recommended")) if key == rec and gpu_name else ""))
        head.setStyleSheet("color: #F6EAF6; font-size: 15px; font-weight: 600;")
        desc = QtWidgets.QLabel(p["desc"][idx])
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #BFAFD0; font-size: 12px;")
        ctx = min(p["ctx"], context_cap(vram))
        facts = QtWidgets.QLabel(tr("presets_facts", "Context {ctx} · reply up to {mt} tokens").format(ctx=f"{ctx:,}".replace(",", "."), mt=p["max_tokens"]))
        facts.setStyleSheet("color: #8D7AA3; font-size: 11px;")
        btn = QtWidgets.QPushButton(tr("presets_apply", "Apply"))
        btn.setFixedHeight(34)
        btn.setCursor(QtGui.QCursor(QtCore.Qt.CursorShape.PointingHandCursor))
        btn.setStyleSheet(BTN)
        v.addWidget(head)
        v.addWidget(desc, 1)
        v.addWidget(facts)
        v.addWidget(btn)
        row.addWidget(box, 1)
        ui.preset_buttons[key] = btn
    l.addLayout(row)
    ui.label_preset_status = QtWidgets.QLabel("")
    ui.label_preset_status.setWordWrap(True)
    ui.label_preset_status.setStyleSheet("color: #FFC2E2; border: none; background: transparent;")
    l.addWidget(ui.label_preset_status)
    ui.presets_controller = PresetsController(ui, vram)
    return card


def _setting(key, default=None):
    try:
        from app.configuration.configuration import ConfigurationSettings
        value = ConfigurationSettings().get_main_setting(key)
        return default if value is None else value
    except Exception:
        return default


class PresetsController(QtCore.QObject):
    def __init__(self, ui, vram):
        super().__init__()
        self.ui = ui
        self.vram = vram
        self.signals = None
        for key, btn in ui.preset_buttons.items():
            btn.clicked.connect(lambda _=False, k=key: self.apply(k))

    def attach(self, signals):
        self.signals = signals

    def snapshot_for(self, key) -> dict:
        p = PRESETS[key]
        vram = self.vram
        values = list(getattr(self.ui, "CONTEXT_VALUES", [8192, 16384, 32768]))
        wanted = min(p["ctx"], context_cap(vram))
        ctx = max([v for v in values if v <= wanted] or [8192])
        snap = {
            "context_size": ctx, "max_tokens": p["max_tokens"], "reasoning_mode": p["reasoning_mode"],
            "reasoning_effort": p["reasoning_effort"],
            "llm_batch_size": p["batch"] if (key != "quality" or vram >= 7.5) else 512,
        }
        if vram >= 5.5:
            snap["flash_attention_status"] = True
            snap["gpu_layers"] = 99
        return snap

    def apply(self, key):
        if self.signals is None:
            return
        s = self.signals
        p = PRESETS[key]
        snap = self.snapshot_for(key)
        try:
            s._apply_llm_settings_snapshot(snap)
            cfg = s.configuration_settings
            cfg.update_main_setting("tts_chunk_max_chars", p["tts_chars"])
            cfg.update_main_setting("tts_chunk_pause_ms", p["tts_pause"])
            cfg.update_main_setting("vision_max_image_px", p["vision_px"] if (key != "quality" or self.vram >= 7.5) else 1024)
            cfg.update_main_setting("active_llm_preset", None)
            try:
                s.initialize_extended_settings()   # refresh the TTS/vision spin boxes on the other pages
            except Exception:
                pass
            german = int(cfg.get_main_setting("program_language") or 0) == 2
            name = p["title"][1 if german else 0]
            text = (f"„{name}“ angewendet: Kontext {snap['context_size']:,}".replace(",", ".") + f", Antwort bis {snap['max_tokens']} Tokens."
                    if german else f"'{name}' applied: context {snap['context_size']:,}, reply up to {snap['max_tokens']} tokens.")
            self.ui.label_preset_status.setText(text)
            from app.gui.custom_widgets import sow_toast
            sow_toast(parent=s.main_window, title=name, text=text, msg_type="success")
        except Exception as exc:
            logger.exception("Applying the template failed")
            self.ui.label_preset_status.setText(str(exc))
