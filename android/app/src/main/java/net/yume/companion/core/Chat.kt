package net.yume.companion.core

import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.setValue
import kotlinx.coroutines.*
import net.yume.companion.offline.OfflineChat
import org.json.JSONObject

data class Msg(val id: String, val mine: Boolean, val text: String, val streaming: Boolean = false, val time: Long = System.currentTimeMillis()) {
    /** "14:05" like in WhatsApp */
    fun clock(): String = java.text.SimpleDateFormat("HH:mm", java.util.Locale.getDefault()).format(java.util.Date(time))
}

/** Time stamp of the PC ("2026-10-18T14:03:22.123456", PC local time) -> epoch millis; now when it can't be read. */
internal fun parseHostTime(s: String): Long = try {
    java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss", java.util.Locale.US).parse(s.take(19))!!.time
} catch (_: Exception) { System.currentTimeMillis() }

/** The chat of the active character: history from the PC, live stream (chunks) while she answers, sending. */
object ChatRepo {
    val msgs = mutableStateListOf<Msg>()
    var generating by mutableStateOf(false)
        private set
    var loading by mutableStateOf(false)
        private set
    var loadedFor = ""
        private set
    /** false while the PC's own web page (Live2D) plays the voice itself - otherwise it would be heard twice */
    @Volatile var nativeVoice = true
    /** after hanging up, speech that was already on its way is thrown away */
    @Volatile var muteUntil = 0L

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var started = false
    private var counter = 0L
    private fun nextId() = "local" + (counter++)

    fun start() {
        if (started) return
        started = true
        scope.launch {
            HostLink.events.collect { j -> handle(j) }
        }
    }

    private fun handle(j: JSONObject) {
        when (j.optString("type")) {
            "user_message" -> {
                val text = j.optString("text")
                if (text.isNotBlank() && !(msgs.lastOrNull()?.let { it.mine && it.text == text } ?: false)) msgs.add(Msg(nextId(), true, text))
            }
            "message_start" -> { generating = true; msgs.add(Msg(nextId(), false, "", true)) }
            "chunk" -> {
                generating = true
                val last = msgs.lastOrNull()
                if (last == null || last.mine || !last.streaming) msgs.add(Msg(nextId(), false, j.optString("text"), true))
                else msgs[msgs.lastIndex] = last.copy(text = last.text + j.optString("text"))
            }
            "message_end" -> {
                generating = false
                val last = msgs.lastOrNull()
                if (last != null && last.streaming) msgs[msgs.lastIndex] = last.copy(streaming = false)
                if (msgs.lastOrNull()?.text?.isBlank() == true) msgs.removeAt(msgs.lastIndex)
            }
            "audio" -> if (nativeVoice && Prefs.chatVoice && System.currentTimeMillis() > muteUntil && !net.yume.companion.voice.CallEngine.wantCall) {
                try { net.yume.companion.voice.AudioPlayer.enqueue(android.util.Base64.decode(j.optString("data"), android.util.Base64.DEFAULT)) } catch (_: Exception) {}
            }
            "message_deleted" -> msgs.removeAll { it.id == j.optString("id") }
            "message_edited" -> {
                val i = msgs.indexOfFirst { it.id == j.optString("id") }
                if (i >= 0) msgs[i] = msgs[i].copy(text = j.optString("text"))
            }
            "character_changed" -> scope.launch { load(j.optString("character"), force = true) }
        }
    }

    /** Loads the latest messages of [character] from the PC (or the synced copy while the PC is away). */
    suspend fun load(character: String, force: Boolean = false) {
        if (character.isEmpty()) return
        if (!force && loadedFor == character && msgs.isNotEmpty()) return
        loading = true
        val list = withContext(Dispatchers.IO) {
            val online = Host.baseUrl.isNotEmpty() && HostLink.connected
            val j = if (online) Host.getJson("/api/history/" + java.net.URLEncoder.encode(character, "UTF-8").replace("+", "%20") + "?offset=0&limit=60") else null
            val out = ArrayList<Msg>()
            val arr = j?.optJSONArray("history")
            if (arr != null) {
                for (i in 0 until arr.length()) arr.optJSONObject(i)?.let { out += Msg(it.optString("id"), it.optBoolean("is_user", true), it.optString("text"), time = parseHostTime(it.optString("time"))) }
            } else {
                Sync.load(character)?.optJSONArray("history")?.let { a ->
                    for (i in 0 until a.length()) a.optJSONObject(i)?.let { out += Msg(nextId(), it.optString("role") == "user", it.optString("text")) }
                }
            }
            out
        }
        msgs.clear(); msgs.addAll(list)
        loadedFor = character
        generating = false
        loading = false
    }

    /** Sends a message: to the PC when connected, otherwise to the offline model on the phone. */
    fun send(text: String) {
        val t = text.trim()
        if (t.isEmpty()) return
        msgs.add(Msg(nextId(), true, t))
        val interp = net.yume.companion.device.QuickCommands.detectInterpreter(t)
        if (interp != null) {
            generating = true
            scope.launch {
                val answer = try { withContext(Dispatchers.IO) { interp.run() } } catch (e: Exception) { tr("Das hat nicht geklappt: ", "That did not work: ") + (e.message ?: "") }
                msgs.add(Msg(nextId(), false, "🌐 " + answer))
                generating = false
            }
        } else if (HostLink.connected) {
            HostLink.sendText(t)
            generating = true
        } else if (net.yume.companion.device.QuickCommands.detect(t) != null) {
            // PC not reachable: clear commands (music, apps, timer, alarm, navigation ...) still work, without any model
            generating = true
            val cmd = net.yume.companion.device.QuickCommands.detect(t)!!
            scope.launch {
                val answer = try { cmd.run() } catch (e: Exception) { tr("Das hat nicht geklappt: ", "That did not work: ") + (e.message ?: "") }
                msgs.add(Msg(nextId(), false, answer))
                if (Prefs.chatVoice) net.yume.companion.voice.PhoneTts.speak(answer)
                generating = false
            }
        } else if (Prefs.offlineEnabled && OfflineChat.ready()) {
            generating = true
            scope.launch {
                val answer = OfflineChat.reply(t)
                OfflineHandover.record(t, answer)
                msgs.add(Msg(nextId(), false, answer))
                generating = false
            }
        } else {
            msgs.add(Msg(nextId(), false, tr("(Der PC ist nicht erreichbar und der Offline-Modus ist nicht eingerichtet.)", "(The PC is not reachable and offline mode is not set up.)")))
        }
    }

    fun stop() {
        scope.launch(Dispatchers.IO) { Host.stopGeneration() }
        net.yume.companion.voice.AudioPlayer.stop()
        generating = false
        val last = msgs.lastOrNull()
        if (last != null && last.streaming) msgs[msgs.lastIndex] = last.copy(streaming = false)
    }
}
