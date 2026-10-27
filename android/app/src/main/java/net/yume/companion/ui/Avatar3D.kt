// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.ui

import net.yume.companion.core.tr

import android.annotation.SuppressLint
import android.webkit.JavascriptInterface
import android.webkit.WebChromeClient
import android.webkit.WebResourceRequest
import android.webkit.WebResourceResponse
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.yume.companion.App
import net.yume.companion.core.Host
import net.yume.companion.core.HostLink
import net.yume.companion.core.Prefs
import net.yume.companion.voice.AudioPlayer
import okhttp3.Request
import java.io.ByteArrayInputStream
import java.io.File
import java.io.FileInputStream

private fun enc(s: String) = java.net.URLEncoder.encode(s, "UTF-8").replace("+", "%20")

/** 3D models (VRM) of the PC, downloaded once and then animated on the phone itself. */
object VrmStore {
    data class Model(val name: String, val size: Long)

    private val dir get() = File(App.instance.filesDir, "vrm").also { it.mkdirs() }
    private val animDir get() = File(App.instance.filesDir, "vrm_anim").also { it.mkdirs() }
    const val NONE = "-"

    fun chosen(character: String): String = Prefs.sp.getString("vrm_model_" + character, "") ?: ""
    fun choose(character: String, name: String) { Prefs.sp.edit().putString("vrm_model_" + character, name).apply() }
    fun file(name: String) = File(dir, File(name).name)
    /** a real VRM is a glTF binary: a half-written or foreign file counts as "not downloaded" */
    fun downloaded(name: String) = name.isNotEmpty() && name != NONE && file(name).let { it.isFile && it.length() > 1000 && hasGlbHeader(it) }
    private fun hasGlbHeader(f: File): Boolean = try { f.inputStream().use { i -> val b = ByteArray(4); i.read(b) == 4 && String(b, Charsets.ISO_8859_1) == "glTF" } } catch (_: Exception) { false }
    fun invalidate(name: String) { file(name).delete() }
    /** why the last download failed (shown to the user) */
    @Volatile var lastError = ""
    fun downloadedModels(): List<Model> = dir.listFiles { f -> f.name.endsWith(".vrm", true) }?.map { Model(it.name, it.length()) } ?: emptyList()

    /** (models offered by the PC, the one configured for this character on the PC) */
    suspend fun list(character: String): Pair<List<Model>, String>? = withContext(Dispatchers.IO) {
        val j = Host.getJson("/api/avatar/models?character=" + enc(character)) ?: return@withContext null
        val arr = j.optJSONArray("models") ?: return@withContext null
        (0 until arr.length()).map { Model(arr.getJSONObject(it).getString("name"), arr.getJSONObject(it).optLong("size")) } to j.optString("current")
    }

    suspend fun download(name: String, progress: (Float) -> Unit = {}): Boolean = withContext(Dispatchers.IO) {
        if (downloaded(name)) return@withContext true
        val base = Host.baseUrl
        lastError = ""
        if (base.isEmpty()) { lastError = tr("kein PC verbunden", "no PC connected"); return@withContext false }
        try {
            val tmp = File(dir, File(name).name + ".part")
            Host.clientFor(base).newBuilder().readTimeout(java.time.Duration.ofSeconds(120)).build()
                .newCall(Request.Builder().url("$base/api/avatar/model?name=" + enc(name)).header("X-Yume-Token", Prefs.token).build()).execute().use { r ->
                    if (!r.isSuccessful) {
                        lastError = if (r.code == 404) tr("der PC hat dieses Modell nicht (Ordner assets/emotions/vrm)", "the PC does not have this model (folder assets/emotions/vrm)") else tr("PC antwortet mit Fehler ${r.code}", "PC answers with error ${r.code}")
                        return@withContext false
                    }
                    val total = r.body?.contentLength()?.coerceAtLeast(1) ?: 1
                    var read = 0L
                    r.body!!.byteStream().use { inp -> tmp.outputStream().use { out ->
                        val buf = ByteArray(1 shl 16)
                        while (true) { val n = inp.read(buf); if (n <= 0) break; out.write(buf, 0, n); read += n; progress((read.toFloat() / total).coerceAtMost(1f)) }
                    } }
                }
            file(name).delete()
            val ok = tmp.renameTo(file(name)) && downloaded(name)
            if (!ok) { file(name).delete(); tmp.delete(); lastError = tr("Datei unvollständig oder kein VRM-Modell", "File incomplete or not a VRM model") }
            ok
        } catch (e: Exception) { lastError = e.message ?: e.javaClass.simpleName; false }
    }

    /** Body animation clips (idle, emotions) are fetched from the PC the first time and cached on the phone. */
    fun animation(name: String): File? {
        val f = File(animDir, File(name).name)
        if (f.isFile && f.length() > 100) return f
        val base = Host.baseUrl
        if (base.isEmpty()) return null
        return try {
            Host.clientFor(base).newCall(Request.Builder().url("$base/vrm/expressions/" + enc(f.name)).build()).execute().use { r ->
                if (!r.isSuccessful) return null
                f.writeBytes(r.body!!.bytes()); f
            }
        } catch (_: Exception) { null }
    }
}

private const val VHOST = "yume.app"

private fun mime(path: String) = when {
    path.endsWith(".js") || path.endsWith(".mjs") -> "text/javascript"
    path.endsWith(".html") -> "text/html"
    path.endsWith(".json") -> "application/json"
    else -> "application/octet-stream"
}

private fun response(mime: String, stream: java.io.InputStream?, status: Int = 200): WebResourceResponse {
    val body = stream ?: ByteArrayInputStream(ByteArray(0))
    return WebResourceResponse(mime, null, if (stream == null) 404 else status, if (stream == null) "Not Found" else "OK",
        mapOf("Access-Control-Allow-Origin" to "*", "Cache-Control" to "no-store"), body)
}

/** Serves the page, the 3D libraries (inside the APK), the downloaded model and the cached animation clips under https://yume.app/ . */
private class AvatarClient(val onLog: (String) -> Unit) : WebViewClient() {
    override fun shouldInterceptRequest(view: WebView, request: WebResourceRequest): WebResourceResponse? {
        val uri = request.url
        if (uri.host != VHOST) return response("text/plain", null)          // the avatar page never talks to the internet
        val path = uri.path ?: "/"
        return try {
            when {
                path == "/avatar.html" -> response("text/html", App.instance.assets.open("avatar.html"))
                path.startsWith("/vrm/modules/") -> response(mime(path), App.instance.assets.open(path.removePrefix("/")))
                path.startsWith("/model/") -> VrmStore.file(Uri_decode(path.removePrefix("/model/"))).takeIf { it.isFile }?.let { response("application/octet-stream", FileInputStream(it)) } ?: response("text/plain", null)
                path.startsWith("/app/utils/emotions/vrm/expressions/") ->
                    VrmStore.animation(Uri_decode(path.substringAfterLast('/')))?.let { response("application/octet-stream", FileInputStream(it)) } ?: response("text/plain", null)
                else -> response("text/plain", null)
            }
        } catch (e: Exception) { onLog("intercept ${path}: ${e.message}"); response("text/plain", null) }
    }
}

private fun Uri_decode(s: String): String = try { java.net.URLDecoder.decode(s.replace("+", "%2B"), "UTF-8") } catch (_: Exception) { s }

/**
 * The avatar page is expensive to start (3D libraries, model, animation clips). It therefore lives as ONE WebView for the whole app run:
 * switching tabs or opening the call screen only moves it, so the character stays loaded instead of popping in again.
 */
@SuppressLint("SetJavaScriptEnabled")
private object AvatarHolder {
    private var view: WebView? = null
    private var model = ""
    private var loadedModel = false
    private var onState: (Boolean) -> Unit = {}
    private var onLog: (String) -> Unit = {}

    fun isLoaded(name: String) = view != null && model == name && loadedModel

    fun obtain(c: android.content.Context, name: String, state: (Boolean) -> Unit, log: (String) -> Unit): WebView {
        onState = state; onLog = log
        view?.let { v ->
            if (model == name) {
                (v.parent as? android.view.ViewGroup)?.removeView(v)
                v.onResume()
                if (loadedModel) v.post { state(true) }
                return v
            }
            (v.parent as? android.view.ViewGroup)?.removeView(v)
            v.destroy(); view = null
        }
        model = name; loadedModel = false
        val v = WebView(c).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.allowFileAccess = false
            settings.mediaPlaybackRequiresUserGesture = true
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_NEVER_ALLOW
            setBackgroundColor(0x00000000)
            addJavascriptInterface(LocalAvatarBridge({ _, ok -> post { loadedModel = ok; onState(ok) } }, { m -> post { onLog(m) } }), "YumeBridge")
            webViewClient = AvatarClient { m -> post { onLog(m) } }
            webChromeClient = object : WebChromeClient() {
                // the page's alert() must not pop up as a dialog on the phone: the problem is logged and the picture stays
                override fun onJsAlert(view: WebView?, url: String?, message: String?, result: android.webkit.JsResult?): Boolean { post { onLog(message ?: "") }; result?.confirm(); return true }
                override fun onConsoleMessage(m: android.webkit.ConsoleMessage): Boolean { if (m.messageLevel() == android.webkit.ConsoleMessage.MessageLevel.ERROR) post { onLog(m.message()) }; return true }
            }
            loadUrl("https://$VHOST/avatar.html?model=" + java.net.URLEncoder.encode("/model/" + enc(name), "UTF-8") + "&transparent=1&static=1&bg=1")
        }
        view = v
        return v
    }

    /** The screen showing the avatar went away: keep the page, just let it rest. */
    fun park(v: WebView) {
        if (v === view) { try { v.onPause() } catch (_: Exception) {} }
        else v.destroy()
    }
}

/** true when the page for [name] is already running (no waiting, no flicker when a screen shows it again) */
fun avatarReady(name: String) = AvatarHolder.isLoaded(name)

class LocalAvatarBridge(private val state: (String, Boolean) -> Unit, private val log: (String) -> Unit) {
    @JavascriptInterface fun avatarState(mode: String, ok: Boolean) { state(mode, ok) }
    @JavascriptInterface fun log(msg: String) { log(msg) }
}

/**
 * The character's own 3D model, rendered and animated on the phone (breathing, blinking, idle gestures, emotions from the chat,
 * lip sync from the voice). Transparent, so the animated background shines through.
 */
@SuppressLint("SetJavaScriptEnabled")
@Composable
fun LocalAvatar(modelName: String, modifier: Modifier, zoom: Int, onReady: (Boolean) -> Unit, onLog: (String) -> Unit = {}, appState: String? = null) {
    var web by remember { mutableStateOf<WebView?>(null) }
    var loaded by remember { mutableStateOf(AvatarHolder.isLoaded(modelName)) }
    val ready by rememberUpdatedState(onReady)
    val logger by rememberUpdatedState(onLog)
    val bodyAnim = Prefs.avatarBodyAnim

    fun js(code: String) { web?.post { try { web?.evaluateJavascript(code, null) } catch (_: Exception) {} } }

    AndroidView(modifier = modifier, factory = { c ->
        AvatarHolder.obtain(c, modelName, { ok -> loaded = ok; ready(ok) }, { m -> logger(m) }).also { web = it }
    }, onRelease = { AvatarHolder.park(it); web = null })

    // size of the model in its frame
    LaunchedEffect(zoom, loaded, web) { if (loaded) js("window.setZoom && setZoom(${zoom / 100.0})") }

    // listening / thinking pose (calls)
    LaunchedEffect(appState, loaded, web) { if (loaded && appState != null) js("window.setAppState && setAppState('$appState')") }

    // emotions of the chat -> face, head pose and (optionally) a body animation
    LaunchedEffect(web) {
        HostLink.events.collect { j ->
            when (j.optString("type")) {
                "emotion_changed" -> {
                    val e = j.optString("emotion").lowercase().filter { it.isLetter() }
                    if (e.isNotEmpty()) {
                        js("window.setEmotion && setEmotion('$e', 1.0)")
                        if (bodyAnim) js("window.loadFBX && loadFBX('/app/utils/emotions/vrm/expressions/$e.fbx')")
                    }
                }
                "message_start" -> js("window.setAppState && setAppState('PROCESSING')")
                "message_end" -> js("window.setAppState && setAppState('STOPPED')")
                "avatar_telemetry" -> if (!AudioPlayer.playing) js("window.setMouthOpen && setMouthOpen(${j.optDouble("volume", 0.0).coerceIn(0.0, 1.0)})")
            }
        }
    }
    // lip sync from the voice that plays on this phone
    LaunchedEffect(web) {
        AudioPlayer.level.collect { v -> js("window.setMouthOpen && setMouthOpen(${"%.2f".format(java.util.Locale.US, v)})") }
    }
}

/** Choose (and download) the 3D model for a character. */
@Composable
fun VrmPickerDialog(character: String, onDismiss: () -> Unit, onChosen: () -> Unit) {
    val scope = rememberCoroutineScope()
    var models by remember { mutableStateOf<List<VrmStore.Model>?>(null) }
    var hostCurrent by remember { mutableStateOf("") }
    var progress by remember { mutableStateOf<Pair<String, Float>?>(null) }
    var error by remember { mutableStateOf("") }
    val offline = remember { VrmStore.downloadedModels() }

    LaunchedEffect(character) {
        val r = VrmStore.list(character)
        if (r != null) { models = r.first; hostCurrent = r.second } else models = emptyList()
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(tr("3D-Modell für $character", "3D model for $character")) },
        text = {
            Column {
                Text(tr("Das Modell kommt vom PC (Ordner assets\\emotions\\vrm), wird einmal geladen und läuft dann auf dem Handy – mit Mimik, Lippenbewegung und Idle-Bewegungen.", "The model comes from the PC (folder assets\\emotions\\vrm), is downloaded once and then runs on the phone – with facial expressions, lip movement and idle movements."), fontSize = 12.sp)
                Spacer(Modifier.height(8.dp))
                val list = (models ?: emptyList()).ifEmpty { offline }
                if (models == null) CircularProgressIndicator()
                if (models != null && list.isEmpty()) Text(tr("Keine Modelle gefunden. Ist der PC erreichbar und liegt eine .vrm-Datei im Ordner assets\\emotions\\vrm?", "No models found. Is the PC reachable and is there a .vrm file in the folder assets\\emotions\\vrm?"), color = MaterialTheme.colorScheme.error)
                LazyColumn(Modifier.heightIn(max = 300.dp)) {
                    items(list) { m ->
                        val sel = VrmStore.chosen(character) == m.name
                        Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
                            Column(Modifier.weight(1f)) {
                                Text(m.name.removeSuffix(".vrm"), color = if (sel) Pink else MaterialTheme.colorScheme.onSurface)
                                Text("%.1f MB".format(m.size / 1_048_576.0) + (if (VrmStore.downloaded(m.name)) tr(" · geladen", " · downloaded") else "") + (if (m.name == hostCurrent) tr(" · am PC gewählt", " · chosen on the PC") else ""), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            }
                            val p = progress
                            if (p != null && p.first == m.name) LinearProgressIndicator(progress = { p.second }, Modifier.width(70.dp))
                            else TextButton(onClick = {
                                scope.launch {
                                    error = ""
                                    progress = m.name to 0f
                                    val ok = VrmStore.download(m.name) { progress = m.name to it }
                                    progress = null
                                    if (ok) { VrmStore.choose(character, m.name); onChosen() } else error = tr("Download fehlgeschlagen: ", "Download failed: ") + VrmStore.lastError.ifEmpty { tr("PC erreichbar?", "PC reachable?") }
                                }
                            }) { Text(if (sel) tr("Aktiv", "Active") else tr("Wählen", "Choose")) }
                        }
                    }
                }
                if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(tr("Schließen", "Close")) } },
        dismissButton = { TextButton(onClick = { VrmStore.choose(character, VrmStore.NONE); onChosen() }) { Text(tr("Nur Bild", "Picture only")) } },
    )
}
