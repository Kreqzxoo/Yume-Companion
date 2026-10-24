package net.yume.companion.device

import net.yume.companion.core.Host
import net.yume.companion.core.Prefs
import net.yume.companion.voice.PhoneTts
import org.json.JSONObject
import java.util.Locale

/**
 * Interpreter mode: everything you say (or type) is translated by the PC's language model and spoken by the phone in the other language.
 * "Dolmetscher Englisch" starts it, "Dolmetscher aus" ends it. One direction (your language -> the target language).
 */
object Interpreter {
    @Volatile var active = false
        private set
    @Volatile var targetName = ""
        private set
    @Volatile private var locale: Locale = Locale.ENGLISH

    private val LANGS = mapOf(
        "englisch" to Triple("English", "en-US", "Englisch"), "französisch" to Triple("French", "fr-FR", "Französisch"), "spanisch" to Triple("Spanish", "es-ES", "Spanisch"),
        "italienisch" to Triple("Italian", "it-IT", "Italienisch"), "türkisch" to Triple("Turkish", "tr-TR", "Türkisch"), "polnisch" to Triple("Polish", "pl-PL", "Polnisch"),
        "niederländisch" to Triple("Dutch", "nl-NL", "Niederländisch"), "holländisch" to Triple("Dutch", "nl-NL", "Niederländisch"), "portugiesisch" to Triple("Portuguese", "pt-PT", "Portugiesisch"),
        "russisch" to Triple("Russian", "ru-RU", "Russisch"), "japanisch" to Triple("Japanese", "ja-JP", "Japanisch"), "griechisch" to Triple("Greek", "el-GR", "Griechisch"),
        "schwedisch" to Triple("Swedish", "sv-SE", "Schwedisch"), "dänisch" to Triple("Danish", "da-DK", "Dänisch"), "kroatisch" to Triple("Croatian", "hr-HR", "Kroatisch"),
        "tschechisch" to Triple("Czech", "cs-CZ", "Tschechisch"), "rumänisch" to Triple("Romanian", "ro-RO", "Rumänisch"), "ungarisch" to Triple("Hungarian", "hu-HU", "Ungarisch"),
        "arabisch" to Triple("Arabic", "ar-SA", "Arabisch"), "chinesisch" to Triple("Chinese", "zh-CN", "Chinesisch"), "koreanisch" to Triple("Korean", "ko-KR", "Koreanisch"),
    )
    private val STEM = LANGS.keys.associateBy { it.removeSuffix("isch") }          // "englisch" -> "engl": "ins Englische", "auf Englisch"

    fun languageIn(text: String): String? {
        val t = text.lowercase(Locale.GERMAN)
        return LANGS.keys.firstOrNull { t.contains(it) } ?: STEM.entries.firstOrNull { t.contains(it.key) && it.key.length >= 4 }?.value
    }

    fun start(langKey: String): String {
        val (name, tag, label) = LANGS[langKey] ?: return "Diese Sprache kenne ich nicht."
        targetName = name; locale = Locale.forLanguageTag(tag); active = true
        return "Dolmetscher an: alles, was du sagst, übersage ich auf $label. Zum Beenden sag „Dolmetscher aus“."
    }

    fun stop(): String { active = false; return "Dolmetscher aus." }

    /** translated text (null when the PC cannot be reached) */
    fun translate(text: String): String? {
        val r = Host.postJson("/api/translate", JSONObject().put("text", text).put("target", targetName).put("character", Prefs.character)) ?: return null
        return r.optString("text").takeIf { r.optBoolean("ok") && it.isNotEmpty() }
    }

    /** translates, speaks the translation in the target language and returns it for the screen */
    suspend fun run(text: String): String {
        val out = translate(text) ?: return "Die Übersetzung braucht den PC – er ist gerade nicht erreichbar."
        PhoneTts.speakIn(locale, out)
        return out
    }
}
