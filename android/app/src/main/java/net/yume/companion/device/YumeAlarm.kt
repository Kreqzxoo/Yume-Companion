// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.device

import net.yume.companion.core.tr

import android.app.AlarmManager
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.media.AudioAttributes
import android.media.RingtoneManager
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.app.NotificationCompat
import kotlinx.coroutines.delay
import net.yume.companion.App
import net.yume.companion.MainActivity
import net.yume.companion.core.ChatRepo
import net.yume.companion.core.HostLink
import net.yume.companion.core.LinkService
import net.yume.companion.core.Prefs
import net.yume.companion.ui.YumeTheme
import net.yume.companion.voice.AudioPlayer
import net.yume.companion.voice.PhoneTts
import org.json.JSONArray
import org.json.JSONObject
import java.util.Calendar
import java.util.Locale

/**
 * Yume's own alarm clock: she is asked ("weck mich morgen um 8"), the phone rings at the time and Yume wakes you with words she
 * makes up herself (answered by the PC with her usual voice) and asks how you slept. Without a connection to the PC the phone's
 * own voice says a short good-morning instead.
 */
object YumeAlarms {
    data class Alarm(val id: String, val at: Long, val label: String, val daily: Boolean)

    private const val KEY = "yume_alarms"
    private val ctx: Context get() = App.instance

    fun all(): List<Alarm> = try {
        val arr = JSONArray(Prefs.sp.getString(KEY, "[]"))
        (0 until arr.length()).map { arr.getJSONObject(it).let { o -> Alarm(o.getString("id"), o.getLong("at"), o.optString("label"), o.optBoolean("daily")) } }.sortedBy { it.at }
    } catch (_: Exception) { emptyList() }

    private fun save(list: List<Alarm>) {
        val arr = JSONArray()
        list.forEach { arr.put(JSONObject().put("id", it.id).put("at", it.at).put("label", it.label).put("daily", it.daily)) }
        Prefs.sp.edit().putString(KEY, arr.toString()).apply()
    }

    /** next moment with this clock time (today if it is still ahead, otherwise tomorrow), or the given [day] ("heute" / "morgen" / yyyy-MM-dd) */
    fun nextTime(hour: Int, minute: Int, day: String = ""): Long {
        val c = Calendar.getInstance().apply { set(Calendar.HOUR_OF_DAY, hour.coerceIn(0, 23)); set(Calendar.MINUTE, minute.coerceIn(0, 59)); set(Calendar.SECOND, 0); set(Calendar.MILLISECOND, 0) }
        val d = day.trim().lowercase()
        when {
            d == "tomorrow" || d == "morgen" -> c.add(Calendar.DAY_OF_YEAR, 1)
            d == "übermorgen" || d == "day_after_tomorrow" -> c.add(Calendar.DAY_OF_YEAR, 2)
            Regex("\\d{4}-\\d{2}-\\d{2}").matches(d) -> {
                val (y, m, dd) = d.split("-").map { it.toInt() }
                c.set(y, m - 1, dd)
            }
        }
        if (c.timeInMillis <= System.currentTimeMillis() + 5_000 && d != "heute" && d != "today") c.add(Calendar.DAY_OF_YEAR, 1)
        return c.timeInMillis
    }

    fun add(at: Long, label: String, daily: Boolean = false): Alarm {
        val a = Alarm(java.lang.Long.toHexString(System.nanoTime()).takeLast(8), at, label.take(60), daily)
        save(all() + a)
        schedule(a)
        return a
    }

    fun cancel(id: String): Boolean {
        val list = all()
        val a = list.firstOrNull { it.id == id } ?: return false
        unschedule(a)
        save(list - a)
        return true
    }

    fun cancelAll(): Int { val l = all(); l.forEach { unschedule(it) }; save(emptyList()); return l.size }

    private fun pending(a: Alarm) = PendingIntent.getBroadcast(
        ctx, a.id.hashCode(), Intent(ctx, AlarmReceiver::class.java).setAction("net.yume.companion.ALARM").putExtra("id", a.id),
        PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)

    fun schedule(a: Alarm) {
        val am = ctx.getSystemService(AlarmManager::class.java)
        val show = PendingIntent.getActivity(ctx, 0, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        // setAlarmClock needs no special permission and is exact even in Doze (it is what the clock app uses)
        am.setAlarmClock(AlarmManager.AlarmClockInfo(a.at, show), pending(a))
    }

    private fun unschedule(a: Alarm) { ctx.getSystemService(AlarmManager::class.java).cancel(pending(a)) }

    /** after a restart / app update the system forgets all alarms */
    fun rescheduleAll() {
        val now = System.currentTimeMillis()
        var list = all()
        list = list.map { a ->
            var at = a.at
            while (a.daily && at < now - 60_000) at += 24L * 3600_000       // a daily alarm missed while the phone was off moves on
            a.copy(at = at)
        }.filter { it.at >= now - 60_000 || it.daily }
        save(list)
        list.forEach { schedule(it) }
    }

    /** the alarm is ringing: a one-time alarm is used up, a daily one moves to tomorrow */
    fun fired(id: String): Alarm? {
        val list = all()
        val a = list.firstOrNull { it.id == id } ?: return null
        if (a.daily) {
            val next = a.copy(at = a.at + 24L * 3600_000)
            save(list.map { if (it.id == id) next else it }); schedule(next)
        } else save(list - a)
        return a
    }

    fun describe(a: Alarm): String =
        java.text.SimpleDateFormat(tr("EEEE, dd.MM. 'um' HH:mm", "EEEE, MM/dd 'at' HH:mm"), if (net.yume.companion.core.Lang.isEn) Locale.ENGLISH else Locale.GERMAN).format(java.util.Date(a.at)) + (if (a.label.isNotBlank()) " – ${a.label}" else "") + (if (a.daily) tr(" (täglich)", " (daily)") else "") + "  [id ${a.id}]"
}

class AlarmReceiver : BroadcastReceiver() {
    override fun onReceive(c: Context, intent: Intent) {
        Prefs.init(c)
        val a = YumeAlarms.fired(intent.getStringExtra("id") ?: return) ?: return
        LinkService.ensure(c)                         // the connection to the PC should be there when she has to speak
        val nm = c.getSystemService(NotificationManager::class.java)
        if (nm.getNotificationChannel("alarm") == null) nm.createNotificationChannel(NotificationChannel("alarm", tr("Wecker", "Alarm clock"), NotificationManager.IMPORTANCE_HIGH))
        val open = PendingIntent.getActivity(c, 3, Intent(c, AlarmActivity::class.java).putExtra("label", a.label).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = NotificationCompat.Builder(c, "alarm").setSmallIcon(android.R.drawable.ic_lock_idle_alarm)
            .setContentTitle(tr("Yume weckt dich", "Yume wakes you")).setContentText(a.label.ifBlank { tr("Aufstehen!", "Time to get up!") })
            .setCategory(NotificationCompat.CATEGORY_ALARM).setPriority(NotificationCompat.PRIORITY_MAX)
            .setFullScreenIntent(open, true).setContentIntent(open).setAutoCancel(true).build()
        nm.notify(21, n)
        try { c.startActivity(Intent(c, AlarmActivity::class.java).putExtra("label", a.label).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) } catch (_: Exception) {}
    }
}

class AlarmActivity : ComponentActivity() {
    private var ringtone: android.media.Ringtone? = null

    private fun ring(on: Boolean) {
        try {
            if (on && ringtone == null) {
                ringtone = RingtoneManager.getRingtone(this, RingtoneManager.getDefaultUri(RingtoneManager.TYPE_ALARM))?.apply {
                    audioAttributes = AudioAttributes.Builder().setUsage(AudioAttributes.USAGE_ALARM).setContentType(AudioAttributes.CONTENT_TYPE_SONIFICATION).build()
                    isLooping = true; play()
                }
            } else if (!on) { ringtone?.stop(); ringtone = null }
        } catch (_: Exception) {}
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setShowWhenLocked(true); setTurnScreenOn(true)
        window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        getSystemService(NotificationManager::class.java).cancel(21)
        val label = intent.getStringExtra("label").orEmpty()
        ChatRepo.start()
        ring(true)
        setContent {
            YumeTheme {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    var reply by remember { mutableStateOf("") }
                    var spoken by remember { mutableStateOf(false) }
                    val now = remember { java.text.SimpleDateFormat("HH:mm", Locale.getDefault()).format(java.util.Date()) }

                    // the words of Yume arrive from the PC (text + voice); the ringing makes room for them
                    LaunchedEffect(Unit) {
                        HostLink.events.collect { j ->
                            when (j.optString("type")) {
                                "message_start" -> { spoken = true; ring(false); reply = "" }
                                "chunk" -> { spoken = true; ring(false); reply += j.optString("text") }
                            }
                        }
                    }
                    LaunchedEffect(Unit) {
                        var waited = 0
                        while (!HostLink.connected && waited < 8000) { delay(250); waited += 250 }       // the link comes back first
                        val asked = HostLink.connected && HostLink.sendText(wakePrompt(now, label))
                        delay(if (asked) 14_000 else 500)
                        if (!spoken) {                       // PC asleep / no answer: the phone says good morning itself
                            ring(false)
                            reply = fallbackText(now, label)
                            PhoneTts.speak(reply)
                        }
                    }
                    Column(Modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        Text(now, fontSize = 64.sp, fontWeight = FontWeight.Bold)
                        if (label.isNotBlank()) Text(label, fontSize = 18.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                        Spacer(Modifier.height(20.dp))
                        Text(reply.ifBlank { tr("Yume ist gleich bei dir …", "Yume will be with you in a moment …") }, textAlign = TextAlign.Center, fontSize = 18.sp)
                        Spacer(Modifier.height(32.dp))
                        Button(onClick = { stopAll(); startActivity(Intent(this@AlarmActivity, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); finish() }, modifier = Modifier.fillMaxWidth()) { Text(tr("Mit Yume reden", "Talk to Yume")) }
                        OutlinedButton(onClick = { stopAll(); YumeAlarms.add(System.currentTimeMillis() + 10 * 60_000L, label.ifBlank { tr("Schlummern", "Snooze") }); finish() }, modifier = Modifier.fillMaxWidth()) { Text(tr("10 Minuten schlummern", "Snooze for 10 minutes")) }
                        TextButton(onClick = { stopAll(); finish() }) { Text(tr("Ich bin wach", "I'm awake")) }
                    }
                }
            }
        }
    }

    private fun stopAll() { ring(false); AudioPlayer.stop(); PhoneTts.stop() }

    override fun onDestroy() { ring(false); super.onDestroy() }

    private fun wakePrompt(time: String, label: String) =
        if (net.yume.companion.core.Lang.isEn)
            "[Automatic message from the alarm clock – the user asked you to wake them. It is now $time." +
                (if (label.isNotBlank()) " Reason: $label." else "") +
                " Wake them now in your own style with a few personal, freshly worded words (not too long, spoken), wish them a good start to the day and ask whether they slept well. Answer in the language you usually talk in.]"
        else
        "[Automatische Nachricht vom Wecker – der Nutzer hat dich gebeten, ihn zu wecken. Es ist jetzt $time Uhr." +
            (if (label.isNotBlank()) " Anlass: $label." else "") +
            " Weck ihn jetzt in deinem eigenen Stil mit ein paar persönlichen, frisch formulierten Worten (nicht zu lang, gesprochen), wünsch einen guten Start in den Tag und frag, ob er gut geschlafen hat. Antworte in der Sprache, in der ihr sonst redet.]"

    private fun fallbackText(time: String, label: String) =
        tr("Guten Morgen! Es ist $time Uhr.", "Good morning! It is $time.") + (if (label.isNotBlank()) " $label." else "") + tr(" Hast du gut geschlafen?", " Did you sleep well?")
}
