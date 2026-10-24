package net.yume.companion.voice

import net.yume.companion.core.tr

import android.content.Context
import android.media.AudioFormat
import android.media.AudioManager
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.audiofx.AcousticEchoCanceler
import android.media.audiofx.NoiseSuppressor
import android.util.Base64
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import net.yume.companion.core.Host
import net.yume.companion.core.HostLink
import net.yume.companion.core.OfflineHandover
import net.yume.companion.core.Prefs
import net.yume.companion.offline.OfflineChat
import java.io.ByteArrayOutputStream
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.sqrt

object CarMode {
    @Volatile var active = false
}

enum class Phase { IDLE, LISTENING, HEARING, THINKING, SPEAKING }

data class CallUi(
    val active: Boolean = false, val phase: Phase = Phase.IDLE, val level: Float = 0f,
    val heard: String = "", val reply: String = "", val offline: Boolean = false, val seconds: Int = 0, val error: String = "",
)

/**
 * Phone call with the character: continuous microphone, voice activity detection, every utterance goes to the PC
 * (speech recognition + answer), the PC's voice comes back over the WebSocket. Barge-in: speak (or say a stop word)
 * while she talks and she stops. Without a PC connection the offline emergency mode answers instead.
 */
object CallEngine {
    private const val RATE = 16000
    private const val FRAME = 320                       // 20 ms

    private val _ui = MutableStateFlow(CallUi())
    val ui = _ui.asStateFlow()

    @Volatile var wantCall = false
    @Volatile var oneShot = false
    /** assistant panel: one question, one answer (spoken to the end), then the microphone closes again */
    @Volatile var singleTurn = false
    @Volatile private var answered = false
    /** the microphone is already open (set up while the wake greeting plays) but must not hear the greeting itself */
    @Volatile var gate = false
    @Volatile var ready = false
    private fun update(f: (CallUi) -> CallUi) { _ui.value = f(_ui.value) }

    fun request(oneShot: Boolean, car: Boolean = false, single: Boolean = false) {
        this.oneShot = oneShot
        this.singleTurn = single
        CarMode.active = car
        wantCall = true
    }

    fun hangup() { wantCall = false }

    // reply bookkeeping (written from the event collector, read by the audio loop)
    @Volatile private var replyEndedAt = 0L
    @Volatile private var replyStarted = false
    @Volatile private var phase = Phase.IDLE
    private fun setPhase(p: Phase) { phase = p; update { it.copy(phase = p) } }

    suspend fun run(ctx: Context) = coroutineScope {
        val am = ctx.getSystemService(AudioManager::class.java)
        val oldMode = am.mode
        // phone-call audio mode (echo cancelling, telephone sound) only AFTER the wake greeting: it plays in normal media quality
        var modeApplied = false
        fun applyMode() {
            if (modeApplied) return
            modeApplied = true
            AudioPlayer.callMode = true
            am.mode = AudioManager.MODE_IN_COMMUNICATION
            @Suppress("DEPRECATION") run { am.isSpeakerphoneOn = Prefs.speaker }
        }
        if (!gate) applyMode()

        val minBuf = AudioRecord.getMinBufferSize(RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val rec = try {
            AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, RATE, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, FRAME * 2 * 16))
        } catch (e: SecurityException) { update { it.copy(error = tr("Mikrofon-Berechtigung fehlt", "Microphone permission missing")) }; wantCall = false; return@coroutineScope }
        if (rec.state != AudioRecord.STATE_INITIALIZED) { update { it.copy(error = tr("Mikrofon nicht verfügbar", "Microphone not available")) }; rec.release(); wantCall = false; return@coroutineScope }

        var aec: AcousticEchoCanceler? = null
        var ns: NoiseSuppressor? = null
        val haveAec = Prefs.echoCancel && AcousticEchoCanceler.isAvailable()
        if (haveAec) try { aec = AcousticEchoCanceler.create(rec.audioSessionId)?.also { it.enabled = true } } catch (_: Exception) {}
        if (NoiseSuppressor.isAvailable()) try { ns = NoiseSuppressor.create(rec.audioSessionId)?.also { it.enabled = true } } catch (_: Exception) {}

        replyEndedAt = 0; replyStarted = false; answered = false
        update { CallUi(active = true, phase = Phase.LISTENING, offline = !HostLink.connected) }
        setPhase(Phase.LISTENING)
        HostLink.callStart()
        val startedAt = System.currentTimeMillis()

        // events from the PC: streamed text, voice, end of message
        val events = launch {
            HostLink.events.collect { j ->
                when (j.optString("type")) {
                    "message_start" -> { replyStarted = true; replyEndedAt = 0; update { it.copy(reply = "") } }
                    "chunk" -> update { it.copy(reply = (it.reply + j.optString("text")).takeLast(1500)) }
                    "message_end" -> replyEndedAt = System.currentTimeMillis()
                    "audio" -> try {
                        AudioPlayer.enqueue(Base64.decode(j.optString("data"), Base64.DEFAULT))
                        if (phase == Phase.THINKING || phase == Phase.LISTENING) setPhase(Phase.SPEAKING)
                    } catch (_: Exception) {}
                }
            }
        }
        val clock = launch { while (isActive) { delay(1000); update { it.copy(seconds = ((System.currentTimeMillis() - startedAt) / 1000).toInt()) } } }

        val wakeRec = if (Prefs.bargeIn == "word") VoskStore.newRecognizer(Prefs.language) else null
        val sensitivity = Prefs.vadSensitivity
        val k = 6.0 - sensitivity / 100.0 * 4.0
        val minAbs = 250.0 + (100 - sensitivity) * 6.0
        val silenceFramesNeeded = Prefs.silenceMs / 20
        var noise = 150.0
        val preroll = ArrayDeque<ShortArray>()
        var utter: ByteArrayOutputStream? = null
        var speechRun = 0; var silenceRun = 0; var speechFrames = 0
        var listenSince = System.currentTimeMillis()
        var thinkingSince = 0L
        val buf = ShortArray(FRAME)

        rec.startRecording()
        ready = true
        try {
            while (isActive && wantCall) {
                var got = 0
                while (got < FRAME) { val n = rec.read(buf, got, FRAME - got); if (n <= 0) break; got += n }
                if (got < FRAME) { delay(10); continue }
                if (gate) { preroll.clear(); speechRun = 0; listenSince = System.currentTimeMillis(); continue }      // her greeting is playing: do not listen to it
                applyMode()
                var sum = 0.0
                for (s in buf) sum += s.toDouble() * s
                val rms = sqrt(sum / FRAME)
                update { it.copy(level = (rms / 6000.0).coerceIn(0.0, 1.0).toFloat(), offline = !HostLink.connected) }

                val thr = maxOf(noise * k, minAbs)
                val speech = rms > thr
                if (!speech) noise = (noise * 0.97 + rms * 0.03).coerceIn(30.0, 1500.0)

                val talking = phase == Phase.SPEAKING || (phase == Phase.THINKING && (AudioPlayer.busy || PhoneTts.speaking))

                // ---- end of the reply: back to listening
                if (phase == Phase.SPEAKING || phase == Phase.THINKING) {
                    val busy = AudioPlayer.busy || PhoneTts.speaking
                    if (busy && phase == Phase.THINKING) setPhase(Phase.SPEAKING)
                    val ended = replyEndedAt > 0 && System.currentTimeMillis() - replyEndedAt > 1500
                    if (!busy && ended) {
                        if (singleTurn && answered) wantCall = false          // the panel does not keep listening
                        else { setPhase(Phase.LISTENING); listenSince = System.currentTimeMillis() }
                    }
                    if (phase == Phase.THINKING && System.currentTimeMillis() - thinkingSince > 120_000) { setPhase(Phase.LISTENING); listenSince = System.currentTimeMillis() }
                }

                // ---- barge-in while she is thinking / talking
                if (phase == Phase.SPEAKING || phase == Phase.THINKING) {
                    when (Prefs.bargeIn) {
                        "voice" -> {
                            val loud = rms > thr * (if (haveAec) 1.2 else 2.6)
                            if (loud) speechRun++ else speechRun = 0
                            if (speechRun >= 12 && (talking || phase == Phase.THINKING)) {
                                interrupt()
                                utter = ByteArrayOutputStream().also { o -> preroll.forEach { o.write(toBytes(it)) } }
                                speechFrames = speechRun; silenceRun = 0
                                setPhase(Phase.HEARING)
                            }
                        }
                        "word" -> if (wakeRec != null) {
                            val done = wakeRec.acceptWaveForm(buf, FRAME)
                            val heard = VoskStore.text(if (done) wakeRec.result else wakeRec.partialResult)
                            if (heard.isNotBlank() && WakeMatch.containsAny(heard, Prefs.bargeWordList())) {
                                interrupt(); wakeRec.reset(); utter = null; speechRun = 0
                                setPhase(Phase.LISTENING); listenSince = System.currentTimeMillis()
                            }
                        }
                    }
                    pushPreroll(preroll, buf)
                    continue
                }

                // ---- listening / hearing
                if (phase == Phase.LISTENING || phase == Phase.HEARING) {
                    if (phase == Phase.LISTENING) {
                        pushPreroll(preroll, buf)
                        if (speech) speechRun++ else speechRun = 0
                        if (speechRun >= 3) {
                            utter = ByteArrayOutputStream().also { o -> preroll.forEach { o.write(toBytes(it)) } }
                            speechFrames = speechRun; silenceRun = 0
                            setPhase(Phase.HEARING)
                        } else if (oneShot && System.currentTimeMillis() - listenSince > Prefs.oneShotIdleSec * 1000L) {
                            wantCall = false
                        }
                    } else {
                        utter?.write(toBytes(buf))
                        if (speech) { speechFrames++; silenceRun = 0 } else silenceRun++
                        val tooLong = (utter?.size() ?: 0) > RATE * 2 * 30
                        if (silenceRun >= silenceFramesNeeded || tooLong) {
                            val pcm = utter?.toByteArray() ?: ByteArray(0)
                            utter = null; speechRun = 0
                            if (speechFrames < 15) { // < 300 ms: just a click or cough
                                setPhase(Phase.LISTENING); listenSince = System.currentTimeMillis()
                            } else {
                                thinkingSince = System.currentTimeMillis()
                                answered = true
                                replyEndedAt = 0; replyStarted = false
                                setPhase(Phase.THINKING)
                                launch(Dispatchers.IO) { handleUtterance(pcm) }
                            }
                            speechFrames = 0
                        }
                    }
                }
            }
        } finally {
            ready = false; gate = false
            events.cancel(); clock.cancel()
            try { rec.stop() } catch (_: Exception) {}
            rec.release(); aec?.release(); ns?.release(); wakeRec?.close()
            singleTurn = false
            net.yume.companion.device.VideoCall.reset()
            net.yume.companion.core.ChatRepo.muteUntil = System.currentTimeMillis() + 5000
            AudioPlayer.stop(); PhoneTts.stop()
            HostLink.callEnd()
            AudioPlayer.callMode = false
            am.mode = oldMode
            @Suppress("DEPRECATION") run { am.isSpeakerphoneOn = false }
            CarMode.active = false
            wantCall = false
            _ui.value = CallUi()
            phase = Phase.IDLE
        }
    }

    private fun interrupt() {
        AudioPlayer.stop(); PhoneTts.stop()
        if (HostLink.connected) CoroutineScope(Dispatchers.IO).launch { Host.stopGeneration() }
        replyEndedAt = System.currentTimeMillis() - 2000
    }

    private fun pushPreroll(q: ArrayDeque<ShortArray>, f: ShortArray) {
        q.addLast(f.copyOf()); while (q.size > 15) q.removeFirst()
    }

    private fun toBytes(s: ShortArray): ByteArray = ByteBuffer.allocate(s.size * 2).order(ByteOrder.LITTLE_ENDIAN).also { b -> s.forEach { b.putShort(it) } }.array()

    private fun wav(pcm: ByteArray): ByteArray {
        val h = ByteBuffer.allocate(44).order(ByteOrder.LITTLE_ENDIAN)
        h.put("RIFF".toByteArray()).putInt(36 + pcm.size).put("WAVE".toByteArray()).put("fmt ".toByteArray())
            .putInt(16).putShort(1).putShort(1).putInt(RATE).putInt(RATE * 2).putShort(2).putShort(16)
            .put("data".toByteArray()).putInt(pcm.size)
        return h.array() + pcm
    }

    private suspend fun handleUtterance(pcm: ByteArray) {
        val online = HostLink.connected
        if (net.yume.companion.device.Interpreter.active && online) {
            // interpreter mode: the PC only transcribes, the sentence is translated and spoken in the other language (no chat answer)
            val said = Host.transcribe(wav(pcm), Prefs.language)
            if (said.isNullOrBlank()) { setPhase(Phase.LISTENING); return }
            update { it.copy(heard = said, error = "") }
            val cmd = net.yume.companion.device.QuickCommands.detectInterpreter(said)
            if (cmd != null) { val out = cmd.run(); update { it.copy(reply = out) } }
            setPhase(Phase.LISTENING)
            return
        }
        if (online) {
            val who = if (Prefs.voiceId) withContext(Dispatchers.Default) { SpeakerLock.identify(pcm) } else ""
            val text = Host.sendSpeech(wav(pcm), Prefs.character, Prefs.language, net.yume.companion.device.VideoCall.snapshot(), who)
            if (text == null) {
                // the PC vanished in the middle of the call: continue offline if possible
                if (!offlineTurn(pcm)) { update { it.copy(error = tr("Verbindung zum PC verloren", "Connection to the PC lost")) }; setPhase(Phase.LISTENING) }
                return
            }
            update { it.copy(heard = text, error = "") }
            if (text.isBlank() || text.length <= 2) { setPhase(Phase.LISTENING); return }
            if (WakeMatch.containsAny(text, Prefs.hangupWordList())) { wantCall = false; return }
        } else if (!offlineTurn(pcm)) {
            update { it.copy(error = tr("PC nicht erreichbar und der Offline-Modus ist nicht eingerichtet", "PC not reachable and offline mode is not set up")) }
            setPhase(Phase.LISTENING)
        }
    }

    /** Offline emergency mode: Vosk recognises, the small on-device model answers, Android reads it out. */
    /** A clear command was recognised: it is carried out right here (no PC, no model) and the result is spoken by the phone. */
    private suspend fun quickTurn(text: String): Boolean {
        val cmd = net.yume.companion.device.QuickCommands.detect(text) ?: return false
        update { it.copy(heard = text, offline = true) }
        val answer = try { cmd.run() } catch (e: Exception) { tr("Das hat nicht geklappt.", "That did not work.") }
        update { it.copy(reply = answer) }
        replyEndedAt = 0; replyStarted = false
        PhoneTts.onDone = { replyEndedAt = System.currentTimeMillis() - 1000 }
        setPhase(Phase.SPEAKING)
        PhoneTts.speak(answer)
        return true
    }

    /** Offline model not set up: speech recognition alone is still enough for the quick commands. */
    private suspend fun quickOnlyTurn(pcm: ByteArray): Boolean {
        val rec = VoskStore.newRecognizer(Prefs.language) ?: return false
        val shorts = ShortArray(pcm.size / 2)
        ByteBuffer.wrap(pcm).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(shorts)
        rec.acceptWaveForm(shorts, shorts.size)
        val text = VoskStore.text(rec.finalResult); rec.close()
        if (text.isBlank()) { setPhase(Phase.LISTENING); return true }
        if (WakeMatch.containsAny(text, Prefs.hangupWordList())) { wantCall = false; return true }
        return quickTurn(text)
    }

    private suspend fun offlineTurn(pcm: ByteArray): Boolean {
        if (!Prefs.offlineEnabled || !Prefs.offlineAutoSwitch || !OfflineChat.ready()) return quickOnlyTurn(pcm)
        val rec = VoskStore.newRecognizer(Prefs.language) ?: return false
        val bytes = pcm
        val shorts = ShortArray(bytes.size / 2)
        ByteBuffer.wrap(bytes).order(ByteOrder.LITTLE_ENDIAN).asShortBuffer().get(shorts)
        rec.acceptWaveForm(shorts, shorts.size)
        val text = VoskStore.text(rec.finalResult); rec.close()
        update { it.copy(heard = text, offline = true) }
        if (text.isBlank()) { setPhase(Phase.LISTENING); return true }
        if (WakeMatch.containsAny(text, Prefs.hangupWordList())) { wantCall = false; return true }
        if (quickTurn(text)) return true
        val answer = OfflineChat.reply(text)
        update { it.copy(reply = answer) }
        OfflineHandover.record(text, answer)
        replyEndedAt = 0; replyStarted = false
        PhoneTts.onDone = { replyEndedAt = System.currentTimeMillis() - 1000 }
        setPhase(Phase.SPEAKING)
        PhoneTts.speak(answer)
        return true
    }
}
