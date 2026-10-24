"""Setting: language of the speech recognition. "Auto" lets Whisper guess for every sentence - short German sentences are then often taken
for another language. A fixed language is noticeably more reliable."""
from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

KEY = "stt_language"
LANGUAGES = [("auto", "Automatisch erkennen"), ("de", "Deutsch"), ("en", "English"), ("ru", "Русский"), ("fr", "Français"),
             ("es", "Español"), ("it", "Italiano"), ("pl", "Polski"), ("nl", "Nederlands"), ("tr", "Türkçe"), ("ja", "日本語"), ("zh", "中文")]


def build_stt_language_row(ui, font_input, audio_form):
    tr = ui.translations.get
    ui.comboBox_stt_language = QtWidgets.QComboBox()
    ui.comboBox_stt_language.setFont(font_input)
    ui.comboBox_stt_language.setFixedHeight(40)
    ui.comboBox_stt_language.setToolTip(tr("stt_language_tooltip", "Feste Sprache ist zuverlässiger als „Automatisch“ - besonders bei kurzen Sätzen."))
    for code, label in LANGUAGES:
        ui.comboBox_stt_language.addItem(tr("stt_language_auto", label) if code == "auto" else label, code)
    audio_form.addRow(tr("stt_language_label", "Sprache der Spracherkennung"), ui.comboBox_stt_language)
    ui.stt_language_controller = SttLanguageController(ui)


class SttLanguageController(QtCore.QObject):
    def __init__(self, ui):
        super().__init__()
        self.ui = ui
        self.signals = None
        self._loading = True
        ui.comboBox_stt_language.currentIndexChanged.connect(self._changed)

    def attach(self, signals):
        self.signals = signals
        self._loading = True
        value = str(signals.configuration_settings.get_main_setting(KEY) or "auto")
        self.ui.comboBox_stt_language.setCurrentIndex(max(0, self.ui.comboBox_stt_language.findData(value)))
        self._loading = False

    def _changed(self, _index):
        if not self._loading and self.signals is not None:
            self.signals.configuration_settings.update_main_setting(KEY, self.ui.comboBox_stt_language.currentData())
