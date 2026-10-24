package net.yume.companion.device

import net.yume.companion.core.tr

import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import net.yume.companion.App
import net.yume.companion.core.Lang
import net.yume.companion.core.Prefs
import org.json.JSONObject
import java.util.Calendar
import java.util.Locale

/**
 * Quick commands that work WITHOUT the PC (and without any language model): music, flashlight, apps, timer, alarm, volume, navigation,
 * reading notifications, time, battery, calls. Used when the PC is not reachable (chat and voice). Same idea as the PC's quick commands.
 */
object QuickCommands {
    class Cmd(val label: String, val run: suspend () -> String)

    private val POLITE = setOf("bitte", "mal", "mir", "doch", "jetzt", "eben", "kannst", "könntest", "du", "würdest", "hey", "ok", "okay", "danke", "schnell", "einfach")
    private val POLITE_EN = setOf("please", "can", "could", "you", "would", "hey", "ok", "okay", "thanks", "just", "now", "quickly", "me", "for", "yume")
    private val MUSIC =setOf("musik", "spotify", "song", "songs", "lied", "titel", "track")
    private val PAUSE = setOf("stopp", "stoppe", "stoppen", "stop", "pause", "pausiere", "pausieren", "aus", "ausmachen", "ausschalten", "anhalten", "halt")
    private val RESUME = setOf("weiter", "weiterspielen", "fortsetzen", "an", "wieder", "anmachen", "einschalten")
    private val NEXT = setOf("nächster", "nächste", "nächstes", "skip", "überspring", "überspringe", "überspringen", "next")
    private val PREV = setOf("vorheriger", "vorherige", "vorheriges", "zurück", "previous", "letzter", "letzte", "letztes")

    private fun clean(text: String): String = text.lowercase(Locale.GERMAN).replace(Regex("[^\\p{L}\\p{N}\\s:]"), " ").split(Regex("\\s+")).filter { it.isNotEmpty() }.joinToString(" ")

    private suspend fun phone(action: String, p: JSONObject = JSONObject()): String {
        val r = CommandExecutor.execute(action, p)
        return if (r.optBoolean("ok")) (r.optString("data").ifEmpty { tr("Erledigt.", "Done.") }) else (r.optString("error").ifEmpty { tr("Das hat nicht geklappt.", "That did not work.") })
    }

    /** interpreter mode: the command that starts / ends it, and - while it is on - everything you say is translated */
    fun detectInterpreter(text: String): Cmd? {
        val raw = text.trim()
        if (raw.isEmpty()) return null
        val low = clean(raw)
        if (Interpreter.active) {
            if (Regex("^interpreter\\s+(?:off|end|stop)$|^(?:stop|end)\\s+(?:the\\s+)?(?:interpreter|translating)$|^(?:dolmetscher|dolmetschen|übersetzer)\\s+(?:aus|ende|beenden|stopp)$|^(?:hör|hoer)\\s+auf\\s+zu\\s+(?:dolmetschen|übersetzen)$|^stopp\\s+(?:dolmetschen|dolmetscher)$").containsMatchIn(low))
                return Cmd(tr("Beende den Dolmetscher …", "Ending the interpreter …")) { Interpreter.stop() }
            return Cmd(tr("Übersetze …", "Translating …")) { Interpreter.run(raw) }
        }
        if (Regex("^(?:interpreter|translator)\\b|^translate\\s+(?:everything\\s+)?(?:in)?to\\s+\\w+").containsMatchIn(low)) {
            val lang = Interpreter.languageIn(low)
            if (lang != null) return Cmd(tr("Starte den Dolmetscher …", "Starting the interpreter …")) { Interpreter.start(lang) }
        }
        if (Regex("^(?:dolmetscher|dolmetschen|übersetzer|übersetze\\s+(?:alles|das|mir)?)\\b").containsMatchIn(low) || Regex("übersetze\\s+(?:alles\\s+)?(?:ins|auf|in)\\s+\\w+").containsMatchIn(low)) {
            val lang = Interpreter.languageIn(low)
            if (lang != null) return Cmd(tr("Starte den Dolmetscher …", "Starting the interpreter …")) { Interpreter.start(lang) }
        }
        return null
    }

    fun detect(text: String): Cmd? {
        detectInterpreter(text)?.let { return it }
        return detectDe(text) ?: detectEn(text)
    }

    /** the same quick commands in English */
    private fun detectEn(text: String): Cmd? {
        val raw = text.trim()
        Regex("^(?:reply|answer|write back|tell (?:him|her|them))\\s*[:,]?\\s+(.{2,300})$", RegexOption.IGNORE_CASE).find(raw)?.let { m ->
            val reply = m.groupValues[1].trim()
            return Cmd(tr("Antworte auf die Nachricht …", "Replying to the message …")) { phone("reply_message", JSONObject().put("text", reply)) }
        }
        if (raw.isEmpty() || raw.length > 90) return null
        val sentence = clean(raw)
        val words = sentence.split(" ").filter { it !in POLITE_EN }
        if (words.isEmpty() || words.size > 10) return null
        val ws = words.toSet()
        val joined = words.joinToString(" ")
        val music = ws.any { it in setOf("music", "spotify", "song", "songs", "track") }
        if (ws.any { it in setOf("pc", "computer", "laptop") }) return null

        if (Spotify.connected) {
            Regex("^(?:play|start)\\s+(?:the\\s+)?(?:playlist\\s+)?(.+)$").find(joined)?.let { m ->
                val q = m.groupValues[1].replace(Regex("\\s+on\\s+(?:my\\s+)?(?:phone|spotify)$"), "").trim()
                if (q.isNotEmpty() && q !in setOf("music", "something", "anything", "again") && !q.startsWith("the next") && !q.endsWith(" on")) {
                    val kind = if (joined.contains("playlist")) "playlist" else "track"
                    return Cmd(tr("Spiele „$q“ …", "Playing “$q” …")) { Spotify.play(q, kind) }
                }
            }
            if (Regex("what(?: s| is)? (?:playing|this song)|which (?:song|track) is (?:this|playing)").containsMatchIn(joined)) return Cmd(tr("Prüfe, was läuft …", "Checking what is playing …")) { Spotify.now() }
            if (ws.any { it in setOf("next", "skip") } && (music || words.size <= 2)) return Cmd(tr("Nächster Titel …", "Next track …")) { Spotify.control("next") }
            if (ws.any { it in setOf("previous", "back") } && (music || words.size <= 2)) return Cmd(tr("Voriger Titel …", "Previous track …")) { Spotify.control("previous") }
            if (ws.any { it in setOf("pause", "stop") } && (music || ws.size == 1) && !Regex("\\d").containsMatchIn(raw)) return Cmd(tr("Pausiere die Musik …", "Pausing the music …")) { Spotify.control("pause") }
            if (ws == setOf("resume") || ws == setOf("continue") || (music && ws.any { it in setOf("resume", "continue") })) return Cmd(tr("Setze die Musik fort …", "Resuming the music …")) { Spotify.control("resume") }
        }
        if ("flashlight" in ws || "torch" in ws) {
            val on = ws.none { it in setOf("off", "disable") }
            return Cmd(tr("Schalte die Taschenlampe …", "Switching the flashlight …")) { phone("flashlight", JSONObject().put("on", on)) }
        }
        Regex("^(?:volume\\s+)?(up|down)$|^(?:turn|make|put)\\s+(?:the\\s+)?(?:music\\s+|volume\\s+)?(up|down)$|^(louder|quieter)$|^(?:turn\\s+)?(?:the\\s+)?(?:music\\s+)?(louder|quieter)$").find(joined)?.let {
            val up = joined.contains("up") || joined.contains("louder")
            return Cmd(if (up) tr("Lauter …", "Louder …") else tr("Leiser …", "Quieter …")) { adjustVolume(up) }
        }
        Regex("^(?:set\\s+)?volume\\s+(?:to\\s+)?(\\d{1,3})(?:\\s*(?:percent|%))?$").find(joined)?.let { m ->
            val level = m.groupValues[1].toInt().coerceIn(0, 100)
            return Cmd(tr("Stelle die Lautstärke auf $level % …", "Setting the volume to $level % …")) { phone("volume", JSONObject().put("level", level)) }
        }
        Regex("timer\\s+(?:for|of)?\\s*(\\d{1,3})\\s*(seconds?|minutes?|hours?|secs?|mins?)").find(joined)?.let { m ->
            val n = m.groupValues[1].toInt()
            val unit = m.groupValues[2]
            val seconds = when { unit.startsWith("sec") -> n; unit.startsWith("min") -> n * 60; else -> n * 3600 }
            return Cmd(tr("Stelle den Timer …", "Setting the timer …")) { phone("set_timer", JSONObject().put("seconds", seconds)) }
        }
        if (Regex("alarm|\\bwake\\b").containsMatchIn(joined)) {
            Regex("(\\d{1,2})(?::(\\d{2}))?\\s*(am|pm)?").find(joined)?.let { m ->
                var h = m.groupValues[1].toInt()
                val min = m.groupValues[2].toIntOrNull() ?: 0
                when (m.groupValues[3]) { "pm" -> if (h < 12) h += 12; "am" -> if (h == 12) h = 0 }
                if (h in 0..23 && min in 0..59) {
                    val day = if (joined.contains("tomorrow")) "tomorrow" else ""
                    return Cmd(tr("Stelle den Wecker …", "Setting the alarm …")) { phone("alarm_set", JSONObject().put("hour", h).put("minute", min).put("day", day)) }
                }
            }
        }
        Regex("^(?:navigate|directions|route|take me|drive|bring me)\\s+(?:me\\s+)?(?:to|home)\\s*(.*)$").find(joined)?.let { m ->
            val dest = m.groupValues[1].ifEmpty { "home" }
            return Cmd(tr("Starte die Navigation …", "Starting navigation …")) { navigate(dest) }
        }
        if (Regex("read (?:me )?(?:my )?(?:new )?(?:messages|notifications)|do i have (?:any )?new messages|any new messages|what s new").containsMatchIn(joined))
            return Cmd(tr("Lese deine Nachrichten …", "Reading your messages …")) { phone("notifications") }
        if (Regex("what time|current time|time is it").containsMatchIn(joined)) return Cmd(tr("Schaue auf die Uhr …", "Looking at the clock …")) { timeText() }
        if (Regex("what day|what date|today s date|date today").containsMatchIn(joined)) return Cmd(tr("Schaue in den Kalender …", "Looking at the calendar …")) { dateText() }
        if (Regex("battery").containsMatchIn(joined) && words.size <= 6) return Cmd(tr("Prüfe den Akku …", "Checking the battery …")) { phone("battery") }
        Regex("^(?:call|phone|ring)\\s+(.+)$").find(joined)?.let { m ->
            val who = m.groupValues[1]
            return Cmd(tr("Rufe $who an …", "Calling $who …")) { phone("call", JSONObject().put("number", who)) }
        }
        Regex("^(?:open|launch|start)\\s+(?:the\\s+)?(?:app\\s+)?(.+?)(?:\\s+(?:app|on\\s+(?:my\\s+)?phone))?$").find(joined)?.let { m ->
            val name = m.groupValues[1].trim()
            if (name.isNotEmpty() && name.split(" ").size <= 3 && name.split(" ").none { it in setOf("music", "folder", "file", "window", "program", "light", "lamp") } && !Regex("\\d").containsMatchIn(name))
                return Cmd(tr("Öffne $name …", "Opening $name …")) { phone("open_app", JSONObject().put("app", name)) }
        }
        return null
    }

    private fun detectDe(text: String): Cmd? {
        val raw = text.trim()
        // "antworte ich bin gleich da": answers the latest message (WhatsApp etc.) through the notification's reply action
        Regex("^(?:antworte|antwort|schreib(?:e)?\\s+(?:(?:ihm|ihr|denen)\\s+)?zurück|schreib(?:e)?\\s+(?:ihm|ihr|denen)|sag(?:e)?\\s+(?:ihm|ihr|denen))\\s*[:,]?\\s+(.{2,300})$", RegexOption.IGNORE_CASE).find(raw)?.let { m ->
            val reply = m.groupValues[1].trim()
            return Cmd(tr("Antworte auf die Nachricht …", "Replying to the message …")) { phone("reply_message", JSONObject().put("text", reply)) }
        }
        if (raw.isEmpty() || raw.length > 90) return null
        val sentence = clean(raw)
        val words = sentence.split(" ").filter { it !in POLITE }
        if (words.isEmpty() || words.size > 9) return null
        val ws = words.toSet()
        val music = ws.any { it in MUSIC }
        val joined = words.joinToString(" ")
        if (ws.any { it in setOf("pc", "computer", "rechner", "laptop") }) return null     // meant for the PC

        // ---------------------------------------------------------------- Spotify (own login of the phone; needs internet, not the PC)
        if (Spotify.connected) {
            Regex("^(?:spiel|spiele|starte|spielt)\\s+(?:mir\\s+)?(?:die\\s+playlist\\s+)?(.+)$").find(joined)?.let { m ->
                val q = m.groupValues[1].replace(Regex("\\s+auf\\s+(?:dem\\s+|meinem\\s+)?(?:handy|smartphone|spotify)$"), "").trim()
                if (q.isNotEmpty() && q !in setOf("weiter", "musik", "was", "etwas", "irgendwas") && !q.startsWith("weiter") && !q.endsWith(" an")) {
                    val kind = if (joined.contains("playlist")) "playlist" else "track"
                    return Cmd(tr("Spiele „$q“ …", "Playing “$q” …")) { Spotify.play(q, kind) }
                }
            }
            if (Regex("was (?:läuft|spielt)|welch\\w* (?:song|lied|titel) (?:läuft|ist das)").containsMatchIn(joined)) return Cmd(tr("Prüfe, was läuft …", "Checking what is playing …")) { Spotify.now() }
            if ((music || words.size == 1) && ws.any { it in NEXT } && ws.none { it in PAUSE }) return Cmd(tr("Nächster Titel …", "Next track …")) { Spotify.control("next") }
            if (ws.any { it in PREV } && (music || ws.any { it.startsWith("vorherige") }) && words.size <= 4) return Cmd(tr("Voriger Titel …", "Previous track …")) { Spotify.control("previous") }
            if ((music || ws == setOf("pause")) && ws.any { it in PAUSE } && ws.none { it in setOf("weiter", "wieder", "an", "starte", "spiele", "spiel") } && !Regex("\\d").containsMatchIn(raw))
                return Cmd(tr("Pausiere die Musik …", "Pausing the music …")) { Spotify.control("pause") }
            if (((music && ws.any { it in RESUME }) || ws.any { it == "weiterspielen" || it == "fortsetzen" } || ws == setOf("weiter") || ws == setOf("spiel", "weiter")) && ws.none { it in PAUSE })
                return Cmd(tr("Setze die Musik fort …", "Resuming the music …")) { Spotify.control("resume") }
        }

        // ---------------------------------------------------------------- phone
        if ("taschenlampe" in ws) {
            val on = ws.none { it in setOf("aus", "ausmachen", "ausschalten", "off") }
            return Cmd(tr("Schalte die Taschenlampe …", "Switching the flashlight …")) { phone("flashlight", JSONObject().put("on", on)) }
        }
        Regex("^(?:lauter|leiser)$|^(?:musik|handy)\\s+(lauter|leiser)$|^(?:mach\\w*\\s+)?(?:die\\s+)?(?:musik\\s+)?(lauter|leiser)$").find(joined)?.let {
            val up = joined.contains("lauter")
            return Cmd(if (up) tr("Lauter …", "Louder …") else tr("Leiser …", "Quieter …")) { adjustVolume(up) }
        }
        Regex("^lautstärke\\s+(?:auf\\s+)?(\\d{1,3})(?:\\s*prozent)?$").find(joined)?.let { m ->
            val level = m.groupValues[1].toInt().coerceIn(0, 100)
            return Cmd(tr("Stelle die Lautstärke auf $level % …", "Setting the volume to $level % …")) { phone("volume", JSONObject().put("level", level)) }
        }
        Regex("timer\\s+(?:auf|für|von)?\\s*(\\d{1,3})\\s*(sekunden?|minuten?|stunden?|min|std|sek)").find(joined)?.let { m ->
            val n = m.groupValues[1].toInt()
            val unit = m.groupValues[2]
            val seconds = when { unit.startsWith("sek") -> n; unit.startsWith("min") -> n * 60; else -> n * 3600 }
            return Cmd(tr("Stelle den Timer …", "Setting the timer …")) { phone("set_timer", JSONObject().put("seconds", seconds)) }
        }
        if (Regex("wecker|weck mich").containsMatchIn(joined)) {
            Regex("(\\d{1,2})(?::(\\d{2}))?\\s*(?:uhr)?").find(joined)?.let { m ->
                val h = m.groupValues[1].toInt()
                val min = m.groupValues[2].toIntOrNull() ?: 0
                if (h in 0..23 && min in 0..59) {
                    val day = if (joined.contains("morgen")) "tomorrow" else ""
                    return Cmd(tr("Stelle den Wecker …", "Setting the alarm …")) { phone("alarm_set", JSONObject().put("hour", h).put("minute", min).put("day", day)) }
                }
            }
        }
        Regex("^(?:navigiere|navigation|route|fahr|fahre|bring|führ|führe)\\s+(?:mich\\s+)?(?:nach|zu|zum|zur)\\s+(.+)$").find(joined)?.let { m ->
            val dest = m.groupValues[1]
            return Cmd(tr("Starte die Navigation …", "Starting navigation …")) { navigate(dest) }
        }
        if (Regex("(?:lies|lese|les)\\s+(?:mir\\s+)?(?:meine\\s+)?(?:neuen\\s+)?nachrichten(?:\\s+vor)?|habe ich neue nachrichten|was gibt es neues").containsMatchIn(joined))
            return Cmd(tr("Lese deine Nachrichten …", "Reading your messages …")) { phone("notifications") }
        if (Regex("wie spät|wie viel uhr|wieviel uhr|uhrzeit").containsMatchIn(joined)) return Cmd(tr("Schaue auf die Uhr …", "Looking at the clock …")) { timeText() }
        if (Regex("welcher tag|welches datum|welchen tag|datum heute").containsMatchIn(joined)) return Cmd(tr("Schaue in den Kalender …", "Looking at the calendar …")) { dateText() }
        if (Regex("akku|batterie").containsMatchIn(joined) && words.size <= 5) return Cmd(tr("Prüfe den Akku …", "Checking the battery …")) { phone("battery") }
        Regex("^(?:ruf|rufe)\\s+(.+?)\\s+an$").find(joined)?.let { m ->
            val who = m.groupValues[1]
            return Cmd(tr("Rufe $who an …", "Calling $who …")) { phone("call", JSONObject().put("number", who)) }
        }
        val openMatch = Regex("^(?:öffne|öffnen|starte|starten|open)\\s+(?:die\\s+|den\\s+|das\\s+)?(?:app\\s+)?(.+?)(?:\\s+(?:auf|am)\\s+(?:dem\\s+|meinem\\s+)?(?:handy|smartphone))?$").find(joined)
            ?: Regex("^(?:die\\s+|den\\s+|das\\s+)?(?:app\\s+)?(.+?)\\s+(?:öffnen|starten)(?:\\s+(?:auf|am)\\s+(?:dem\\s+|meinem\\s+)?(?:handy|smartphone))?$").find(joined)
        if (openMatch != null) {
            val name = openMatch.groupValues[1].trim()
            if (name.isNotEmpty() && name.split(" ").size <= 3 && name.split(" ").none { it in setOf("musik", "ordner", "datei", "fenster", "programm", "licht", "lampe") } && !Regex("\\d").containsMatchIn(name))
                return Cmd(tr("Öffne $name …", "Opening $name …")) { phone("open_app", JSONObject().put("app", name)) }
        }
        return null
    }

    private fun adjustVolume(up: Boolean): String {
        val am = App.instance.getSystemService(AudioManager::class.java)
        repeat(2) { am.adjustStreamVolume(AudioManager.STREAM_MUSIC, if (up) AudioManager.ADJUST_RAISE else AudioManager.ADJUST_LOWER, AudioManager.FLAG_SHOW_UI) }
        val max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC).coerceAtLeast(1)
        return tr("Lautstärke jetzt ", "Volume now ") + (100 * am.getStreamVolume(AudioManager.STREAM_MUSIC) / max) + " %."
    }

    private fun navigate(dest: String): String = try {
        val maps = Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=" + Uri.encode(dest))).setPackage("com.google.android.apps.maps").addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        val ctx = App.instance
        if (maps.resolveActivity(ctx.packageManager) != null) ctx.startActivity(maps)
        else ctx.startActivity(Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=" + Uri.encode(dest))).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        tr("Navigation nach $dest gestartet.", "Navigation to $dest started.")
    } catch (e: Exception) { tr("Die Navigation konnte nicht gestartet werden: ${e.message}", "Navigation could not be started: ${e.message}") }

    private fun timeText(): String = Calendar.getInstance().let { tr("Es ist %d:%02d Uhr.", "It is %d:%02d.").format(it.get(Calendar.HOUR_OF_DAY), it.get(Calendar.MINUTE)) }

    private fun dateText(): String = java.text.SimpleDateFormat(tr("EEEE, d. MMMM yyyy", "EEEE, MMMM d, yyyy"), if (Lang.isEn) Locale.ENGLISH else Locale.GERMAN).format(java.util.Date()).let { tr("Heute ist $it.", "Today is $it.") }
}
