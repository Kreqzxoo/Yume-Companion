// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.core

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.os.IBinder
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.withContext
import net.yume.companion.App
import net.yume.companion.MainActivity
import net.yume.companion.voice.VoiceService
import org.json.JSONObject
import java.io.File
import java.net.DatagramPacket
import java.net.DatagramSocket
import java.net.InetAddress
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Keeps the process (and the WebSocket to the PC) alive so the PC can reach the phone. */
class LinkService : Service() {
    override fun onBind(intent: Intent?): IBinder? = null
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val n: Notification = NotificationCompat.Builder(this, "link").setSmallIcon(android.R.drawable.ic_menu_share)
            .setContentTitle(tr("Yume ist verbunden", "Yume is connected")).setContentText(tr("Bereit für Anfragen vom PC", "Ready for requests from the PC"))
            .setContentIntent(open).setOngoing(true).setPriority(NotificationCompat.PRIORITY_MIN).build()
        startForeground(2, n)
        HostLink.start()
        return START_STICKY
    }
    override fun onDestroy() { HostLink.stop(); super.onDestroy() }

    companion object {
        fun ensure(ctx: Context) {
            if (!Prefs.paired) return
            if (Prefs.keepConnected) {
                try { ContextCompat.startForegroundService(ctx, Intent(ctx, LinkService::class.java)) } catch (_: Exception) { HostLink.start() }
            } else HostLink.start()
        }
    }
}

class BootReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        Prefs.init(ctx)
        try { net.yume.companion.device.YumeAlarms.rescheduleAll() } catch (_: Exception) {}     // alarms are forgotten by a restart
        if (!Prefs.paired) return
        LinkService.ensure(ctx)
        // Android 14+ does not allow starting a microphone service at boot: ask the user with one tap instead.
        if (Prefs.wakeEnabled) {
            val open = PendingIntent.getActivity(ctx, 1, Intent(ctx, MainActivity::class.java).putExtra("start_wake", true), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            val n = NotificationCompat.Builder(ctx, "info").setSmallIcon(android.R.drawable.ic_btn_speak_now)
                .setContentTitle(tr("Yume zuhören aktivieren", "Enable Yume listening")).setContentText(tr("Tippen, um das Wake Word wieder einzuschalten", "Tap to turn the wake word back on"))
                .setContentIntent(open).setAutoCancel(true).build()
            ctx.getSystemService(android.app.NotificationManager::class.java).notify(7, n)
        }
    }
}

/** Wake-on-LAN: magic packet into the home network, optionally a webhook for waking the PC from outside. */
object WakeOnLan {
    suspend fun wake(): String = withContext(Dispatchers.IO) {
        val macs = Prefs.macList()
        var sent = 0
        for (mac in macs) {
            val bytes = try { mac.split(':', '-').map { it.toInt(16).toByte() }.toByteArray() } catch (_: Exception) { continue }
            if (bytes.size != 6) continue
            val packet = ByteArray(6 + 16 * 6) { if (it < 6) 0xFF.toByte() else bytes[(it - 6) % 6] }
            for (target in broadcastTargets()) {
                try {
                    DatagramSocket().use { s ->
                        s.broadcast = true
                        s.send(DatagramPacket(packet, packet.size, InetAddress.getByName(target), 9))
                        s.send(DatagramPacket(packet, packet.size, InetAddress.getByName(target), 7))
                    }
                    sent++
                } catch (_: Exception) {}
            }
        }
        var hook = ""
        if (Prefs.wolWebhook.isNotEmpty()) {
            hook = try {
                Host.http.newCall(okhttp3.Request.Builder().url(Prefs.wolWebhook).build()).execute().use { " Webhook: ${it.code}" }
            } catch (e: Exception) { tr(" Webhook fehlgeschlagen", " Webhook failed") }
        }
        AgentLog.add("Wake-on-LAN gesendet ($sent Pakete).$hook")
        if (macs.isEmpty() && hook.isEmpty()) tr("Keine MAC-Adresse bekannt – bitte erneut koppeln.", "No MAC address known – please pair again.") else tr("Aufwecksignal gesendet.$hook", "Wake signal sent.$hook")
    }

    private fun broadcastTargets(): List<String> {
        val list = arrayListOf("255.255.255.255")
        try {
            for (ni in java.net.NetworkInterface.getNetworkInterfaces()) {
                for (ia in ni.interfaceAddresses) ia.broadcast?.hostAddress?.let { if (it !in list) list += it }
            }
        } catch (_: Exception) {}
        return list
    }
}

/** Short log of what the AI did on the phone (visible in the app, nothing leaves the phone). */
object AgentLog {
    data class Entry(val time: String, val text: String)
    private val _entries = MutableStateFlow<List<Entry>>(emptyList())
    val entries = _entries.asStateFlow()
    private val fmt = SimpleDateFormat("HH:mm:ss", Locale.getDefault())
    fun add(text: String) {
        val max = Prefs.agentLogMax.coerceAtLeast(20)
        _entries.value = (listOf(Entry(fmt.format(Date()), text)) + _entries.value).take(max)
    }
    fun clear() { _entries.value = emptyList() }
}

/** Character data for the offline emergency mode, fetched from the PC while it is reachable. */
object Sync {
    fun file(name: String): File = File(App.instance.filesDir, "sync_" + name.replace(Regex("[^A-Za-z0-9_-]"), "_") + ".json")

    fun load(name: String): JSONObject? = try { JSONObject(file(name).readText()) } catch (_: Exception) { null }

    suspend fun onConnected() = withContext(Dispatchers.IO) {
        try {
            if (Prefs.syncOnConnect && Prefs.offlineEnabled) refresh()
            OfflineHandover.pushBack()
        } catch (_: Exception) {}
    }

    fun refresh(): Boolean {
        if (Prefs.character.isEmpty()) return false
        val j = Host.getJson("/api/sync/" + java.net.URLEncoder.encode(Prefs.character, "UTF-8").replace("+", "%20")) ?: return false
        if (j.optString("status") != "ok") return false
        file(Prefs.character).writeText(j.toString())
        return true
    }
}

/** What was said offline is told to the PC once it is reachable again, so the conversation continues seamlessly. */
object OfflineHandover {
    private val file get() = File(App.instance.filesDir, "offline_turns.json")

    @Synchronized fun record(user: String, reply: String) {
        val arr = try { org.json.JSONArray(file.readText()) } catch (_: Exception) { org.json.JSONArray() }
        arr.put(JSONObject().put("u", user).put("a", reply))
        file.writeText(arr.toString())
    }

    @Synchronized fun pushBack() {
        if (!Prefs.offlineHandoverBack || !file.exists()) return
        val arr = try { org.json.JSONArray(file.readText()) } catch (_: Exception) { return }
        if (arr.length() == 0) { file.delete(); return }
        val sb = StringBuilder(tr("(Notiz: Während der PC nicht erreichbar war, haben wir auf dem Handy offline gesprochen. Kurzfassung – gib keine lange Antwort darauf.)\n", "(Note: While the PC was not reachable we talked offline on the phone. Summary – do not give a long answer to it.)\n"))
        for (i in 0 until arr.length()) {
            val o = arr.getJSONObject(i)
            sb.append("Ich: ").append(o.optString("u")).append("\nDu: ").append(o.optString("a")).append('\n')
        }
        if (HostLink.sendText(sb.toString().trim())) file.delete()
    }

    fun pending(): Int = try { org.json.JSONArray(file.readText()).length() } catch (_: Exception) { 0 }
}
