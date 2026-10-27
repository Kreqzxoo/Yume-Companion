// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.offline

import net.yume.companion.core.tr

import android.content.Context
import com.google.mediapipe.tasks.genai.llminference.LlmInference
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.yume.companion.App
import net.yume.companion.core.Prefs
import net.yume.companion.core.Sync
import java.io.File
import java.io.FileOutputStream
import java.io.IOException
import java.net.HttpURLConnection
import java.net.URL

/** Small language models that run on the phone itself (emergency mode when the PC cannot be reached). */
data class OfflineModel(val id: String, val title: String, val file: String, val url: String, val sizeMb: Int)

object OfflineModels {
    private const val HF = "https://huggingface.co/litert-community"
    val all = listOf(
        OfflineModel("qwen05", tr("Qwen 2.5 – 0,5 B (schnell, ~0,55 GB)", "Qwen 2.5 – 0.5 B (fast, ~0.55 GB)"), "qwen25_05b.task",
            "$HF/Qwen2.5-0.5B-Instruct/resolve/main/Qwen2.5-0.5B-Instruct_multi-prefill-seq_q8_ekv1280.task", 560),
        OfflineModel("qwen15", tr("Qwen 2.5 – 1,5 B (klüger, ~1,6 GB)", "Qwen 2.5 – 1.5 B (smarter, ~1.6 GB)"), "qwen25_15b.task",
            "$HF/Qwen2.5-1.5B-Instruct/resolve/main/Qwen2.5-1.5B-Instruct_multi-prefill-seq_q8_ekv1280.task", 1600),
    )
    fun current() = all.firstOrNull { it.id == Prefs.offlineModel } ?: all.first()
    fun file(m: OfflineModel = current()) = File(App.instance.filesDir, "llm/${m.file}")
    fun installed(m: OfflineModel = current()) = file(m).let { it.exists() && it.length() > m.sizeMb * 1_000_000L * 0.9 }

    // ---- downloads run in the app's own scope: they go on when the screen is left, and resume where they stopped (the files are 0.5 - 1.6 GB)
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
    val progress = MutableStateFlow(-1f)          // < 0 = no download running
    val activeId = MutableStateFlow("")
    val error = MutableStateFlow("")
    val version = MutableStateFlow(0)             // counts up whenever a file was added or deleted

    fun broken(m: OfflineModel = current()) = Prefs.offlineBroken.split(',').contains(m.id)
    fun markBroken(id: String) { Prefs.offlineBroken = (Prefs.offlineBroken.split(',').filter { it.isNotBlank() && it != id } + id).joinToString(",") }
    fun clearBroken(id: String) { Prefs.offlineBroken = Prefs.offlineBroken.split(',').filter { it.isNotBlank() && it != id }.joinToString(",") }
    /** the file is there AND the model did not crash on this phone */
    fun usable(m: OfflineModel = current()) = installed(m) && !broken(m)

    fun start(m: OfflineModel) {
        if (activeId.value.isNotEmpty()) return
        activeId.value = m.id; progress.value = 0f; error.value = ""
        scope.launch {
            download(m) { progress.value = it }.onFailure { error.value = tr("Download fehlgeschlagen: ${it.message} (beim nächsten Versuch geht es dort weiter, wo es aufgehört hat)", "Download failed: ${it.message} (the next attempt continues where it stopped)") }
            clearBroken(m.id)
            progress.value = -1f; activeId.value = ""; version.value++
        }
    }

    fun delete(m: OfflineModel) {
        if (activeId.value == m.id) return
        file(m).delete(); File(file(m).path + ".part").delete(); clearBroken(m.id); version.value++
    }

    suspend fun download(m: OfflineModel, progress: (Float) -> Unit): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val target = file(m); target.parentFile?.mkdirs()
            val part = File(target.path + ".part")
            val have = if (part.exists()) part.length() else 0L
            val conn = (URL(m.url).openConnection() as HttpURLConnection).also {
                it.connectTimeout = 15000; it.readTimeout = 60000
                if (have > 0) it.setRequestProperty("Range", "bytes=$have-")
            }
            val code = conn.responseCode
            if (code == 416 && have > 0) {                      // the part file is already complete
                target.delete(); part.renameTo(target); return@withContext Result.success(Unit)
            }
            if (code !in 200..299) throw IOException(tr("Server antwortet mit $code", "Server answers with $code"))
            val resumed = code == 206
            val total = ((if (resumed) have else 0L) + conn.contentLengthLong).coerceAtLeast(1)
            var read = if (resumed) have else 0L
            conn.inputStream.use { inp ->
                FileOutputStream(part, resumed).use { out ->
                    val buf = ByteArray(1 shl 16)
                    while (true) {
                        val n = inp.read(buf); if (n <= 0) break
                        out.write(buf, 0, n); read += n; progress(read.toFloat() / total)
                    }
                }
            }
            if (read < total * 0.99) throw IOException(tr("Datei unvollständig (${read / 1_000_000} von ${total / 1_000_000} MB)", "File incomplete (${read / 1_000_000} of ${total / 1_000_000} MB)"))
            target.delete(); part.renameTo(target)
            Result.success(Unit)
        } catch (e: Exception) { Result.failure(e) }
    }
}

object OfflineChat {
    private var llm: LlmInference? = null
    private var loadedId = ""
    private val localHistory = ArrayList<Pair<String, String>>()   // user, assistant (this offline session)

    @Volatile var lastError = ""

    fun ready(): Boolean = OfflineModels.usable()

    @Synchronized private fun engine(ctx: Context): LlmInference? {
        val m = OfflineModels.current()
        if (!OfflineModels.usable(m)) return null
        if (llm == null || loadedId != m.id) {
            try { llm?.close() } catch (_: Throwable) {}
            llm = null
            // Loading maps the whole model into memory. If the phone cannot do that, Android may kill the app without any exception:
            // the marker is written first (commit = really on disk) and removed afterwards; if it is still there at the next start, App.kt marks the model as "crashed".
            Prefs.sp.edit().putString("offline_loading", m.id).commit()
            try {
                val opts = LlmInference.LlmInferenceOptions.builder()
                    .setModelPath(OfflineModels.file(m).absolutePath)
                    .setMaxTokens(1280)
                    .build()
                llm = LlmInference.createFromOptions(ctx, opts)
                loadedId = m.id
                lastError = ""
            } catch (t: Throwable) {
                lastError = (t.message ?: t.javaClass.simpleName).take(160)
                llm = null
            } finally {
                Prefs.sp.edit().putString("offline_loading", "").commit()
            }
        }
        return llm
    }

    fun unload() { llm?.close(); llm = null }

    private fun persona(): String {
        val d = Sync.load(Prefs.character)
        val sb = StringBuilder()
        if (d == null) {
            sb.append(tr("Du bist ${Prefs.character.ifEmpty { "Yume" }}, eine freundliche KI-Begleiterin. Antworte kurz, warm und natürlich.", "You are ${Prefs.character.ifEmpty { "Yume" }}, a friendly AI companion. Answer briefly, warmly and naturally."))
        } else {
            val name = d.optString("name", Prefs.character)
            val user = d.optString("user_name", "User")
            sb.append(tr("Du bist $name. Sprich als $name mit $user. Antworte kurz (1-3 Sätze), natürlich und in der Rolle.\n", "You are $name. Speak as $name with $user. Answer briefly (1-3 sentences), naturally and in character.\n"))
            listOf("description" to tr("Beschreibung", "Description"), "personality" to tr("Persönlichkeit", "Personality"), "scenario" to tr("Szenario", "Scenario"), "character_information" to "Info")
                .forEach { (k, label) -> d.optString(k).takeIf { it.isNotBlank() }?.let { sb.append(label).append(": ").append(it.take(900)).append('\n') } }
        }
        sb.append(tr("Hinweis: Du läufst gerade im Offline-Notfallmodus auf dem Handy, der große Rechner ist nicht erreichbar. Du hast keine Werkzeuge und keinen Internetzugriff. Sag das nur, wenn danach gefragt wird.", "Note: You are currently running in offline emergency mode on the phone, the big computer is not reachable. You have no tools and no internet access. Only say this if asked."))
        return sb.toString()
    }

    private fun prompt(user: String): String {
        val sb = StringBuilder("<|im_start|>system\n").append(persona()).append("<|im_end|>\n")
        val hist = ArrayList<Pair<String, String>>()
        Sync.load(Prefs.character)?.optJSONArray("history")?.let { a ->
            val from = maxOf(0, a.length() - 8)
            for (i in from until a.length()) a.optJSONObject(i)?.let { hist += it.optString("role") to it.optString("text") }
        }
        for ((role, text) in hist) sb.append("<|im_start|>").append(if (role == "user") "user" else "assistant").append('\n').append(text.take(500)).append("<|im_end|>\n")
        for ((u, a) in localHistory.takeLast(6)) sb.append("<|im_start|>user\n").append(u).append("<|im_end|>\n<|im_start|>assistant\n").append(a).append("<|im_end|>\n")
        sb.append("<|im_start|>user\n").append(user).append("<|im_end|>\n<|im_start|>assistant\n")
        return sb.toString()
    }

    suspend fun reply(user: String): String = withContext(Dispatchers.Default) {
        try {
            val e = engine(App.instance)
            if (e == null) {
                val m = OfflineModels.current()
                return@withContext when {
                    OfflineModels.broken(m) -> tr("Das Offline-Modell „${m.title.substringBefore(" (")}“ ließ sich auf diesem Handy nicht laden (vermutlich zu wenig Arbeitsspeicher). Wähle unter Offline das kleinere Modell.", "The offline model “${m.title.substringBefore(" (")}” could not be loaded on this phone (probably not enough memory). Choose the smaller model under Offline.")
                    !OfflineModels.installed(m) -> tr("Das Offline-Modell ist noch nicht geladen.", "The offline model has not been downloaded yet.")
                    else -> tr("Das Offline-Modell konnte nicht gestartet werden", "The offline model could not be started") + (if (lastError.isNotEmpty()) " ($lastError)." else ".")
                }
            }
            val out = e.generateResponse(prompt(user)).replace("<|im_end|>", "").trim()
            localHistory += user to out
            if (localHistory.size > 20) localHistory.removeAt(0)
            out.ifEmpty { tr("Hmm, dazu fällt mir gerade nichts ein.", "Hmm, nothing comes to mind about that right now.") }
        } catch (ex: Throwable) { tr("Offline-Antwort fehlgeschlagen: ${ex.message ?: ex.javaClass.simpleName}", "Offline answer failed: ${ex.message ?: ex.javaClass.simpleName}") }
    }
}
