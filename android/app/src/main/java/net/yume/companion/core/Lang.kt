package net.yume.companion.core

import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import java.util.Locale

/**
 * Language of the app. "auto" follows the phone (German phones: German, every other phone: English);
 * the user can force "de" or "en" in the settings. The choice is a Compose state, so the screens update at once.
 */
object Lang {
    private var choice by mutableStateOf("auto")

    /** reads the saved choice (call once at start, after Prefs.init) */
    fun load() { choice = Prefs.uiLang }

    fun set(value: String) { Prefs.uiLang = value; choice = value }

    /** "auto", "de" or "en" */
    val current: String get() = choice

    val isEn: Boolean
        get() = when (choice) {
            "en" -> true
            "de" -> false
            else -> Locale.getDefault().language != "de"
        }

    val code: String get() = if (isEn) "en" else "de"

    /** default language for speech recognition / wake word: the language of the phone if the app has a model for it */
    fun defaultSpeechLanguage(): String = if (Locale.getDefault().language == "de") "de" else "en"
}

/** German text, English text: returns the one that matches the app language */
fun tr(de: String, en: String): String = if (Lang.isEn) en else de
