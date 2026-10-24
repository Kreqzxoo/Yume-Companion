"""Per-character reply language: choices, storage helpers and the prompt instruction."""
from __future__ import annotations

# code -> (label shown in the UI, name used inside the instruction)
LANGUAGES = {
    "auto": ("Automatisch (Programmsprache)", ""),
    "de": ("Deutsch", "German"),
    "en": ("English", "English"),
    "ru": ("Русский", "Russian"),
    "ja": ("日本語", "Japanese"),
    "es": ("Español", "Spanish"),
    "fr": ("Français", "French"),
    "it": ("Italiano", "Italian"),
    "pt": ("Português", "Portuguese"),
    "pl": ("Polski", "Polish"),
    "tr": ("Türkçe", "Turkish"),
    "zh": ("中文", "Chinese"),
    "ko": ("한국어", "Korean"),
}
APP_LANG_CODES = {0: "en", 1: "ru", 2: "de"}


def fill_combo(combo, translations=None, current="auto"):
    combo.clear()
    for code, (label, _) in LANGUAGES.items():
        if code == "auto" and translations:
            label = translations.get("character_language_auto", label)
        combo.addItem(label, code)
    idx = combo.findData(current if current in LANGUAGES else "auto")
    combo.setCurrentIndex(max(idx, 0))


def effective_language(code, app_language_index):
    """Resolve 'auto' to the program language; English as app language adds no instruction."""
    code = code if code in LANGUAGES else "auto"
    if code == "auto":
        code = APP_LANG_CODES.get(int(app_language_index or 0), "en")
        return "" if code == "en" else code
    return code


def instruction(code, app_language_index):
    lang = effective_language(code, app_language_index)
    if not lang:
        return ""
    name = LANGUAGES[lang][1]
    return (f"\n\n[REPLY LANGUAGE]\nAlways write every reply, including dialogue and narration, in {name}. "
            f"Only switch language if the user explicitly asks for it.")
