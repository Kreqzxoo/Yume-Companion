"""LLM setting: "plain spoken text only" - the model is told to answer with just what the character says (no quotation marks,
no *actions*, no narration). Much shorter answers, so generation is clearly faster. Applied in the prompt engine."""
from __future__ import annotations

import logging

from PyQt6 import QtCore, QtWidgets

logger = logging.getLogger("PlainTextMode")
KEY = "llm_plain_text_only"


def build_plain_text_row(ui, font_input):
    tr = ui.translations.get
    box = QtWidgets.QWidget()
    lay = QtWidgets.QVBoxLayout(box)
    lay.setContentsMargins(0, 8, 0, 0)
    lay.setSpacing(4)
    ui.checkBox_llm_plain_text = QtWidgets.QCheckBox(tr("llm_plain_text_label", "Nur normalen, gesprochenen Text generieren (ohne Anführungszeichen, *Handlungen* und Beschreibungen)"))
    ui.checkBox_llm_plain_text.setFont(font_input)
    ui.checkBox_llm_plain_text.setFocusPolicy(QtCore.Qt.FocusPolicy.NoFocus)
    hint = QtWidgets.QLabel(tr("llm_plain_text_hint", "Die KI antwortet nur noch mit dem, was die Figur sagt – kurz und ohne Erzähltext. Dadurch wird deutlich weniger erzeugt und die Antwort ist schneller da. Gilt für alle Charaktere."))
    hint.setWordWrap(True)
    hint.setStyleSheet("color: #B9A9C9; border: none; background: transparent;")
    lay.addWidget(ui.checkBox_llm_plain_text)
    lay.addWidget(hint)
    ui.plain_text_controller = PlainTextController(ui)
    return box


class PlainTextController(QtCore.QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.signals = None
        self._loading = True
        ui.checkBox_llm_plain_text.toggled.connect(self._toggled)

    def attach(self, signals):
        self.signals = signals
        self._loading = True
        self.ui.checkBox_llm_plain_text.setChecked(bool(signals.configuration_settings.get_main_setting(KEY)))
        self._loading = False

    def _toggled(self, value):
        if not self._loading and self.signals is not None:
            self.signals.configuration_settings.update_main_setting(KEY, bool(value))
