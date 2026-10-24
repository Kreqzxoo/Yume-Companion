package net.yume.companion.voice

import android.net.Uri
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.yume.companion.App
import net.yume.companion.core.Host
import net.yume.companion.core.HostLink
import net.yume.companion.core.Link
import net.yume.companion.core.Prefs
import okhttp3.Request
import java.io.File
import java.security.MessageDigest

/**
 * What she says when the wake word was heard ("Ja, ich höre?"). The sentences are synthesized by the PC with the voice that is set up for
 * the character there (TTS + RVC) in the best quality, checked by speech recognition, and downloaded. Every sentence can have several
 * recordings ("takes"): you listen, choose one, delete, export them, or import your own audio files. At the wake word a random sentence
 * is played, in its chosen take. Without any recording the phone's own voice says it.
 */
object WakeVoice {
    const val DEFAULT_PHRASES = "Ja, ich höre?\nJa?\nIch bin da.\nWas gibt's?"
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    private val root get() = File(App.instance.filesDir, "wake_voice").also { it.mkdirs() }

    var status by mutableStateOf("")
    var busy by mutableStateOf(false)
    /** bumped whenever recordings change, so screens re-read the list */
    var version by mutableIntStateOf(0)
        private set

    fun phrases(): List<String> = Prefs.wakeReplies.lines().map { it.trim() }.filter { it.isNotEmpty() }.take(8)

    private fun hash(s: String): String =
        MessageDigest.getInstance("SHA-1").digest(s.toByteArray()).joinToString("") { "%02x".format(it) }.take(12)

    private fun phraseDir(character: String, text: String) = File(File(root, hash(character)), hash(text))

    /** recordings of one sentence, oldest first */
    fun takes(text: String, character: String = Prefs.character): List<File> =
        phraseDir(character, text).listFiles { f -> f.isFile && f.length() > 500 }?.sortedBy { it.name } ?: emptyList()

    fun selected(text: String, character: String = Prefs.character): File? {
        val all = takes(text, character)
        val name = Prefs.sp.getString("wake_sel_" + hash(character) + "_" + hash(text), null)
        return all.firstOrNull { it.name == name } ?: all.firstOrNull()
    }

    fun select(text: String, file: File, character: String = Prefs.character) {
        Prefs.sp.edit().putString("wake_sel_" + hash(character) + "_" + hash(text), file.name).apply(); version++
    }

    fun delete(text: String, file: File, character: String = Prefs.character) {
        file.delete(); version++
        val sel = Prefs.sp.getString("wake_sel_" + hash(character) + "_" + hash(text), null)
        if (sel == file.name) Prefs.sp.edit().remove("wake_sel_" + hash(character) + "_" + hash(text)).apply()
    }

    fun deleteAll(character: String = Prefs.character) { File(root, hash(character)).deleteRecursively(); version++ }

    /** stores audio as a new recording; [tag] = quality in percent or "x" for imported files */
    fun addTake(text: String, bytes: ByteArray, ext: String = "wav", tag: String = "x", character: String = Prefs.character): File {
        val dir = phraseDir(character, text).also { it.mkdirs() }
        val f = File(dir, "take_%013d_%s.%s".format(System.currentTimeMillis(), tag, ext))
        f.writeBytes(bytes); version++
        return f
    }

    fun importFrom(text: String, uri: Uri): Boolean = try {
        val resolver = App.instance.contentResolver
        val bytes = resolver.openInputStream(uri)?.use { it.readBytes() }
        if (bytes == null || bytes.size < 500 || bytes.size > 8 * 1024 * 1024) false
        else {
            val type = resolver.getType(uri).orEmpty()
            val ext = when { type.contains("wav") -> "wav"; type.contains("mpeg") || type.contains("mp3") -> "mp3"; type.contains("ogg") -> "ogg"; type.contains("mp4") || type.contains("aac") -> "m4a"; else -> "wav" }
            addTake(text, bytes, ext, "x"); true
        }
    } catch (_: Exception) { false }

    fun exportTo(file: File, uri: Uri): Boolean = try {
        App.instance.contentResolver.openOutputStream(uri)?.use { it.write(file.readBytes()) } != null
    } catch (_: Exception) { false }

    /** writes every recording of every sentence into a folder the user picked (Storage Access Framework tree) */
    fun exportAllTo(tree: Uri): Int {
        val resolver = App.instance.contentResolver
        val parent = android.provider.DocumentsContract.buildDocumentUriUsingTree(tree, android.provider.DocumentsContract.getTreeDocumentId(tree))
        var n = 0
        for (text in phrases()) {
            val slug = text.lowercase().replace(Regex("[^a-z0-9äöüß]+"), "_").trim('_').take(24).ifEmpty { "satz" }
            takes(text).forEachIndexed { i, f ->
                try {
                    val doc = android.provider.DocumentsContract.createDocument(resolver, parent, "audio/*", "yume_${slug}_${i + 1}.${f.extension}")
                    if (doc != null) { resolver.openOutputStream(doc)?.use { it.write(f.readBytes()) }; n++ }
                } catch (_: Exception) {}
            }
        }
        return n
    }

    /** "1.2 s · Qualität 100 %" (WAV) or the file size */
    fun describe(f: File): String {
        val q = f.nameWithoutExtension.substringAfterLast('_')
        val quality = if (q.isNotEmpty() && q.all { it.isDigit() }) " · Qualität $q %" else if (q == "x") " · eigene Datei" else ""
        val len = try {
            if (f.extension != "wav") "%.0f KB".format(f.length() / 1024.0) else {
                val h = f.inputStream().use { i -> ByteArray(44).also { i.read(it) } }
                val bb = java.nio.ByteBuffer.wrap(h).order(java.nio.ByteOrder.LITTLE_ENDIAN)
                val rate = bb.getInt(24).coerceAtLeast(8000); val ch = bb.getShort(22).toInt().coerceAtLeast(1)
                "%.1f s".format((f.length() - 44) / (rate * ch * 2.0))
            }
        } catch (_: Exception) { "" }
        return len + quality
    }

    fun downloaded(): Int = phrases().count { selected(it) != null }

    /** a random sentence in its chosen recording, or null */
    fun pick(): Pair<String, ByteArray>? {
        val ready = phrases().mapNotNull { t -> selected(t)?.let { t to it } }
        val (text, file) = ready.randomOrNull() ?: return null
        return text to file.readBytes()
    }

    fun fallbackText(): String = phrases().randomOrNull() ?: "Ja?"

    /** plays one recording (for listening in the manager) */
    fun preview(file: File) { try { AudioPlayer.enqueue(padded(file.readBytes())) } catch (_: Exception) {} }

    /**
     * Asks the PC for [count] new recordings of [text] (best quality, each one checked by speech recognition). Sequential; calls [onProgress]
     * after every recording. Returns how many arrived.
     */
    suspend fun generate(text: String, count: Int, onProgress: (done: Int) -> Unit = {}): Int = withContext(Dispatchers.IO) {
        val character = Prefs.character
        if (character.isEmpty() || !HostLink.connected || Host.baseUrl.isEmpty()) { status = "Der PC ist nicht erreichbar."; return@withContext 0 }
        busy = true
        var got = 0
        try {
            for (i in 1..count) {
                status = "„$text“ – Aufnahme $i von $count wird am PC erzeugt (beste Qualität, mit Prüfung) …"
                val r = fetch(character, text)
                if (r == null) { status = "Der PC konnte die Stimme nicht erzeugen (hat der Charakter dort eine Sprachausgabe?)"; break }
                addTake(text, r.first, "wav", r.second.toString(), character)
                got++; onProgress(got)
            }
            if (got == count) status = "$got neue Aufnahme${if (got == 1) "" else "n"} für „$text“ – hör sie dir an und wähle eine."
        } finally { busy = false }
        got
    }

    /** every sentence needs at least one recording: fetch the missing ones (one each) */
    fun sync() {
        if (busy || !Prefs.wakeReplyOn) return
        val character = Prefs.character
        if (character.isEmpty() || !HostLink.connected || Host.baseUrl.isEmpty()) return
        scope.launch {
            // the first version of this feature kept flat files: they are not used any more
            try { root.listFiles()?.forEach { if (it.isFile) it.delete() } } catch (_: Exception) {}
            for (text in phrases()) if (takes(text, character).isEmpty()) { if (generate(text, 1) == 0) break }
        }
    }

    private fun fetch(character: String, text: String): Pair<ByteArray, Int>? = try {
        val base = Host.baseUrl
        val url = "$base/api/wake_phrase?hq=1&verify=1&character=" + java.net.URLEncoder.encode(character, "UTF-8") + "&text=" + java.net.URLEncoder.encode(text, "UTF-8")
        Host.clientFor(base).newBuilder().readTimeout(java.time.Duration.ofSeconds(600)).build()
            .newCall(Request.Builder().url(url).header("X-Yume-Token", Prefs.token).build()).execute().use { r ->
                if (!r.isSuccessful) null else r.body?.bytes()?.let { it to (r.header("X-Yume-Score")?.toIntOrNull() ?: 0) }
            }
    } catch (_: Exception) { null }

    /** the same WAV with [ms] of silence appended (16-bit PCM, data chunk last); anything else is returned unchanged */
    private fun padded(wav: ByteArray, ms: Int = 300): ByteArray = try {
        val bb = java.nio.ByteBuffer.wrap(wav).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        var pos = 12; var rate = 24000; var channels = 1; var bits = 16; var dataPos = -1; var dataLen = 0
        while (wav.size >= 12 && pos + 8 <= wav.size) {
            val id = String(wav, pos, 4, Charsets.US_ASCII); val size = bb.getInt(pos + 4)
            if (id == "fmt ") { channels = bb.getShort(pos + 10).toInt(); rate = bb.getInt(pos + 12); bits = bb.getShort(pos + 22).toInt() }
            if (id == "data") { dataPos = pos; dataLen = if (size < 0 || pos + 8 + size > wav.size) wav.size - pos - 8 else size; break }
            pos += 8 + size + (size and 1)
        }
        if (wav.size < 12 || String(wav, 0, 4, Charsets.US_ASCII) != "RIFF" || dataPos < 0 || bits != 16 || dataPos + 8 + dataLen != wav.size) wav
        else {
            val silence = ByteArray(rate * channels * 2 * ms / 1000)
            val out = wav + silence
            val ob = java.nio.ByteBuffer.wrap(out).order(java.nio.ByteOrder.LITTLE_ENDIAN)
            ob.putInt(4, out.size - 8); ob.putInt(dataPos + 4, dataLen + silence.size)
            out
        }
    } catch (_: Exception) { wav }

    /** Plays one line and waits until it is over (so the microphone does not hear it as the user's sentence). */
    suspend fun speak(force: Boolean = false) {
        if (!Prefs.wakeReplyOn && !force) return
        val picked = pick()
        if (picked != null) {
            AudioPlayer.enqueue(padded(picked.second))     // silence at the end: the last syllable must not be cut by the audio mode change that follows
            var started = 0
            while (!AudioPlayer.playing && started < 3000) { delay(50); started += 50 }      // wait until it really plays
            var waited = 0
            while (AudioPlayer.busy && waited < 8000) { delay(100); waited += 100 }
            delay(200)                                     // the speaker still plays the tail after the player says "done"
        } else {
            PhoneTts.speakAndWait(fallbackText())          // nothing recorded: the phone's own voice, and we really wait for it
        }
    }

    /** loads missing recordings whenever the PC (re)appears */
    fun watch() {
        scope.launch {
            HostLink.state.collect { s -> if (s == Link.CONNECTED) { delay(2500); sync() } }
        }
    }
}
