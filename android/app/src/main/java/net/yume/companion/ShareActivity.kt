package net.yume.companion

import android.app.Activity
import android.content.Intent
import android.net.Uri
import android.os.Bundle
import android.provider.OpenableColumns
import android.widget.Toast
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import net.yume.companion.core.Host
import net.yume.companion.core.HostLink
import net.yume.companion.core.Prefs
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.Request
import okhttp3.RequestBody
import okhttp3.RequestBody.Companion.toRequestBody
import okio.BufferedSink
import okio.source
import org.json.JSONObject

/**
 * "Share -> Yume": a voice note (WhatsApp ...), picture, screenshot, PDF, text or link is sent to the PC's inbox. Yume then reads / listens to it
 * (and, if switched on, tells you right away what is in it). The activity has no screen: it only starts the upload and closes.
 */
class ShareActivity : Activity() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.IO)

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        Prefs.init(applicationContext)
        val i = intent
        val uris = ArrayList<Uri>()
        when (i?.action) {
            Intent.ACTION_SEND -> @Suppress("DEPRECATION") (i.getParcelableExtra<Uri>(Intent.EXTRA_STREAM))?.let { uris.add(it) }
            Intent.ACTION_SEND_MULTIPLE -> @Suppress("DEPRECATION") i.getParcelableArrayListExtra<Uri>(Intent.EXTRA_STREAM)?.let { uris.addAll(it) }
        }
        val text = i?.getStringExtra(Intent.EXTRA_TEXT).orEmpty()
        val subject = i?.getStringExtra(Intent.EXTRA_SUBJECT).orEmpty()
        if (uris.isEmpty() && text.isBlank()) { Toast.makeText(this, "Nichts zum Senden gefunden.", Toast.LENGTH_SHORT).show(); finish(); return }
        Toast.makeText(this, "Wird an Yume gesendet …", Toast.LENGTH_SHORT).show()
        val app = applicationContext
        scope.launch {
            val kinds = ArrayList<String>()
            var failed = ""
            if (Host.baseUrl.isEmpty()) { Host.resolve(app) }
            if (Host.baseUrl.isEmpty()) failed = "Der PC ist gerade nicht erreichbar."
            if (failed.isEmpty() && text.isNotBlank() && uris.isEmpty()) {
                val r = Host.postJson("/api/inbox/text", JSONObject().put("text", text).put("title", subject))
                if (r?.optBoolean("ok") == true) kinds.add("text") else failed = "Senden fehlgeschlagen."
            }
            for (u in uris) {
                if (failed.isNotEmpty()) break
                val kind = upload(app, u)
                if (kind != null) kinds.add(kind) else failed = "Senden fehlgeschlagen (Datei zu groß oder PC nicht erreichbar)."
            }
            CoroutineScope(Dispatchers.Main).let {
                it.launch {
                    Toast.makeText(app, if (failed.isEmpty()) "An Yume gesendet." else failed, Toast.LENGTH_LONG).show()
                }
            }
            if (failed.isEmpty() && Prefs.shareAutoAsk && kinds.isNotEmpty()) {
                var waited = 0
                while (!HostLink.connected && waited < 15_000) { delay(1000); waited += 1000 }
                if (HostLink.connected) HostLink.sendText(question(kinds.last()))
            }
        }
        finish()
    }

    /** the sentence sent to Yume after sharing: she reads the item with her inbox tool */
    private fun question(kind: String): String = when (kind) {
        "audio" -> "Ich habe dir gerade eine Sprachnachricht geteilt. Fass sie bitte kurz zusammen."
        "image" -> "Ich habe dir gerade ein Bild geteilt. Schau es dir an und sag mir, was drauf ist."
        "pdf", "word" -> "Ich habe dir gerade ein Dokument geteilt. Fass es bitte kurz zusammen."
        "text" -> "Ich habe dir gerade einen Text geteilt. Lies ihn bitte und sag mir kurz, worum es geht."
        else -> "Ich habe dir gerade eine Datei geteilt. Schau in deinen Eingang und sag mir, was es ist."
    }

    private fun upload(ctx: android.content.Context, uri: Uri): String? = try {
        var name = "datei"
        var size = -1L
        ctx.contentResolver.query(uri, null, null, null, null)?.use { c ->
            if (c.moveToFirst()) {
                c.getColumnIndex(OpenableColumns.DISPLAY_NAME).takeIf { it >= 0 }?.let { name = c.getString(it) ?: name }
                c.getColumnIndex(OpenableColumns.SIZE).takeIf { it >= 0 }?.let { size = c.getLong(it) }
            }
        }
        val mime = ctx.contentResolver.getType(uri) ?: "application/octet-stream"
        val body = object : RequestBody() {
            override fun contentType() = mime.toMediaTypeOrNull()
            override fun contentLength() = size
            override fun writeTo(sink: BufferedSink) { ctx.contentResolver.openInputStream(uri)?.use { sink.writeAll(it.source()) } }
        }
        val base = Host.baseUrl
        val url = "$base/api/inbox?name=" + Uri.encode(name) + "&mime=" + Uri.encode(mime)
        Host.clientFor(base).newBuilder().readTimeout(java.time.Duration.ofSeconds(180)).writeTimeout(java.time.Duration.ofSeconds(180)).build()
            .newCall(Request.Builder().url(url).header("X-Yume-Token", Prefs.token).post(body).build()).execute().use { r ->
                if (!r.isSuccessful) null else JSONObject(r.body?.string() ?: "{}").optString("kind", "file")
            }
    } catch (_: Exception) { null }
}
