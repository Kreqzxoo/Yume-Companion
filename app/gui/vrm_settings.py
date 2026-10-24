"""Visualisation settings: natural-motion options for the VRM avatar (shared by the main window and the desktop companion)."""
from __future__ import annotations

import json
import logging

from PyQt6 import QtCore, QtWidgets

logger = logging.getLogger("VrmSettings")

# setting key -> (default, JS option name)
DEFAULTS = {
    "vrm_natural": True,        # procedural idle motion, blended emotions, natural blinking and speaking
    "vrm_intensity": 100,       # emotion strength in percent
    "vrm_idle": 60,             # breathing / head sway in percent
    "vrm_eye_contact": True,    # eyes follow the camera
    "vrm_blink": 100,           # blink frequency in percent
    "vrm_hold": 25,             # seconds an emotion is held before relaxing to neutral
    "vrm_animations": True,     # play the full-body emotion animations (FBX)
    "vrm_gestures": True,       # small idle gestures now and then (touch head, fix hair, stretch ...)
}


def vrm_options(settings, char_data=None) -> dict:
    """Global values, overridden by the character's own `vrm_*` entries."""
    out = {}
    for key, default in DEFAULTS.items():
        value = settings.get_main_setting(key) if settings is not None else None
        if isinstance(char_data, dict) and key in char_data:
            value = char_data[key]
        out[key] = default if value is None or value == "" else value
    return out


def options_js(settings, char_data=None) -> str:
    o = vrm_options(settings, char_data)
    payload = {
        "natural": bool(o["vrm_natural"]),
        "intensity": max(0.0, min(1.5, float(o["vrm_intensity"]) / 100.0)),
        "idle": max(0.0, min(1.0, float(o["vrm_idle"]) / 100.0)),
        "eyeContact": bool(o["vrm_eye_contact"]),
        "blink": max(0.3, min(2.5, float(o["vrm_blink"]) / 100.0)),
        "hold": max(3.0, float(o["vrm_hold"])),
        "animations": bool(o["vrm_animations"]),
        "gestures": bool(o["vrm_gestures"]),
    }
    return f"if (window.setVrmOptions) window.setVrmOptions({json.dumps(payload)});"


def animations_enabled(settings, char_data=None) -> bool:
    return bool(vrm_options(settings, char_data)["vrm_animations"])


# ---------------------------------------------------------------- emotion helpers
ACTION_KEYWORDS = [
    # (emotion, german/english words that appear inside *action text*)
    ("embarrassment", ("errötet", "rot im gesicht", "blushes", "blush", "verlegen", "shyly", "schüchtern", "bashful")),
    ("amusement", ("lacht", "kichert", "grinst", "laughs", "giggles", "chuckles", "smirks", "schmunzelt")),
    ("joy", ("strahlt", "lächelt breit", "beams", "grins happily", "smiles brightly", "jubelt")),
    ("love", ("umarmt", "küsst", "kuschelt", "hugs", "kisses", "cuddles", "schmiegt")),
    ("sadness", ("weint", "schluchzt", "tränen", "cries", "sobs", "tears")),
    ("disappointment", ("seufzt", "sighs", "lässt den kopf hängen")),
    ("anger", ("faucht", "knurrt", "wütend", "growls", "snaps", "glares", "stampft")),
    ("surprise", ("erschrickt", "keucht", "starrt", "gasps", "startles", "wide-eyed", "reißt die augen auf")),
    ("fear", ("zittert", "zuckt zusammen", "trembles", "shivers", "flinches")),
    ("curiosity", ("neigt den kopf", "tilts head", "blinzelt neugierig", "beugt sich vor")),
    ("confusion", ("runzelt die stirn", "verwirrt", "frowns in confusion", "scratches head", "kratzt sich am kopf")),
    ("pride", ("reckt das kinn", "stolz", "puffs chest", "lifts chin")),
    ("relief", ("atmet auf", "erleichtert", "exhales in relief")),
    ("nervousness", ("nervös", "fidgets", "nibbles", "kaut auf der lippe", "zappelt")),
    ("gratitude", ("verbeugt sich", "dankbar", "bows", "thankfully")),
]


def emotion_from_actions(text: str):
    """Roleplay actions in *asterisks* are a strong, language-independent emotion hint for the avatar."""
    import re
    actions = " ".join(re.findall(r"\*([^*\n]{2,120})\*", text or "")).lower()
    if not actions:
        return None
    for emotion, words in ACTION_KEYWORDS:
        if any(w in actions for w in words):
            return emotion
    return None


# ---------------------------------------------------------------- settings card
def build_vrm_card(ui, create_glass_card, font_label, font_input):
    tr = ui.translations.get
    card, l = create_glass_card(tr("vrm_card_title", "Natürliche Bewegung (VRM-Avatar)"))
    hint = QtWidgets.QLabel(tr(
        "vrm_card_hint",
        "Der Avatar atmet, blinzelt unregelmäßig, bewegt den Kopf leicht und mischt Gefühle weich ineinander. "
        "Die Gefühle kommen aus dem Text der KI (auch aus Handlungen in *Sternchen*). Pro Charakter einstellbar unter "
        "Charakter-Einstellungen → Visualisierung."))
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    l.addWidget(hint)

    ui.checkBox_vrm_natural = QtWidgets.QCheckBox(tr("vrm_natural_label", "Natürliche Bewegung aktivieren"))
    ui.checkBox_vrm_eye_contact = QtWidgets.QCheckBox(tr("vrm_eye_contact_label", "Augenkontakt (Avatar schaut in die Kamera)"))
    ui.checkBox_vrm_animations = QtWidgets.QCheckBox(tr("vrm_animations_label", "Ganzkörper-Animationen zu Gefühlen abspielen"))
    ui.checkBox_vrm_gestures = QtWidgets.QCheckBox(tr("vrm_gestures_label", "Kleine Idle-Gesten (Kopf anfassen, Haare richten, strecken …)"))
    for cb in (ui.checkBox_vrm_natural, ui.checkBox_vrm_eye_contact, ui.checkBox_vrm_animations, ui.checkBox_vrm_gestures):
        cb.setFont(font_input)
        cb.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        l.addWidget(cb)

    ui.vrm_sliders = {}
    rows = (
        ("vrm_intensity", tr("vrm_intensity_label", "Stärke der Gefühle"), 30, 150, "%"),
        ("vrm_idle", tr("vrm_idle_label", "Atmen / Kopfbewegung"), 0, 100, "%"),
        ("vrm_blink", tr("vrm_blink_label", "Blinzelhäufigkeit"), 40, 200, "%"),
        ("vrm_hold", tr("vrm_hold_label", "Gefühl halten, dann entspannen"), 5, 60, " s"),
    )
    form = QtWidgets.QFormLayout()
    form.setVerticalSpacing(14)
    form.setHorizontalSpacing(24)
    for key, label, lo, hi, unit in rows:
        row = QtWidgets.QHBoxLayout()
        slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        slider.setRange(lo, hi)
        slider.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
        value = QtWidgets.QLabel("")
        value.setFixedWidth(56)
        value.setStyleSheet("color: #F1E8F6; border: none; background: transparent;")
        row.addWidget(slider, 1)
        row.addWidget(value)
        lab = QtWidgets.QLabel(label)
        lab.setFont(font_label)
        form.addRow(lab, row)
        ui.vrm_sliders[key] = (slider, value, unit)
    l.addLayout(form)
    ui.vrm_settings_controller = VrmSettingsController(ui)
    return card


class VrmSettingsController(QtCore.QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.signals = None
        self._loading = True
        for cb, key in ((ui.checkBox_vrm_natural, "vrm_natural"), (ui.checkBox_vrm_eye_contact, "vrm_eye_contact"),
                        (ui.checkBox_vrm_animations, "vrm_animations"), (ui.checkBox_vrm_gestures, "vrm_gestures")):
            cb.toggled.connect(lambda v, k=key: self._save(k, bool(v)))
        for key, (slider, label, unit) in ui.vrm_sliders.items():
            slider.valueChanged.connect(lambda v, k=key: self._slider(k, v))

    def attach(self, signals):
        self.signals = signals
        s = signals.configuration_settings
        opts = vrm_options(s)
        self._loading = True
        self.ui.checkBox_vrm_natural.setChecked(bool(opts["vrm_natural"]))
        self.ui.checkBox_vrm_eye_contact.setChecked(bool(opts["vrm_eye_contact"]))
        self.ui.checkBox_vrm_animations.setChecked(bool(opts["vrm_animations"]))
        self.ui.checkBox_vrm_gestures.setChecked(bool(opts["vrm_gestures"]))
        for key, (slider, label, unit) in self.ui.vrm_sliders.items():
            slider.setValue(int(opts[key]))
            label.setText(f"{int(opts[key])}{unit}")
        self._loading = False

    def _slider(self, key, value):
        slider, label, unit = self.ui.vrm_sliders[key]
        label.setText(f"{value}{unit}")
        self._save(key, int(value))

    def _save(self, key, value):
        if self._loading or self.signals is None:
            return
        self.signals.configuration_settings.update_main_setting(key, value)
        self.push_to_views()

    def push_to_views(self):
        """Apply the options to any VRM view that is currently running."""
        s = self.signals
        views = []
        view = getattr(s, "vrm_webview", None)
        if view is not None:
            views.append(view)
        sow = getattr(s, "sow_system", None) or s
        for holder in (sow, getattr(sow, "vrm_no_gui", None)):
            v = getattr(holder, "vrm_webview", None) if holder is not None else None
            if v is not None and v not in views:
                views.append(v)
        js = options_js(s.configuration_settings)
        for v in views:
            try:
                v.page().runJavaScript(js)
            except Exception:
                logger.debug("VRM view not ready for options", exc_info=True)
