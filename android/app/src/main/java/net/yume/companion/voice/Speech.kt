package net.yume.companion.voice

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.media.MediaPlayer
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import net.yume.companion.App
import net.yume.companion.core.Prefs
import org.json.JSONObject
import org.vosk.Model
import org.vosk.Recognizer
import java.io.File
import java.net.URL
import java.util.Locale
import java.util.zip.ZipInputStream

/** Android's own offline text-to-speech (offline mode, notifications, confirmations). */
object PhoneTts {
    private var tts: TextToSpeech? = null
    private var ready = false
    @Volatile var speaking = false
    var onDone: (() -> Unit)? = null

    private fun ensure(ctx: Context) {
        if (tts != null) return
        tts = TextToSpeech(ctx.applicationContext) { status ->
            ready = status == TextToSpeech.SUCCESS
            if (ready) {
                tts?.language = Locale.forLanguageTag(Prefs.language.ifEmpty { "de" })
                tts?.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
                    override fun onStart(id: String?) { speaking = true }
                    override fun onDone(id: String?) { speaking = false; onDone?.invoke(); id?.let { finished.remove(it)?.complete(Unit) } }
                    override fun onStop(id: String?, interrupted: Boolean) { speaking = false; id?.let { finished.remove(it)?.complete(Unit) } }
                    @Deprecated("deprecated") override fun onError(id: String?) { speaking = false; onDone?.invoke(); id?.let { finished.remove(it)?.complete(Unit) } }
                })
            }
        }
    }

    fun speak(text: String) {
        val ctx = App.instance
        ensure(ctx)
        val t = tts ?: return
        if (!ready) { // engine still starting: retry once shortly
            android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({ if (ready) speakNow(text) }, 1200)
            return
        }
        speakNow(text)
    }

    private val finished = java.util.concurrent.ConcurrentHashMap<String, kotlinx.coroutines.CompletableDeferred<Unit>>()

    /** Speaks and returns when the sentence is really over (the engine needs a moment to start; waiting on [speaking] alone returns too early and the next step cuts the voice). */
    suspend fun speakAndWait(text: String, maxMs: Long = 9000) {
        ensure(App.instance)
        var waited = 0
        while (!ready && waited < 4000) { kotlinx.coroutines.delay(50); waited += 50 }
        if (!ready) return
        val id = "w" + System.nanoTime()
        val done = kotlinx.coroutines.CompletableDeferred<Unit>()
        finished[id] = done
        speakNow(text, id)
        kotlinx.coroutines.withTimeoutOrNull(maxMs) { done.await() }
        finished.remove(id)
        kotlinx.coroutines.delay(400)                  // the speaker still plays the tail
    }

    /** language of the voice for translations (interpreter mode); null = the app language */
    @Volatile private var overrideLocale: Locale? = null

    suspend fun speakIn(locale: Locale, text: String) {
        overrideLocale = locale
        try { speakAndWait(text, 20_000) } finally { overrideLocale = null }
    }

    private fun speakNow(text: String, id: String = "y" + System.nanoTime()) {
        tts?.language = overrideLocale ?: Locale.forLanguageTag(Prefs.language.ifEmpty { "de" })
        tts?.setSpeechRate(Prefs.phoneTtsRate / 100f)
        val params = android.os.Bundle().apply { putFloat(TextToSpeech.Engine.KEY_PARAM_VOLUME, (Prefs.ttsVolume / 100f * net.yume.companion.core.Quiet.factor()).coerceIn(0f, 1f)) }
        tts?.speak(text, TextToSpeech.QUEUE_ADD, params, id)
    }

    fun stop() { tts?.stop(); speaking = false }
}

/** Plays the PC's voice (WAV chunks) one after the other; can be stopped instantly for barge-in. Also reports the voice level (lip sync). */
object AudioPlayer {
    private val queue = ArrayDeque<ByteArray>()
    private var player: MediaPlayer? = null
    private var focus: AudioFocusRequest? = null
    @Volatile var playing = false
    @Volatile var callMode = false                       // during a call the voice uses the call audio path (echo cancellation)
    var onIdle: (() -> Unit)? = null
    var onStart: (() -> Unit)? = null
    private val handler = android.os.Handler(android.os.Looper.getMainLooper())

    /** 0..1 loudness of the voice that is playing right now - drives the mouth of the 3D avatar. */
    val level = kotlinx.coroutines.flow.MutableStateFlow(0f)
    private var envelope: FloatArray = FloatArray(0)
    private val tick = object : Runnable {
        override fun run() {
            val mp = player
            if (mp == null || !playing) { level.value = 0f; return }
            val i = try { mp.currentPosition / ENV_MS } catch (_: Exception) { -1 }
            level.value = if (i in envelope.indices) envelope[i] else 0f
            handler.postDelayed(this, ENV_MS.toLong())
        }
    }

    /** true from the moment a clip was handed in until it is really playing: the player needs a moment to prepare, and during that moment it used to look idle */
    @Volatile private var starting = false

    fun enqueue(wav: ByteArray) { starting = true; handler.post { queue.addLast(wav); if (!playing) next() } }

    val busy: Boolean get() = playing || starting || queue.isNotEmpty()

    fun stop() {
        handler.post {
            queue.clear(); starting = false
            try { player?.stop() } catch (_: Exception) {}
            release(); playing = false; level.value = 0f
            abandonFocus()
        }
    }

    private fun next() {
        val wav = queue.removeFirstOrNull()
        if (wav == null) { playing = false; starting = false; level.value = 0f; abandonFocus(); onIdle?.invoke(); return }
        val ctx = App.instance
        try {
            envelope = envelopeOf(wav)
            val f = File.createTempFile("yume_", ".wav", ctx.cacheDir)
            f.writeBytes(wav)
            requestFocus(ctx)
            release()
            val mp = MediaPlayer()
            mp.setAudioAttributes(AudioAttributes.Builder()
                .setUsage(if (callMode && Prefs.echoCancel) AudioAttributes.USAGE_VOICE_COMMUNICATION else AudioAttributes.USAGE_MEDIA)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
            mp.setDataSource(f.absolutePath)
            val vol = (Prefs.ttsVolume * net.yume.companion.core.Quiet.factor()).toInt().coerceIn(0, 200)
            mp.setVolume((vol / 100f).coerceAtMost(1f), (vol / 100f).coerceAtMost(1f))
            if (vol > 100) try {                       // more than 100 %: amplify (up to +15 dB)
                enhancer = android.media.audiofx.LoudnessEnhancer(mp.audioSessionId).also { it.setTargetGain((vol - 100) * 15); it.enabled = true }
            } catch (_: Exception) {}
            mp.setOnCompletionListener { f.delete(); next() }
            mp.setOnErrorListener { _, _, _ -> f.delete(); next(); true }
            mp.setOnPreparedListener { playing = true; starting = false; onStart?.invoke(); it.start(); handler.removeCallbacks(tick); handler.post(tick) }
            player = mp
            mp.prepareAsync()
        } catch (_: Exception) { next() }
    }

    private const val ENV_MS = 40

    /** Loudness per 40 ms of a 16-bit PCM WAV (empty array when the format is something else). */
    private fun envelopeOf(wav: ByteArray): FloatArray {
        try {
            val bb = java.nio.ByteBuffer.wrap(wav).order(java.nio.ByteOrder.LITTLE_ENDIAN)
            var pos = 12
            var rate = 22050; var channels = 1; var bits = 16; var fmt = 1
            while (pos + 8 <= wav.size) {
                val id = String(wav, pos, 4, Charsets.US_ASCII); val size = bb.getInt(pos + 4)
                if (id == "fmt ") { fmt = bb.getShort(pos + 8).toInt(); channels = bb.getShort(pos + 10).toInt(); rate = bb.getInt(pos + 12); bits = bb.getShort(pos + 22).toInt() }
                if (id == "data") {
                    if (fmt != 1 || bits != 16) return FloatArray(0)
                    val start = pos + 8; val end = minOf(wav.size, start + size.coerceAtLeast(0))
                    val step = (rate * ENV_MS / 1000) * channels * 2
                    if (step <= 0) return FloatArray(0)
                    val n = (end - start) / step
                    val rms = FloatArray(n)
                    for (w in 0 until n) {
                        var sum = 0.0; var c = 0
                        var o = start + w * step
                        while (o + 1 < start + (w + 1) * step && o + 1 < end) { val s = bb.getShort(o).toInt(); sum += s.toDouble() * s; c++; o += 2 * channels }
                        rms[w] = if (c > 0) Math.sqrt(sum / c).toFloat() else 0f
                    }
                    val sorted = rms.sortedArray()
                    val ref = (sorted.getOrElse((sorted.size * 0.92).toInt()) { 1f }).coerceAtLeast(300f)
                    var prev = 0f
                    return FloatArray(n) { i ->
                        val v = (rms[i] / ref).coerceIn(0f, 1f)
                        prev = if (v > prev) prev + (v - prev) * 0.7f else prev + (v - prev) * 0.35f     // quick attack, slower release
                        if (prev < 0.06f) 0f else prev
                    }
                }
                pos += 8 + size + (size and 1)
            }
        } catch (_: Exception) {}
        return FloatArray(0)
    }

    private var enhancer: android.media.audiofx.LoudnessEnhancer? = null
    private fun release() {
        handler.removeCallbacks(tick)
        try { enhancer?.release() } catch (_: Exception) {}
        enhancer = null
        try { player?.release() } catch (_: Exception) {}
        player = null
    }

    private fun requestFocus(ctx: Context) {
        val am = ctx.getSystemService(AudioManager::class.java)
        if (focus == null) {
            focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
                .setAudioAttributes(AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_VOICE_COMMUNICATION).setContentType(AudioAttributes.CONTENT_TYPE_SPEECH).build())
                .build()
            am.requestAudioFocus(focus!!)
        }
    }

    private fun abandonFocus() {
        val f = focus ?: return
        App.instance.getSystemService(AudioManager::class.java).abandonAudioFocusRequest(f)
        focus = null
    }
}

/** Vosk models (offline speech recognition, no account / key): downloaded once per language. */
object VoskStore {
    private val urls = mapOf(
        "de" to "vosk-model-small-de-0.15", "en" to "vosk-model-small-en-us-0.15", "ru" to "vosk-model-small-ru-0.22",
        "fr" to "vosk-model-small-fr-0.22", "es" to "vosk-model-small-es-0.42", "it" to "vosk-model-small-it-0.22",
        "pl" to "vosk-model-small-pl-0.22", "nl" to "vosk-model-small-nl-0.22", "tr" to "vosk-model-small-tr-0.3",
        "ja" to "vosk-model-small-ja-0.22", "zh" to "vosk-model-small-cn-0.22",
        "spk" to "vosk-model-spk-0.4",                     // speaker model (voice prints), not a language
    )
    val languages: List<String> get() = urls.keys.filter { it != "spk" }
    private val models = HashMap<String, Model>()

    fun dir(lang: String) = File(App.instance.filesDir, "vosk/$lang")
    fun installed(lang: String) = File(dir(lang), "am").exists() || File(dir(lang), "conf").exists() || File(dir(lang), "mfcc.conf").exists()

    suspend fun download(lang: String, progress: (Float) -> Unit): Result<Unit> = withContext(Dispatchers.IO) {
        val name = urls[lang] ?: return@withContext Result.failure(Exception("Sprache nicht unterstützt"))
        try {
            val target = dir(lang)
            val tmp = File(target.parentFile, "$lang.tmp"); tmp.deleteRecursively(); tmp.mkdirs()
            val conn = URL("https://alphacephei.com/vosk/models/$name.zip").openConnection()
            val total = conn.contentLengthLong.coerceAtLeast(1)
            var read = 0L
            ZipInputStream(conn.getInputStream().buffered()).use { zin ->
                var e = zin.nextEntry
                while (e != null) {
                    val rel = e.name.substringAfter('/')
                    if (rel.isNotEmpty() && !rel.contains("..")) {
                        val out = File(tmp, rel)
                        if (e.isDirectory) out.mkdirs() else {
                            out.parentFile?.mkdirs()
                            out.outputStream().use { o ->
                                val buf = ByteArray(65536)
                                while (true) { val n = zin.read(buf); if (n <= 0) break; o.write(buf, 0, n); read += n; progress((read.toFloat() / (total * 1.6f)).coerceAtMost(0.99f)) }
                            }
                        }
                    }
                    e = zin.nextEntry
                }
            }
            target.deleteRecursively(); tmp.renameTo(target)
            progress(1f)
            Result.success(Unit)
        } catch (e: Exception) { Result.failure(e) }
    }

    @Synchronized fun model(lang: String): Model? {
        if (!installed(lang)) return null
        return models.getOrPut(lang) { Model(dir(lang).absolutePath) }
    }

    fun newRecognizer(lang: String): Recognizer? = model(lang)?.let { Recognizer(it, 16000f) }

    fun text(json: String): String = try { JSONObject(json).let { it.optString("text").ifEmpty { it.optString("partial") } } } catch (_: Exception) { "" }
}

/** Fuzzy comparison of what the recogniser heard with the wake words ("yume" is often heard as "jume", "ju me", "umi" ...). */
object WakeMatch {
    private fun norm(s: String): String = s.lowercase(Locale.ROOT)
        .replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("ß", "ss")
        .replace(Regex("[^a-z0-9 ]"), "")
        .replace('j', 'y').replace("ou", "u").replace("oo", "u").replace("ee", "i").replace('w', 'v')
        .replace("ph", "f").replace('c', 'k').replace('q', 'k').replace('z', 's')

    private fun dist(a: String, b: String): Int {
        val dp = IntArray(b.length + 1) { it }
        for (i in 1..a.length) {
            var prev = dp[0]; dp[0] = i
            for (j in 1..b.length) { val t = dp[j]; dp[j] = minOf(dp[j] + 1, dp[j - 1] + 1, prev + if (a[i - 1] == b[j - 1]) 0 else 1); prev = t }
        }
        return dp[b.length]
    }

    // ---- wake word matching: the German speech model hears English names badly ("hey yume" -> "hai sero zwei", "he cero 2" ...)
    private val GREETINGS = setOf("hey", "hei", "hai", "hay", "hi", "he", "ey", "eh", "hallo", "halo", "hello", "ok", "okay", "oke", "ach")
    /** words that are heard instead of a number name; the same table is applied to what was heard and to the wake word */
    private val SOUND_ALIKE = mapOf(
        "2" to "tu", "zwei" to "tu", "zwo" to "tu", "two" to "tu", "too" to "tu", "to" to "tu", "tu" to "tu", "du" to "tu", "zu" to "tu", "tue" to "tu",
        "0" to "sero", "null" to "sero", "zero" to "sero", "cero" to "sero", "siro" to "sero", "ziro" to "sero",
    )

    /** one word -> a rough pronunciation key (voiced/unvoiced pairs, spelling variants and double letters are folded together) */
    private fun sound(word: String): String {
        var w = word
        w = w.replace("ei", "ai").replace("ey", "ai").replace("ay", "ai")
            .replace('d', 't').replace('b', 'p').replace('g', 'k').replace('v', 'f').replace("h", "")
        w = w.replace(Regex("(.)\\1+"), "$1")
        return w
    }

    /** whole text -> list of pronunciation keys without the leading greeting ("hey ...") */
    private fun keys(s: String): List<String> {
        val raw = s.lowercase(Locale.ROOT)
            .replace("ü", "u").replace("ö", "o").replace("ä", "a").replace("ß", "ss")
            .replace(Regex("[^a-z0-9 ]"), " ")
            .split(' ').filter { it.isNotEmpty() }
        var start = 0
        while (start < raw.size - 1 && raw[start] in GREETINGS) start++      // "hey yume" -> "yume" (the greeting is optional)
        return raw.drop(start).map { word ->
            val w = SOUND_ALIKE[word] ?: word
            val base = w.replace('j', 'y').replace("ou", "u").replace("oo", "u").replace("ee", "i").replace('w', 'v')
                .replace("ph", "f").replace('c', 'k').replace('q', 'k').replace('z', 's')
            sound(base)
        }.filter { it.isNotEmpty() }
    }

    /** sensitivity 0..100: higher = accepts more distant matches (more false alarms) */
    fun matches(heard: String, words: List<String>, sensitivity: Int): Boolean = explain(heard, words, sensitivity) != null

    /** which wake word matched (null = none); also used by the wake word test in the settings */
    fun explain(heard: String, words: List<String>, sensitivity: Int): String? {
        if (heard.isBlank()) return null
        val tokens = keys(heard)
        if (tokens.isEmpty()) return null
        val maxRatio = 0.15 + sensitivity / 100.0 * 0.30
        for (w in words) {
            val wTokens = keys(w)
            val wn = wTokens.joinToString("")
            if (wn.length < 2) continue
            for (len in maxOf(1, wTokens.size - 1)..minOf(wTokens.size + 1, tokens.size)) {
                for (i in 0..tokens.size - len) {
                    val cand = tokens.subList(i, i + len).joinToString("")
                    if (cand.length < 2) continue
                    if (dist(cand, wn).toDouble() / wn.length <= maxRatio) return w
                }
            }
        }
        return null
    }

    fun containsAny(heard: String, words: List<String>): Boolean {
        val h = " " + norm(heard) + " "
        return words.any { val n = norm(it); n.isNotEmpty() && h.contains(" $n ") }
    }
}
