package net.yume.companion.core

import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Build
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONArray
import org.json.JSONObject
import java.net.URLDecoder
import java.util.concurrent.TimeUnit

/** Parsed content of the QR code: yume://pair?v=1&h=<host_id>&n=<name>&c=<code>&l=<local>&e=<external>&m=<macs> */
data class PairInfo(val hostId: String, val name: String, val code: String, val local: String, val external: String, val macs: String)

object Host {
    val http: OkHttpClient = OkHttpClient.Builder()
        .connectTimeout(4, TimeUnit.SECONDS).readTimeout(120, TimeUnit.SECONDS).writeTimeout(60, TimeUnit.SECONDS).build()
    private val quick: OkHttpClient = http.newBuilder().connectTimeout(2, TimeUnit.SECONDS).readTimeout(3, TimeUnit.SECONDS).build()

    private val privateHost = Regex("""^(10\.|192\.168\.|172\.(1[6-9]|2[0-9]|3[01])\.|169\.254\.).*|.*\.local$""")

    /**
     * Connections to a home-network address must leave through the Wi-Fi / Ethernet network. Without this Android may send them over
     * mobile data when the Wi-Fi is judged "without internet" or a VPN is active, and the PC then seems unreachable.
     */
    fun clientFor(url: String, base: OkHttpClient = http): OkHttpClient {
        val host = try { java.net.URI(url).host ?: "" } catch (_: Exception) { "" }
        if (!privateHost.matches(host)) return base
        return try {
            val cm = net.yume.companion.App.instance.getSystemService(ConnectivityManager::class.java)
            val lan = cm.allNetworks.firstOrNull { n ->
                cm.getNetworkCapabilities(n)?.let { it.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || it.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET) } == true
            }
            if (lan != null) base.newBuilder().socketFactory(lan.socketFactory).build() else base
        } catch (_: Exception) { base }
    }

    /** "local", "external" or "offline" */
    @Volatile var where: String = "offline"
    @Volatile var baseUrl: String = ""

    fun parsePairUrl(raw: String): PairInfo? {
        val text = raw.trim()
        if (!text.startsWith("yume://pair")) return null
        val q = text.substringAfter('?', "")
        val map = HashMap<String, String>()
        for (part in q.split('&')) {
            val k = part.substringBefore('=')
            val v = part.substringAfter('=', "")
            map[k] = try { URLDecoder.decode(v, "UTF-8") } catch (_: Exception) { v }
        }
        val code = map["c"] ?: return null
        return PairInfo(map["h"] ?: "", map["n"] ?: "Yume PC", code, map["l"] ?: "", map["e"] ?: "", map["m"] ?: "")
    }

    fun normalize(url: String): String {
        var u = url.trim().trimEnd('/')
        if (u.isEmpty()) return ""
        if (!u.startsWith("http://") && !u.startsWith("https://")) u = "http://$u"
        return u
    }

    /** Is [base] reachable and really our Yume PC? */
    fun ping(base: String, expectedHostId: String = Prefs.hostId): Boolean {
        if (base.isEmpty()) return false
        return try {
            clientFor(base, quick).newCall(Request.Builder().url("$base/api/ping").build()).execute().use { r ->
                if (!r.isSuccessful) return false
                val j = JSONObject(r.body?.string() ?: return false)
                j.optString("api") == "yume-mobile-v1" && (expectedHostId.isEmpty() || j.optString("host_id") == expectedHostId)
            }
        } catch (_: Exception) { false }
    }

    fun onWifi(ctx: Context): Boolean {
        val cm = ctx.getSystemService(ConnectivityManager::class.java)
        val caps = cm.getNetworkCapabilities(cm.activeNetwork ?: return false) ?: return false
        return caps.hasTransport(NetworkCapabilities.TRANSPORT_WIFI) || caps.hasTransport(NetworkCapabilities.TRANSPORT_ETHERNET)
    }

    /** Local network first (direct), otherwise the external domain (mobile data). */
    suspend fun resolve(ctx: Context): String? = withContext(Dispatchers.IO) {
        val local = normalize(Prefs.localUrl)
        val ext = normalize(Prefs.externalUrl)
        val order = ArrayList<Pair<String, String>>()
        val wifi = onWifi(ctx)
        if (local.isNotEmpty() && (wifi || Prefs.preferLocal)) order += "local" to local
        if (ext.isNotEmpty()) order += "external" to ext
        if (local.isNotEmpty() && order.none { it.first == "local" }) order += "local" to local
        for ((kind, url) in order) {
            if (ping(url)) { where = kind; baseUrl = url; Prefs.lastUrl = url; return@withContext url }
        }
        where = "offline"; baseUrl = ""
        null
    }

    // ------------------------------------------------------------ REST helpers (blocking, call from IO)
    private fun req(path: String): Request.Builder =
        Request.Builder().url(baseUrl + path).header("X-Yume-Token", Prefs.token)

    fun getJson(path: String): JSONObject? = try {
        clientFor(baseUrl).newCall(req(path).build()).execute().use { r -> if (r.isSuccessful) JSONObject(r.body?.string() ?: "{}") else null }
    } catch (_: Exception) { null }

    fun postJson(path: String, body: JSONObject = JSONObject()): JSONObject? = try {
        val rb = body.toString().toRequestBody("application/json".toMediaType())
        clientFor(baseUrl).newCall(req(path).post(rb).build()).execute().use { r -> if (r.isSuccessful) JSONObject(r.body?.string() ?: "{}") else null }
    } catch (_: Exception) { null }

    fun stopGeneration() { postJson("/api/generation/stop") }

    fun characters(): List<String> {
        val a: JSONArray = getJson("/api/characters")?.optJSONArray("characters") ?: return emptyList()
        return (0 until a.length()).map { a.getString(it) }
    }

    fun switchCharacter(name: String) { postJson("/api/character/switch", JSONObject().put("character", name)) }

    /** Sends a recorded utterance (WAV) to the PC: the PC transcribes it and answers in the chat. Returns the recognised text. */
    fun sendSpeech(wav: ByteArray, character: String, language: String, image: ByteArray? = null, speaker: String = ""): String? = try {
        val bb = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("character", character)
            .addFormDataPart("language", language)
            .addFormDataPart("audio", "speech.wav", wav.toRequestBody("audio/wav".toMediaType()))
        if (Quiet.active()) bb.addFormDataPart("mode", "quiet")
        if (speaker.isNotEmpty()) bb.addFormDataPart("speaker", speaker)
        if (image != null) bb.addFormDataPart("image", "frame.jpg", image.toRequestBody("image/jpeg".toMediaType()))      // video call
        val body = bb.build()
        clientFor(baseUrl).newCall(req("/api/voice/stt").post(body).build()).execute().use { r ->
            if (!r.isSuccessful) null else JSONObject(r.body?.string() ?: "{}").let { if (it.optString("status") == "ok") it.optString("text") else null }
        }
    } catch (_: Exception) { null }

    /** Speech to text only (interpreter mode): the PC transcribes, nothing is answered. */
    fun transcribe(wav: ByteArray, language: String): String? = try {
        val body = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("language", language)
            .addFormDataPart("audio", "speech.wav", wav.toRequestBody("audio/wav".toMediaType())).build()
        clientFor(baseUrl).newCall(req("/api/transcribe").post(body).build()).execute().use { r ->
            if (!r.isSuccessful) null else JSONObject(r.body?.string() ?: "{}").let { if (it.optBoolean("ok")) it.optString("text") else null }
        }
    } catch (_: Exception) { null }

    /** Phone screenshot / camera photo -> description by the PC's vision model. */
    fun describeImage(jpeg: ByteArray, prompt: String?): String? = try {
        val b = MultipartBody.Builder().setType(MultipartBody.FORM)
            .addFormDataPart("image", "img.jpg", jpeg.toRequestBody("image/jpeg".toMediaType()))
        if (!prompt.isNullOrEmpty()) b.addFormDataPart("prompt", prompt)
        clientFor(baseUrl).newCall(req("/api/vision/describe").post(b.build()).build()).execute().use { r ->
            if (!r.isSuccessful) null else JSONObject(r.body?.string() ?: "{}").optString("text")
        }
    } catch (_: Exception) { null }

    private fun explain(kind: String, code: Int): String = when (code) {
        403 -> tr("Der Code ist abgelaufen oder wurde schon benutzt (am PC einen neuen QR-Code erzeugen).", "The code has expired or was already used (create a new QR code on the PC).")
        429 -> tr("Zu viele Versuche. Bitte kurz warten.", "Too many attempts. Please wait a moment.")
        521, 522, 523, 524 -> tr("Cloudflare erreicht den PC nicht (Fehler $code) – läuft der Cloudflare-Tunnel / Yume auf dem PC?", "Cloudflare cannot reach the PC (error $code) – are the Cloudflare tunnel and Yume running on the PC?")
        530 -> tr("Die externe Domain ist bei Cloudflare nicht (mehr) eingerichtet (Fehler 530).", "The external domain is not (or no longer) set up at Cloudflare (error 530).")
        502, 503, 504 -> tr("Der Server hinter der Domain antwortet nicht (Fehler $code).", "The server behind the domain does not answer (error $code).")
        else -> tr("Fehler $code", "Error $code")
    }

    private fun explain(e: Exception): String = when (e) {
        is java.net.SocketTimeoutException, is java.net.ConnectException ->
            tr("keine Antwort – Firewall am PC blockiert (Port freigeben) oder Handy nicht im selben Netz", "no answer – firewall on the PC blocks it (open the port) or the phone is not in the same network")
        is java.net.UnknownHostException -> tr("Adresse nicht auffindbar", "Address not found")
        else -> e.message ?: e.javaClass.simpleName
    }

    /** Exchanges the one-time code of the QR for this phone's own revocable token. Tries the local address first, then the external domain. */
    suspend fun pair(info: PairInfo, deviceName: String, deviceId: String): Result<JSONObject> = withContext(Dispatchers.IO) {
        val candidates = listOf(tr("Heimnetz", "Home network") to info.local, tr("Extern", "External") to info.external).map { it.first to normalize(it.second) }.filter { it.second.isNotEmpty() }
        if (candidates.isEmpty()) return@withContext Result.failure(Exception(tr("Im QR-Code steht keine Adresse. Bitte am PC einen neuen Code erzeugen.", "The QR code contains no address. Please generate a new code on the PC.")))
        val problems = ArrayList<String>()
        for ((kind, base) in candidates) {
            try {
                val body = JSONObject().put("code", info.code).put("device_name", deviceName).put("device_id", deviceId).toString()
                    .toRequestBody("application/json".toMediaType())
                clientFor(base).newCall(Request.Builder().url("$base/api/pair").post(body).build()).execute().use { r ->
                    val txt = r.body?.string() ?: "{}"
                    if (r.isSuccessful) {
                        val j = JSONObject(txt)
                        if (j.optString("status") == "ok") {
                            Prefs.token = j.getString("token")
                            Prefs.hostId = j.optString("host_id", info.hostId)
                            Prefs.hostName = j.optString("host_name", info.name)
                            Prefs.deviceId = deviceId
                            Prefs.localUrl = info.local.ifEmpty { j.optString("local_url") }.let { if (it.isNotEmpty()) normalize(it) else normalize(base) }
                            if (info.external.isNotEmpty()) Prefs.externalUrl = normalize(info.external)
                            else if (Prefs.externalUrl.isEmpty()) Prefs.externalUrl = normalize(j.optString("remote_url"))
                            val macs = j.optJSONArray("macs")
                            Prefs.macs = if (macs != null) (0 until macs.length()).joinToString(",") { macs.getString(it) } else info.macs
                            val active = j.optString("active_character")
                            if (Prefs.character.isEmpty() && active.isNotEmpty()) Prefs.character = active
                            return@withContext Result.success(j)
                        }
                    }
                    problems += "$kind ($base): " + explain(kind, r.code)
                    if (r.code == 403 || r.code == 429) return@withContext Result.failure(Exception(explain(kind, r.code)))
                }
            } catch (e: Exception) { problems += "$kind ($base): " + explain(e) }
        }
        Result.failure(Exception(problems.joinToString("\n")))
    }

    fun unpair() {
        Prefs.token = ""; Prefs.hostId = ""; Prefs.deviceId = ""
        where = "offline"; baseUrl = ""
    }

    fun deviceName(): String = "${Build.MANUFACTURER.replaceFirstChar { it.uppercase() }} ${Build.MODEL}".take(48)
}
