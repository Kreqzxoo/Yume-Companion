// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.device

import net.yume.companion.core.tr

import android.content.Intent
import android.net.Uri
import android.util.Base64
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.yume.companion.App
import net.yume.companion.core.Host
import net.yume.companion.core.HostLink
import net.yume.companion.core.Link
import net.yume.companion.core.Prefs
import okhttp3.FormBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.security.MessageDigest
import java.security.SecureRandom

/**
 * Spotify via the Web API. The user only enters the Client ID of their own Spotify app and logs in once in the browser (PKCE: no secret
 * is needed or stored). Yume can then search and start music, pause, skip and tell what is playing. Playback control needs Spotify Premium.
 */
object Spotify {
    const val REDIRECT = "yume://spotify"
    private const val SCOPES = "user-read-playback-state user-modify-playback-state user-read-currently-playing"
    private val http = OkHttpClient()
    private val scope = CoroutineScope(Dispatchers.Main)

    var status by mutableStateOf("")
    var connected by mutableStateOf(false)

    private val sp get() = Prefs.sp
    fun init() { connected = sp.getString("spotify_refresh", "").orEmpty().isNotEmpty() }

    /** Phone and PC share ONE Spotify login: whichever side is logged in hands it to the other one as soon as they are connected. */
    fun watchHost() {
        scope.launch { HostLink.state.collect { s -> if (s == Link.CONNECTED) { delay(2000); syncWithHost() } } }
    }

    suspend fun syncWithHost() = withContext(Dispatchers.IO) {
        try {
            val j = Host.getJson("/api/spotify/credentials") ?: return@withContext
            val hostId = j.optString("client_id").trim(); val hostRefresh = j.optString("refresh_token")
            val myId = Prefs.spotifyClientId.trim(); val myRefresh = sp.getString("spotify_refresh", "").orEmpty()
            if (hostId.isNotEmpty() && hostRefresh.isNotEmpty()) {
                // the PC has the login: take it over when the phone has none, another app, or a login that does not work any more
                if (myRefresh.isEmpty() || myId != hostId || token() == null) {
                    Prefs.spotifyClientId = hostId
                    sp.edit().putString("spotify_refresh", hostRefresh).remove("spotify_access").remove("spotify_expires").apply()
                    withContext(Dispatchers.Main) { connected = true; status = tr("Spotify-Anmeldung vom PC übernommen.", "Spotify login adopted from the PC.") }
                }
            } else if (myRefresh.isNotEmpty() && myId.isNotEmpty()) {
                Host.postJson("/api/spotify/credentials", JSONObject().put("client_id", myId).put("refresh_token", myRefresh))
            }
        } catch (_: Exception) {}
    }

    private fun b64url(b: ByteArray) = Base64.encodeToString(b, Base64.URL_SAFE or Base64.NO_PADDING or Base64.NO_WRAP)

    fun loginIntent(): Intent? {
        val id = Prefs.spotifyClientId.trim()
        if (id.isEmpty()) return null
        val verifier = b64url(ByteArray(48).also { SecureRandom().nextBytes(it) })
        val state = b64url(ByteArray(12).also { SecureRandom().nextBytes(it) })
        sp.edit().putString("spotify_verifier", verifier).putString("spotify_state", state).apply()
        val challenge = b64url(MessageDigest.getInstance("SHA-256").digest(verifier.toByteArray()))
        val url = Uri.parse("https://accounts.spotify.com/authorize").buildUpon()
            .appendQueryParameter("client_id", id).appendQueryParameter("response_type", "code")
            .appendQueryParameter("redirect_uri", REDIRECT).appendQueryParameter("scope", SCOPES)
            .appendQueryParameter("code_challenge_method", "S256").appendQueryParameter("code_challenge", challenge)
            .appendQueryParameter("state", state).build()
        return Intent(Intent.ACTION_VIEW, url).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
    }

    /** The browser came back to yume://spotify?code=... */
    fun finishLogin(uri: Uri) {
        scope.launch {
            val err = uri.getQueryParameter("error")
            val code = uri.getQueryParameter("code")
            if (err != null || code == null) { status = tr("Anmeldung abgebrochen (${err ?: "kein Code"}).", "Login cancelled (${err ?: "no code"})."); return@launch }
            if (uri.getQueryParameter("state") != sp.getString("spotify_state", null)) { status = "Anmeldung abgelehnt (falscher state)."; return@launch }
            status = tr("Melde bei Spotify an …", "Signing in to Spotify …")
            val res = withContext(Dispatchers.IO) {
                tokenCall(FormBody.Builder().add("grant_type", "authorization_code").add("code", code).add("redirect_uri", REDIRECT)
                    .add("client_id", Prefs.spotifyClientId.trim()).add("code_verifier", sp.getString("spotify_verifier", "").orEmpty()).build())
            }
            status = if (res == null) tr("Spotify hat die Anmeldung nicht akzeptiert. Stimmt die Client-ID und ist „yume://spotify“ als Redirect-URI in deiner Spotify-App eingetragen?", "Spotify did not accept the login. Is the client ID correct and is \"yume://spotify\" entered as the redirect URI in your Spotify app?")
            else tr("Mit Spotify verbunden.", "Connected to Spotify.")
        }
    }

    fun logout() {
        sp.edit().remove("spotify_refresh").remove("spotify_access").remove("spotify_expires").apply()
        connected = false; status = tr("Von Spotify getrennt.", "Disconnected from Spotify.")
    }

    private fun tokenCall(form: FormBody): String? = try {
        http.newCall(Request.Builder().url("https://accounts.spotify.com/api/token").post(form).build()).execute().use { r ->
            if (!r.isSuccessful) return null
            val j = JSONObject(r.body!!.string())
            val e = sp.edit().putString("spotify_access", j.getString("access_token"))
                .putLong("spotify_expires", System.currentTimeMillis() + (j.optLong("expires_in", 3600) - 60) * 1000)
            if (j.optString("refresh_token").isNotEmpty()) e.putString("spotify_refresh", j.getString("refresh_token"))
            e.apply()
            connected = true
            j.getString("access_token")
        }
    } catch (_: Exception) { null }

    private fun token(): String? {
        if (System.currentTimeMillis() < sp.getLong("spotify_expires", 0)) sp.getString("spotify_access", null)?.let { return it }
        val refresh = sp.getString("spotify_refresh", "").orEmpty()
        if (refresh.isEmpty()) return null
        return tokenCall(FormBody.Builder().add("grant_type", "refresh_token").add("refresh_token", refresh).add("client_id", Prefs.spotifyClientId.trim()).build())
    }

    private class Reply(val code: Int, val body: String)

    private fun api(method: String, path: String, json: String? = null): Reply {
        val t = token() ?: return Reply(401, "")
        val body = if (method == "GET") null else (json ?: "").toRequestBody(null)
        http.newCall(Request.Builder().url("https://api.spotify.com/v1$path").header("Authorization", "Bearer $t").method(method, body).build()).execute().use { r ->
            return Reply(r.code, r.body?.string().orEmpty())
        }
    }

    private fun enc(s: String) = Uri.encode(s)

    private suspend fun deviceId(): String? {
        suspend fun look(): String? {
            val r = withContext(Dispatchers.IO) { api("GET", "/me/player/devices") }
            val arr = try { JSONObject(r.body).optJSONArray("devices") } catch (_: Exception) { null } ?: return null
            var first: String? = null
            for (i in 0 until arr.length()) {
                val d = arr.getJSONObject(i)
                if (d.optBoolean("is_active")) return d.optString("id")
                if (first == null) first = d.optString("id")
            }
            return first
        }
        look()?.let { return it }
        // Spotify is not running: start the app and wait for it to register as a device
        val launch = App.instance.packageManager.getLaunchIntentForPackage("com.spotify.music") ?: return null
        App.instance.startActivity(launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        repeat(6) { delay(1500); look()?.let { return it } }
        return null
    }

    private fun explain(r: Reply): String = when (r.code) {
        401 -> tr("Spotify ist nicht verbunden (in den App-Einstellungen anmelden).", "Spotify is not connected (sign in under the app settings).")
        403 -> tr("Spotify verweigert das – für die Fernsteuerung ist Spotify Premium nötig.", "Spotify refuses this – remote control needs Spotify Premium.")
        404 -> tr("Kein Spotify-Gerät gefunden. Spotify auf dem Handy öffnen und nochmal versuchen.", "No Spotify device found. Open Spotify on the phone and try again.")
        else -> tr("Spotify-Fehler ${r.code}.", "Spotify error ${r.code}.")
    }

    suspend fun play(query: String, kind: String): String = withContext(Dispatchers.IO) {
        if (token() == null) return@withContext tr("Spotify ist nicht verbunden (in den App-Einstellungen anmelden).", "Spotify is not connected (sign in under the app settings).")
        val type = if (kind in listOf("track", "album", "playlist", "artist")) kind else "track"
        val s = api("GET", "/search?q=${enc(query)}&type=$type&limit=5")
        if (s.code != 200) return@withContext explain(s)
        val items = JSONObject(s.body).optJSONObject(type + "s")?.optJSONArray("items")
        var hit: JSONObject? = null
        if (items != null) for (i in 0 until items.length()) { val o = items.optJSONObject(i); if (o != null) { hit = o; break } }
        val h = hit ?: return@withContext tr("Nichts zu „$query“ gefunden.", "Nothing found for “$query”.")
        val uri = h.getString("uri")
        val title = h.optString("name") + (h.optJSONArray("artists")?.optJSONObject(0)?.optString("name")?.let { " – $it" } ?: "")
        val payload = if (type == "track") JSONObject().put("uris", org.json.JSONArray().put(uri)) else JSONObject().put("context_uri", uri)
        var r = api("PUT", "/me/player/play", payload.toString())
        if (r.code == 404) {
            val dev = deviceId() ?: return@withContext explain(r)
            r = api("PUT", "/me/player/play?device_id=${enc(dev)}", payload.toString())
        }
        if (r.code in 200..204) tr("Spielt jetzt: $title", "Now playing: $title") else explain(r)
    }

    suspend fun control(c: String): String = withContext(Dispatchers.IO) {
        val (method, path, said) = when (c) {
            "pause" -> Triple("PUT", "/me/player/pause", "pausiert")
            "resume", "play" -> Triple("PUT", "/me/player/play", tr("läuft weiter", "resumed"))
            "next" -> Triple("POST", "/me/player/next", tr("nächster Titel", "next track"))
            "previous" -> Triple("POST", "/me/player/previous", "voriger Titel")
            else -> return@withContext tr("Unbekannte Spotify-Steuerung: $c", "Unknown Spotify control: $c")
        }
        val r = api(method, path)
        if (r.code in 200..204) "Spotify: $said" else explain(r)
    }

    suspend fun volume(level: Int): String = withContext(Dispatchers.IO) {
        val r = api("PUT", "/me/player/volume?volume_percent=${level.coerceIn(0, 100)}")
        if (r.code in 200..204) tr("Spotify-Lautstärke $level %", "Spotify volume $level %") else explain(r)
    }

    suspend fun now(): String = withContext(Dispatchers.IO) {
        val r = api("GET", "/me/player/currently-playing")
        if (r.code == 204 || r.body.isEmpty()) return@withContext if (r.code == 401) explain(r) else tr("Gerade läuft nichts auf Spotify.", "Nothing is playing on Spotify right now.")
        if (r.code != 200) return@withContext explain(r)
        val j = JSONObject(r.body)
        val item = j.optJSONObject("item") ?: return@withContext tr("Gerade läuft nichts auf Spotify.", "Nothing is playing on Spotify right now.")
        (if (j.optBoolean("is_playing")) tr("Läuft: ", "Playing: ") else tr("Pausiert: ", "Paused: ")) + item.optString("name") +
            (item.optJSONArray("artists")?.optJSONObject(0)?.optString("name")?.let { " – $it" } ?: "")
    }
}
