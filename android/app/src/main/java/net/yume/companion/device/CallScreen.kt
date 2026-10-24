package net.yume.companion.device

import android.app.NotificationManager
import android.app.PendingIntent
import android.content.Intent
import android.net.Uri
import android.provider.ContactsContract
import android.telecom.Call
import android.telecom.CallScreeningService
import androidx.core.app.NotificationCompat
import net.yume.companion.App
import net.yume.companion.MainActivity
import net.yume.companion.core.Prefs
import net.yume.companion.core.Quiet
import net.yume.companion.voice.PhoneTts

enum class CallDecision { ALLOW, REJECT, SILENCE }

/** What to do with an incoming call - plain function, so it can be tested without a phone. */
object CallRules {
    fun prefixes(csv: String): List<String> = csv.split(',', ';', ' ').map { it.trim().replace(" ", "") }.filter { it.isNotEmpty() }

    /** [number] as the network delivers it (+49..., 0900...). Known contacts are always let through. */
    fun decide(number: String, known: Boolean, blockPrefixes: List<String>, silenceUnknownAtNight: Boolean, quietNow: Boolean): CallDecision {
        if (known) return CallDecision.ALLOW
        val n = number.replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        val national = if (n.startsWith("+49")) "0" + n.substring(3) else if (n.startsWith("0049")) "0" + n.substring(4) else n
        if (blockPrefixes.any { national.startsWith(it) || n.startsWith(it) }) return CallDecision.REJECT
        if (silenceUnknownAtNight && quietNow) return CallDecision.SILENCE
        return CallDecision.ALLOW
    }

    /** "+4930123456" -> "plus vier neun drei null ..." is hard to listen to: read the number in small groups */
    fun speakable(number: String): String {
        val digits = number.filter { it.isDigit() || it == '+' }.replace("+", "plus ")
        return digits.chunked(3).joinToString(" ")
    }
}

/**
 * Call protection: the app is asked by Android about every incoming call (when set as the "caller ID & spam app" in the settings).
 * Known contacts: let through, the name is announced (hands-free). Unknown numbers: blocked by prefix (e.g. 0900), or silenced at night, or announced.
 * An answer by voice is not possible for normal apps - Yume blocks, silences and tells you.
 */
class YumeCallScreen : CallScreeningService() {
    override fun onScreenCall(details: Call.Details) {
        val incoming = details.callDirection == Call.Details.DIRECTION_INCOMING
        val number = details.handle?.schemeSpecificPart.orEmpty()
        if (!incoming || !Prefs.callScreenOn) { respondToCall(details, CallResponse.Builder().build()); return }
        val name = contactName(number)
        val decision = CallRules.decide(number, name != null, CallRules.prefixes(Prefs.callBlockPrefixes), Prefs.callSilenceNight, Quiet.active())
        val resp = CallResponse.Builder()
        when (decision) {
            CallDecision.REJECT -> { resp.setDisallowCall(true).setRejectCall(true).setSkipNotification(true); note("Anruf blockiert", number) }
            CallDecision.SILENCE -> { resp.setSilenceCall(true); note("Unbekannter Anruf (lautlos, Ruhemodus)", number) }
            CallDecision.ALLOW -> if (Prefs.callAnnounce) PhoneTts.speak(if (name != null) "Anruf von $name" else "Unbekannter Anruf von " + CallRules.speakable(number).ifEmpty { "unbekannter Nummer" })
        }
        respondToCall(details, resp.build())
    }

    private fun contactName(number: String): String? {
        if (number.isEmpty() || androidx.core.content.ContextCompat.checkSelfPermission(this, android.Manifest.permission.READ_CONTACTS) != android.content.pm.PackageManager.PERMISSION_GRANTED) return null
        return try {
            contentResolver.query(Uri.withAppendedPath(ContactsContract.PhoneLookup.CONTENT_FILTER_URI, Uri.encode(number)), arrayOf(ContactsContract.PhoneLookup.DISPLAY_NAME), null, null, null)
                ?.use { c -> if (c.moveToFirst()) c.getString(0) else null }
        } catch (_: Exception) { null }
    }

    private fun note(title: String, number: String) {
        val open = PendingIntent.getActivity(this, 11, Intent(this, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK), PendingIntent.FLAG_IMMUTABLE)
        val n = NotificationCompat.Builder(this, "info").setSmallIcon(android.R.drawable.ic_menu_call).setContentTitle(title).setContentText(number.ifEmpty { "ohne Nummer" })
            .setContentIntent(open).setAutoCancel(true).build()
        getSystemService(NotificationManager::class.java).notify((System.currentTimeMillis() % 100000).toInt() + 300, n)
    }
}
