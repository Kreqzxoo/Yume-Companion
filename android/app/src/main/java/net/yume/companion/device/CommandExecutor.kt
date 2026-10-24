package net.yume.companion.device

import android.Manifest
import android.app.NotificationManager
import android.app.PendingIntent
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.graphics.Bitmap
import android.hardware.camera2.CameraManager
import android.location.LocationManager
import android.media.AudioManager
import android.net.Uri
import android.os.BatteryManager
import android.provider.AlarmClock
import android.provider.CalendarContract
import android.provider.ContactsContract
import android.telephony.SmsManager
import android.util.Base64
import android.view.KeyEvent
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.delay
import kotlinx.coroutines.withTimeoutOrNull
import net.yume.companion.App
import net.yume.companion.MainActivity
import net.yume.companion.core.AgentLog
import net.yume.companion.core.Prefs
import net.yume.companion.voice.PhoneTts
import org.json.JSONArray
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.util.Calendar

/** Executes the `phone` tool actions of the AI (see PhoneControlTool on the PC). Always returns {ok, data|error, image_b64?}. */
object CommandExecutor {
    private val ctx: Context get() = App.instance

    fun capabilities(): List<String> = buildList {
        if (Spotify.connected) add("spotify")
        add("apps"); add("web"); add("alarm"); add("flashlight"); add("volume"); add("media"); add("battery"); add("speak"); add("notify"); if (YumeNotificationListener.active) add("reply")
        if (YumeAccessibilityService.active) add("screen")
        if (YumeNotificationListener.active) add("notifications")
        if (has(Manifest.permission.CAMERA)) add("camera")
        if (has(Manifest.permission.CALL_PHONE)) add("call")
        if (has(Manifest.permission.SEND_SMS)) add("sms")
        if (has(Manifest.permission.READ_CONTACTS)) add("contacts")
        if (has(Manifest.permission.ACCESS_FINE_LOCATION)) add("location")
    }

    private fun has(p: String) = ContextCompat.checkSelfPermission(ctx, p) == PackageManager.PERMISSION_GRANTED
    private fun ok(data: Any? = "ok") = JSONObject().put("ok", true).put("data", data)
    private fun fail(msg: String) = JSONObject().put("ok", false).put("error", msg)

    private fun startActivity(i: Intent) {
        i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        ctx.startActivity(i)
    }

    suspend fun execute(action: String, p: JSONObject): JSONObject {
        AgentLog.add("PC → $action ${p.toString().take(120)}")
        val res = try { run(action, p) } catch (e: SecurityException) {
            fail("Berechtigung fehlt: ${e.message}")
        } catch (e: Exception) { fail(e.message ?: e.javaClass.simpleName) }
        AgentLog.add(if (res.optBoolean("ok")) "✓ $action" else "✗ $action: ${res.optString("error")}")
        return res
    }

    private suspend fun run(action: String, p: JSONObject): JSONObject {
        if (!Prefs.allowControl) return fail("Die Handy-Steuerung ist in der App ausgeschaltet.")
        return when (action) {
            "open_app" -> { need(Prefs.allowApps, "Apps öffnen"); openApp(p.optString("app")) }
            "list_apps" -> { need(Prefs.allowApps, "Apps"); ok(listApps(p.optString("query")).joinToString(", ")) }
            "call" -> { need(Prefs.allowCalls, "Anrufe"); call(p.optString("number")) }
            "sms" -> { need(Prefs.allowSms, "SMS"); sms(p.optString("number"), p.optString("message")) }
            "open_url" -> { openUrl(p.optString("url")) }
            "web_search" -> { openUrl("https://www.google.com/search?q=" + Uri.encode(p.optString("query"))) }
            "set_alarm" -> setAlarm(p)
            "set_timer" -> setTimer(p)
            "alarm_set" -> {
                val at = YumeAlarms.nextTime(p.optInt("hour", 7), p.optInt("minute", 0), p.optString("day"))
                val a = YumeAlarms.add(at, p.optString("label"), p.optBoolean("daily"))
                ok("Yume-Wecker gestellt: " + YumeAlarms.describe(a))
            }
            "spotify_play" -> ok(Spotify.play(p.optString("query"), p.optString("kind", "track")))
            "spotify_control" -> ok(Spotify.control(p.optString("control")))
            "spotify_now" -> ok(Spotify.now())
            "spotify_volume" -> ok(Spotify.volume(p.optInt("level", 50)))
            "alarm_list" -> ok(YumeAlarms.all().joinToString(", ") { YumeAlarms.describe(it) }.ifEmpty { "Keine Wecker gestellt." })
            "alarm_cancel" -> {
                val id = p.optString("id")
                if (id.isEmpty()) ok("${YumeAlarms.cancelAll()} Wecker gelöscht")
                else if (YumeAlarms.cancel(id)) ok("Wecker gelöscht") else fail("Diesen Wecker gibt es nicht.")
            }
            "flashlight" -> flashlight(p.optBoolean("on", true))
            "volume" -> volume(p.optInt("level", 50))
            "media" -> media(p.optString("control"))
            "battery" -> battery()
            "location" -> { need(Prefs.allowLocation, "Standort"); location() }
            "notifications" -> { need(Prefs.allowNotifications, "Benachrichtigungen"); if (!YumeNotificationListener.active) fail("Benachrichtigungszugriff ist nicht aktiviert.") else ok(YumeNotificationListener.summary()) }
            "find_contact" -> { need(Prefs.allowContacts, "Kontakte"); findContact(p.optString("query")) }
            "birthdays" -> { need(Prefs.allowContacts, "Kontakte"); birthdays() }
            "calendar_today" -> calendarToday(p.optInt("days", 1).coerceIn(1, 60))
            "notify" -> notifyUser(p.optString("title", "Yume"), p.optString("text"))
            "reply_message" -> {
                need(Prefs.allowNotifications, "Nachrichten beantworten")
                if (!YumeNotificationListener.active) fail("Benachrichtigungszugriff ist nicht aktiviert.")
                else YumeNotificationListener.reply(p.optString("text")).let { if (it.startsWith("Geantwortet")) ok(it) else fail(it) }
            }
            "screen_read" -> { need(Prefs.allowScreen, "Bildschirm lesen"); screenRead() }
            "screen_look" -> { need(Prefs.allowScreen, "Bildschirm ansehen"); screenLook() }
            "tap" -> { need(Prefs.allowScreen, "Apps bedienen"); tap(p) }
            "type" -> { need(Prefs.allowScreen, "Apps bedienen"); typeText(p.optString("text")) }
            "scroll" -> { need(Prefs.allowScreen, "Apps bedienen"); a11y { it.scroll(p.optString("direction", "down")) }.also { delay(500) }.let { followUp("gescrollt") } }
            "back" -> { need(Prefs.allowScreen, "Apps bedienen"); global(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_BACK, "zurück") }
            "home" -> { need(Prefs.allowScreen, "Apps bedienen"); global(android.accessibilityservice.AccessibilityService.GLOBAL_ACTION_HOME, "Startbildschirm") }
            "camera_look" -> { need(Prefs.allowCamera, "Kamera"); cameraLook(p.optString("facing", "back")) }
            "speak" -> { PhoneTts.speak(p.optString("text")); ok() }
            else -> fail("Unbekannte Aktion: $action")
        }
    }

    private class Denied(msg: String) : Exception(msg)
    private fun need(allowed: Boolean, what: String) { if (!allowed) throw Denied("'$what' ist in den App-Einstellungen ausgeschaltet.") }

    // ------------------------------------------------------------------ apps
    private data class AppEntry(val label: String, val pkg: String)

    private fun apps(): List<AppEntry> {
        val pm = ctx.packageManager
        val intent = Intent(Intent.ACTION_MAIN).addCategory(Intent.CATEGORY_LAUNCHER)
        return pm.queryIntentActivities(intent, 0).map { AppEntry(it.loadLabel(pm).toString(), it.activityInfo.packageName) }
            .distinctBy { it.pkg }.sortedBy { it.label.lowercase() }
    }

    private fun listApps(q: String): List<String> =
        apps().filter { q.isBlank() || it.label.contains(q, true) }.map { it.label }.take(120)

    private fun norm(s: String) = s.lowercase().replace(Regex("[^a-z0-9äöüß]"), "")

    private fun openApp(name: String): JSONObject {
        if (name.isBlank()) return fail("Kein App-Name angegeben.")
        val all = apps()
        val n = norm(name)
        val hit = all.firstOrNull { norm(it.label) == n } ?: all.firstOrNull { norm(it.label).startsWith(n) }
            ?: all.firstOrNull { norm(it.label).contains(n) } ?: all.firstOrNull { n.contains(norm(it.label)) && norm(it.label).length > 3 }
            ?: all.minByOrNull { editDistance(norm(it.label), n) }?.takeIf { editDistance(norm(it.label), n) <= maxOf(2, n.length / 4) }
            ?: return fail("Keine App namens '$name' gefunden.")
        val launch = ctx.packageManager.getLaunchIntentForPackage(hit.pkg) ?: return fail("'${hit.label}' lässt sich nicht starten.")
        startActivity(launch)
        return ok("${hit.label} geöffnet")
    }

    private fun editDistance(a: String, b: String): Int {
        val dp = IntArray(b.length + 1) { it }
        for (i in 1..a.length) {
            var prev = dp[0]; dp[0] = i
            for (j in 1..b.length) {
                val tmp = dp[j]
                dp[j] = minOf(dp[j] + 1, dp[j - 1] + 1, prev + if (a[i - 1] == b[j - 1]) 0 else 1)
                prev = tmp
            }
        }
        return dp[b.length]
    }

    // ------------------------------------------------------------------ calls / sms / contacts
    private fun resolveNumber(target: String): Pair<String, String>? {
        val cleaned = target.replace(" ", "")
        if (cleaned.matches(Regex("[+0-9()\\-/]{3,}"))) return cleaned to cleaned
        if (!has(Manifest.permission.READ_CONTACTS) || !Prefs.allowContacts) return null
        val hits = contacts(target)
        return hits.firstOrNull()?.let { it.second to it.first }
    }

    private fun contacts(q: String): List<Pair<String, String>> {
        if (!has(Manifest.permission.READ_CONTACTS)) return emptyList()
        val out = ArrayList<Pair<String, String>>()
        ctx.contentResolver.query(ContactsContract.CommonDataKinds.Phone.CONTENT_URI,
            arrayOf(ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME, ContactsContract.CommonDataKinds.Phone.NUMBER),
            ContactsContract.CommonDataKinds.Phone.DISPLAY_NAME + " LIKE ?", arrayOf("%$q%"), null)?.use { c ->
            while (c.moveToNext() && out.size < 8) out += c.getString(0) to c.getString(1)
        }
        return out
    }

    private fun findContact(q: String): JSONObject {
        if (!has(Manifest.permission.READ_CONTACTS)) return fail("Kontakte-Berechtigung fehlt.")
        val hits = contacts(q)
        return if (hits.isEmpty()) fail("Kein Kontakt '$q' gefunden.") else ok(hits.joinToString("\n") { "${it.first}: ${it.second}" })
    }

    private suspend fun call(target: String): JSONObject {
        val (number, label) = resolveNumber(target) ?: return fail("Keine Nummer/kein Kontakt für '$target' gefunden.")
        if (Prefs.confirmRisky && !Confirm.ask("Yume möchte anrufen", "Anruf an $label ($number)?")) return fail("Vom Nutzer auf dem Handy abgelehnt.")
        val uri = Uri.parse("tel:" + Uri.encode(number))
        return if (has(Manifest.permission.CALL_PHONE)) { startActivity(Intent(Intent.ACTION_CALL, uri)); ok("Rufe $label an") }
        else { startActivity(Intent(Intent.ACTION_DIAL, uri)); ok("Wählhilfe für $label geöffnet (Anruf-Berechtigung fehlt, bitte selbst auf Anrufen tippen)") }
    }

    private suspend fun sms(target: String, text: String): JSONObject {
        if (text.isBlank()) return fail("Kein Nachrichtentext.")
        val (number, label) = resolveNumber(target) ?: return fail("Keine Nummer/kein Kontakt für '$target' gefunden.")
        if (!has(Manifest.permission.SEND_SMS)) {
            startActivity(Intent(Intent.ACTION_SENDTO, Uri.parse("smsto:" + Uri.encode(number))).putExtra("sms_body", text))
            return ok("SMS-App mit Entwurf geöffnet (Senden-Berechtigung fehlt)")
        }
        if (Prefs.confirmRisky && !Confirm.ask("Yume möchte eine SMS senden", "An $label: \"${text.take(120)}\"")) return fail("Vom Nutzer auf dem Handy abgelehnt.")
        val sm = ctx.getSystemService(SmsManager::class.java)
        sm.sendMultipartTextMessage(number, null, sm.divideMessage(text), null, null)
        return ok("SMS an $label gesendet")
    }

    // ------------------------------------------------------------------ web / alarm / system
    private fun openUrl(url: String): JSONObject {
        if (!url.startsWith("http://") && !url.startsWith("https://")) return fail("Nur http(s)-Adressen sind erlaubt.")
        startActivity(Intent(Intent.ACTION_VIEW, Uri.parse(url))); return ok("Geöffnet: $url")
    }

    private fun setAlarm(p: JSONObject): JSONObject {
        val i = Intent(AlarmClock.ACTION_SET_ALARM).putExtra(AlarmClock.EXTRA_HOUR, p.optInt("hour", 7))
            .putExtra(AlarmClock.EXTRA_MINUTES, p.optInt("minute", 0)).putExtra(AlarmClock.EXTRA_MESSAGE, p.optString("label", "Yume"))
            .putExtra(AlarmClock.EXTRA_SKIP_UI, true)
        startActivity(i); return ok("Wecker auf %02d:%02d gestellt".format(p.optInt("hour", 7), p.optInt("minute", 0)))
    }

    private fun setTimer(p: JSONObject): JSONObject {
        val s = p.optInt("seconds", 60)
        startActivity(Intent(AlarmClock.ACTION_SET_TIMER).putExtra(AlarmClock.EXTRA_LENGTH, s).putExtra(AlarmClock.EXTRA_MESSAGE, p.optString("label", "Yume")).putExtra(AlarmClock.EXTRA_SKIP_UI, true))
        return ok("Timer auf $s Sekunden gestellt")
    }

    private fun flashlight(on: Boolean): JSONObject {
        val cm = ctx.getSystemService(CameraManager::class.java)
        val id = cm.cameraIdList.firstOrNull { cm.getCameraCharacteristics(it).get(android.hardware.camera2.CameraCharacteristics.FLASH_INFO_AVAILABLE) == true }
            ?: return fail("Dieses Handy hat keine Taschenlampe.")
        cm.setTorchMode(id, on); return ok(if (on) "Taschenlampe an" else "Taschenlampe aus")
    }

    private fun volume(level: Int): JSONObject {
        val am = ctx.getSystemService(AudioManager::class.java)
        val max = am.getStreamMaxVolume(AudioManager.STREAM_MUSIC)
        am.setStreamVolume(AudioManager.STREAM_MUSIC, (max * level.coerceIn(0, 100) / 100f).toInt(), 0)
        return ok("Lautstärke $level %")
    }

    private fun media(control: String): JSONObject {
        val code = when (control) { "next" -> KeyEvent.KEYCODE_MEDIA_NEXT; "previous" -> KeyEvent.KEYCODE_MEDIA_PREVIOUS; else -> KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE }
        val am = ctx.getSystemService(AudioManager::class.java)
        am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, code)); am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, code))
        return ok("Medien: $control")
    }

    private fun battery(): JSONObject {
        val bm = ctx.getSystemService(BatteryManager::class.java)
        val i = ctx.registerReceiver(null, android.content.IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        val charging = (i?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) != 0
        return ok("Akku ${bm.getIntProperty(BatteryManager.BATTERY_PROPERTY_CAPACITY)} %" + if (charging) ", lädt" else "")
    }

    @Suppress("MissingPermission")
    private fun location(): JSONObject {
        if (!has(Manifest.permission.ACCESS_FINE_LOCATION)) return fail("Standort-Berechtigung fehlt.")
        val lm = ctx.getSystemService(LocationManager::class.java)
        val loc = lm.getProviders(true).mapNotNull { lm.getLastKnownLocation(it) }.maxByOrNull { it.time } ?: return fail("Kein Standort verfügbar.")
        var place = ""
        try {
            @Suppress("DEPRECATION")
            android.location.Geocoder(ctx).getFromLocation(loc.latitude, loc.longitude, 1)?.firstOrNull()?.let { place = it.getAddressLine(0) ?: "" }
        } catch (_: Exception) {}
        return ok("Position %.5f, %.5f (±%d m)%s".format(loc.latitude, loc.longitude, loc.accuracy.toInt(), if (place.isNotEmpty()) " – $place" else ""))
    }

    /** A reminder of the PC: a normal notification on the phone (tap = open the app). */
    private fun notifyUser(title: String, text: String): JSONObject {
        val open = PendingIntent.getActivity(ctx, 9, Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val n = NotificationCompat.Builder(ctx, "confirm").setSmallIcon(android.R.drawable.ic_popup_reminder).setContentTitle(title).setContentText(text)
            .setStyle(NotificationCompat.BigTextStyle().bigText(text)).setContentIntent(open).setAutoCancel(true).setPriority(NotificationCompat.PRIORITY_HIGH).build()
        ctx.getSystemService(NotificationManager::class.java).notify((System.currentTimeMillis() % 100000).toInt() + 100, n)
        return ok("ok")
    }

    /** "Name|MM-DD" or "Name|YYYY-MM-DD" per line: the birthdays stored in the contacts */
    private fun birthdays(): JSONObject {
        if (!has(Manifest.permission.READ_CONTACTS)) return fail("Kontakte-Berechtigung fehlt.")
        val out = ArrayList<String>()
        val sel = ContactsContract.Data.MIMETYPE + "=? AND " + ContactsContract.CommonDataKinds.Event.TYPE + "=" + ContactsContract.CommonDataKinds.Event.TYPE_BIRTHDAY
        ctx.contentResolver.query(ContactsContract.Data.CONTENT_URI,
            arrayOf(ContactsContract.Contacts.DISPLAY_NAME, ContactsContract.CommonDataKinds.Event.START_DATE), sel,
            arrayOf(ContactsContract.CommonDataKinds.Event.CONTENT_ITEM_TYPE), null)?.use { c ->
            while (c.moveToNext()) {
                val name = c.getString(0) ?: continue
                val date = c.getString(1) ?: continue
                out += "$name|" + date.removePrefix("--")
            }
        }
        return ok(out.joinToString("\n"))
    }

    private fun calendarToday(days: Int = 1): JSONObject {
        if (!has(Manifest.permission.READ_CALENDAR)) return fail("Kalender-Berechtigung fehlt.")
        val start = Calendar.getInstance().apply { set(Calendar.HOUR_OF_DAY, 0); set(Calendar.MINUTE, 0); set(Calendar.SECOND, 0) }.timeInMillis
        val end = start + days * 24L * 3600 * 1000
        val out = ArrayList<String>()
        val uri = CalendarContract.Instances.CONTENT_URI.buildUpon().also { android.content.ContentUris.appendId(it, start); android.content.ContentUris.appendId(it, end) }.build()
        ctx.contentResolver.query(uri, arrayOf(CalendarContract.Instances.TITLE, CalendarContract.Instances.BEGIN), null, null, CalendarContract.Instances.BEGIN + " ASC")?.use { c ->
            val f = java.text.SimpleDateFormat(if (days > 1) "EEE dd.MM. HH:mm" else "HH:mm", java.util.Locale.getDefault())
            while (c.moveToNext()) out += f.format(java.util.Date(c.getLong(1))) + " " + c.getString(0)
        }
        return ok(if (out.isEmpty()) "Heute keine Termine." else out.joinToString("\n"))
    }

    // ------------------------------------------------------------------ screen operation (accessibility)
    private inline fun <T> a11y(block: (YumeAccessibilityService) -> T): T {
        val s = YumeAccessibilityService.instance ?: throw Denied("Der Bedienungshilfen-Dienst von Yume ist nicht aktiviert (Einstellungen → Bedienungshilfen).")
        return block(s)
    }

    private suspend fun followUp(what: String): JSONObject {
        delay(700)
        val text = a11y { it.readScreen() }
        val res = ok("$what.\n$text")
        if (Prefs.autoScreenshot) attachScreenshot(res)
        return res
    }

    private suspend fun attachScreenshot(res: JSONObject) {
        val bmp = a11y { it.screenshot() } ?: return
        res.put("image_b64", encode(bmp))
    }

    private fun encode(bmp: Bitmap): String {
        val edge = Prefs.screenshotMaxEdge.coerceIn(480, 2400)
        val scale = minOf(1f, edge / maxOf(bmp.width, bmp.height).toFloat())
        val scaled = if (scale < 1f) Bitmap.createScaledBitmap(bmp, (bmp.width * scale).toInt(), (bmp.height * scale).toInt(), true) else bmp
        val bos = ByteArrayOutputStream()
        scaled.compress(Bitmap.CompressFormat.JPEG, Prefs.screenshotQuality.coerceIn(30, 95), bos)
        return Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP)
    }

    private fun screenRead(): JSONObject = ok(a11y { it.readScreen() })

    private suspend fun screenLook(): JSONObject {
        val res = ok(a11y { it.readScreen() })
        val bmp = a11y { it.screenshot() }
        if (bmp != null) res.put("image_b64", encode(bmp)) else res.put("data", res.optString("data") + "\n(Screenshot nicht möglich)")
        return res
    }

    private suspend fun tap(p: JSONObject): JSONObject {
        val text = p.optString("text")
        val done = when {
            text.isNotBlank() -> a11y { it.tapText(text) }
            p.has("x") && p.has("y") -> a11y { it.tapXY(p.getDouble("x").toFloat(), p.getDouble("y").toFloat()) }
            else -> return fail("tap braucht 'text' oder 'x' und 'y'.")
        }
        return if (done) followUp("getippt") else fail("Das Element '$text' wurde nicht gefunden – erst mit screen_read nachsehen.")
    }

    private suspend fun typeText(text: String): JSONObject {
        if (Prefs.confirmRisky && !Confirm.ask("Yume möchte Text eintippen", "\"${text.take(160)}\"")) return fail("Vom Nutzer auf dem Handy abgelehnt.")
        return if (a11y { it.typeText(text) }) followUp("Text eingegeben") else fail("Kein Eingabefeld gefunden – erst auf das Feld tippen.")
    }

    private suspend fun global(action: Int, what: String): JSONObject {
        val ok = a11y { it.performGlobalAction(action) }
        return if (ok) followUp(what) else fail("Aktion nicht möglich.")
    }

    // ------------------------------------------------------------------ camera
    private suspend fun cameraLook(facing: String): JSONObject {
        if (!has(Manifest.permission.CAMERA)) return fail("Kamera-Berechtigung fehlt.")
        val b64 = CameraCapture.capture(ctx, facing == "front") ?: return fail("Kamera nicht verfügbar (die App muss dafür kurz sichtbar sein – Handy entsperren oder 'Über anderen Apps einblenden' erlauben).")
        return ok("Foto aufgenommen").put("image_b64", b64)
    }
}

/** Asks the user on the phone itself before risky actions (call, SMS, typing text). */
object Confirm {
    private val pending = HashMap<Int, CompletableDeferred<Boolean>>()
    private var nextId = 100

    suspend fun ask(title: String, text: String): Boolean {
        val ctx = App.instance
        val id = synchronized(this) { nextId++ }
        val d = CompletableDeferred<Boolean>()
        pending[id] = d
        fun pi(allow: Boolean) = PendingIntent.getBroadcast(ctx, id * 2 + (if (allow) 1 else 0),
            Intent(ctx, ConfirmReceiver::class.java).putExtra("id", id).putExtra("allow", allow).setPackage(ctx.packageName),
            PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
        val open = PendingIntent.getActivity(ctx, id, Intent(ctx, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        val needPin = Prefs.pinHash.isNotEmpty()
        if (needPin && System.currentTimeMillis() < lockedUntil) { PhoneTts.speak("Zu viele falsche PIN-Eingaben. Bitte warte ein paar Minuten."); return false }
        // with a PIN the "Allow" button is a small text field in the notification ("PIN eingeben"), the answer goes through the same receiver
        val allowAction = if (needPin) {
            val ri = androidx.core.app.RemoteInput.Builder("pin").setLabel("PIN eingeben").build()
            val mutable = PendingIntent.getBroadcast(ctx, id * 2 + 1,
                Intent(ctx, ConfirmReceiver::class.java).putExtra("id", id).putExtra("allow", true).setPackage(ctx.packageName),
                PendingIntent.FLAG_MUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            NotificationCompat.Action.Builder(0, "Mit PIN erlauben", mutable).addRemoteInput(ri).build()
        } else NotificationCompat.Action.Builder(0, "Erlauben", pi(true)).build()
        val n = NotificationCompat.Builder(ctx, "confirm").setSmallIcon(android.R.drawable.ic_dialog_alert)
            .setContentTitle(title).setContentText(text).setStyle(NotificationCompat.BigTextStyle().bigText(text))
            .setPriority(NotificationCompat.PRIORITY_HIGH).setCategory(NotificationCompat.CATEGORY_CALL)
            .setFullScreenIntent(open, true).setAutoCancel(true)
            .addAction(allowAction).addAction(0, "Ablehnen", pi(false)).build()
        val nm = ctx.getSystemService(NotificationManager::class.java)
        nm.notify(id, n)
        PhoneTts.speak(if (needPin) "$title. $text. Zum Erlauben die PIN eingeben." else "$title. $text")
        val answer = withTimeoutOrNull(if (needPin) 90_000 else 45_000) { d.await() } ?: false
        nm.cancel(id)
        pending.remove(id)
        return answer
    }

    @Volatile private var failures = 0
    @Volatile private var lockedUntil = 0L

    /** [pin] = what was typed into the notification (null when no PIN is needed). A wrong PIN denies; three wrong ones lock for 5 minutes. */
    fun answer(id: Int, allow: Boolean, pin: String? = null) {
        if (allow && Prefs.pinHash.isNotEmpty()) {
            val ok = pin != null && Prefs.hashPin(pin.trim()) == Prefs.pinHash
            if (!ok) {
                failures++
                if (failures >= 3) { lockedUntil = System.currentTimeMillis() + 5 * 60_000; failures = 0 }
                PhoneTts.speak("Falsche PIN. Aktion abgelehnt.")
                pending[id]?.complete(false)
                return
            }
            failures = 0
        }
        pending[id]?.complete(allow)
    }
}

class ConfirmReceiver : BroadcastReceiver() {
    override fun onReceive(context: Context, intent: Intent) {
        val pin = androidx.core.app.RemoteInput.getResultsFromIntent(intent)?.getCharSequence("pin")?.toString()
        Confirm.answer(intent.getIntExtra("id", -1), intent.getBooleanExtra("allow", false), pin)
    }
}
