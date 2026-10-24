package net.yume.companion.device

import net.yume.companion.core.tr

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.net.wifi.WifiManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import net.yume.companion.App
import net.yume.companion.core.HostLink
import net.yume.companion.core.Prefs
import net.yume.companion.voice.PhoneTts

/**
 * "When I come home": as soon as the phone joins the home Wi-Fi, Yume carries out ONE sentence - exactly as if you had said it
 * ("Guten Abend", "Spiel meine Playlist Car", "Öffne Spotify", "Erinnere mich ..."). With the PC reachable the sentence goes to the PC
 * (the answer is spoken on the phone), otherwise the quick commands of the phone run it. At most once every 30 minutes.
 */
object Automations {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private const val MIN_GAP_MS = 30 * 60 * 1000L
    private var registered = false

    /** Name of the Wi-Fi the phone is on now ("" when unknown: needs the location permission and location switched on). */
    @Suppress("DEPRECATION")
    fun currentSsid(): String = try {
        val wm = App.instance.applicationContext.getSystemService(Context.WIFI_SERVICE) as WifiManager
        val s = wm.connectionInfo?.ssid.orEmpty().trim('"')
        if (s == "<unknown ssid>" || s == "0x") "" else s
    } catch (_: Exception) { "" }

    fun start() {
        if (registered) return
        registered = true
        try {
            val cm = App.instance.getSystemService(ConnectivityManager::class.java)
            cm.registerNetworkCallback(NetworkRequest.Builder().addTransportType(NetworkCapabilities.TRANSPORT_WIFI).build(), object : ConnectivityManager.NetworkCallback() {
                override fun onAvailable(network: Network) { scope.launch { onWifi() } }
            })
        } catch (_: Exception) { registered = false }
    }

    private suspend fun onWifi() {
        if (!Prefs.autoWifiOn || Prefs.autoWifiSsid.isBlank() || Prefs.autoWifiSentence.isBlank()) return
        delay(4000)                                                        // the name of the network is only readable a moment after the connection
        if (!currentSsid().equals(Prefs.autoWifiSsid.trim(), ignoreCase = true)) return
        val now = System.currentTimeMillis()
        if (now - Prefs.autoWifiLast < MIN_GAP_MS) return
        Prefs.autoWifiLast = now
        run(Prefs.autoWifiSentence.trim())
    }

    /** Runs a sentence like a spoken command (also used by the settings "test" button). Returns what happened, for display. */
    suspend fun run(sentence: String): String {
        var waited = 0
        while (!HostLink.connected && waited < 40_000) { delay(2000); waited += 2000 }    // the PC needs a few seconds after arriving at home
        if (HostLink.connected) {
            HostLink.sendText(sentence)
            return tr("An den PC geschickt: $sentence", "Sent to the PC: $sentence")
        }
        val cmd = QuickCommands.detect(sentence) ?: return tr("Der PC ist nicht erreichbar und das ist kein Schnellbefehl: $sentence", "The PC is not reachable and this is not a quick command: $sentence")
        val answer = try { cmd.run() } catch (e: Exception) { tr("Das hat nicht geklappt.", "That did not work.") }
        PhoneTts.speak(answer)
        return answer
    }
}
