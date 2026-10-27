// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.voice

import net.yume.companion.core.tr

import android.app.PendingIntent
import android.app.Service
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import android.media.ToneGenerator
import android.media.AudioManager
import android.os.BatteryManager
import android.os.IBinder
import android.os.PowerManager
import android.os.VibrationEffect
import android.os.Vibrator
import android.service.quicksettings.Tile
import android.service.quicksettings.TileService
import android.service.voice.VoiceInteractionService
import android.service.voice.VoiceInteractionSession
import android.service.voice.VoiceInteractionSessionService
import android.speech.RecognitionService
import android.speech.SpeechRecognizer
import androidx.core.app.NotificationCompat
import androidx.core.content.ContextCompat
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import net.yume.companion.MainActivity
import net.yume.companion.core.HostLink
import net.yume.companion.core.LinkService
import net.yume.companion.core.Prefs

object WakeState {
    /** the microphone test in the settings needs the microphone for a moment: the wake word listener steps aside */
    @Volatile var micBusy = false
    private val _status = MutableStateFlow("")
    val status = _status.asStateFlow()
    fun set(s: String) { _status.value = s }
}

/**
 * Foreground service with the microphone: either listens for the wake word (Vosk, offline, no account) or runs a call.
 * The wake word is only active while the user has switched it on (app switch, quick settings tile).
 */
class VoiceService : Service() {
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private var loop: Job? = null
    private var wakeLock: PowerManager.WakeLock? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(1, notification(tr("Yume ist bereit", "Yume is ready")), android.content.pm.ServiceInfo.FOREGROUND_SERVICE_TYPE_MICROPHONE)
        when (intent?.action) {
            ACTION_CALL -> CallEngine.request(intent.getBooleanExtra("oneshot", false), intent.getBooleanExtra("car", false), intent.getBooleanExtra("single", false))
            ACTION_HANGUP -> CallEngine.hangup()
            ACTION_WAKE_OFF -> Prefs.wakeEnabled = false
        }
        LinkService.ensure(this)
        ensureLoop()
        return START_STICKY
    }

    private fun notification(text: String) = NotificationCompat.Builder(this, "voice")
        .setSmallIcon(android.R.drawable.ic_btn_speak_now).setContentTitle("Yume").setContentText(text).setOngoing(true)
        .setContentIntent(PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE))
        .addAction(0, "Beenden", PendingIntent.getService(this, 2, Intent(this, VoiceService::class.java).setAction(ACTION_WAKE_OFF), PendingIntent.FLAG_IMMUTABLE))
        .build()

    private fun setNote(text: String) {
        getSystemService(android.app.NotificationManager::class.java).notify(1, notification(text))
    }

    private fun ensureLoop() {
        if (loop?.isActive == true) return
        loop = scope.launch {
            while (isActive) {
                if (CallEngine.wantCall) {
                    setNote(if (CarMode.active) tr("Auto-Modus – Gespräch läuft", "Car mode – conversation running") else tr("Gespräch läuft", "Conversation running"))
                    CallEngine.run(this@VoiceService)
                    setNote(tr("Yume ist bereit", "Yume is ready"))
                } else if (Prefs.wakeEnabled) {
                    if (WakeState.micBusy) { delay(300); continue }
                    if (!allowedNow()) { WakeState.set(tr("Pausiert (nur beim Laden aktiv)", "Paused (only active while charging)")); delay(5000); continue }
                    wakeLoop()
                } else break
            }
            WakeState.set("")
            stopSelf()
        }
    }

    private fun allowedNow(): Boolean {
        if (!Prefs.wakeOnlyCharging) return true
        val i = registerReceiver(null, IntentFilter(Intent.ACTION_BATTERY_CHANGED))
        return (i?.getIntExtra(BatteryManager.EXTRA_PLUGGED, 0) ?: 0) != 0
    }

    private suspend fun wakeLoop() {
        val rate = 16000
        val rec = SpeakerLock.newRecognizer(Prefs.wakeLanguage())
        if (rec == null) {
            WakeState.set(tr("Sprachmodell (${Prefs.wakeLanguage()}) fehlt – in den Einstellungen laden", "Speech model (${Prefs.wakeLanguage()}) missing – download it in the settings"))
            Prefs.wakeEnabled = false
            return
        }
        val minBuf = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
        val ar = try {
            AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, 16384))
        } catch (e: SecurityException) { WakeState.set(tr("Mikrofon-Berechtigung fehlt", "Microphone permission missing")); Prefs.wakeEnabled = false; rec.close(); return }
        if (ar.state != AudioRecord.STATE_INITIALIZED) { WakeState.set(tr("Mikrofon belegt", "Microphone in use")); ar.release(); rec.close(); delay(3000); return }
        val pm = getSystemService(PowerManager::class.java)
        wakeLock = pm.newWakeLock(PowerManager.PARTIAL_WAKE_LOCK, "yume:wake").also { it.acquire(12 * 3600 * 1000L) }
        WakeState.set(tr("Lausche auf „${Prefs.wakeWordList().firstOrNull() ?: "Yume"}“", "Listening for “${Prefs.wakeWordList().firstOrNull() ?: "Yume"}”"))
        setNote(tr("Wake Word aktiv", "Wake word active"))
        val buf = ShortArray(1600)
        val words = Prefs.wakeWordList()
        var lastPartial = ""
        val lock = SpeakerLock.active()                  // "only my voice": a match counts after the sentence is over and the voice fits
        val myVoice = SpeakerLock.enrolled()
        var pending = false
        ar.startRecording()
        try {
            while (currentCoroutineContext().isActive && Prefs.wakeEnabled && !CallEngine.wantCall && allowedNow() && !WakeState.micBusy) {
                val n = ar.read(buf, 0, buf.size)
                if (n <= 0) { delay(20); continue }
                val done = rec.acceptWaveForm(buf, n)
                val json = if (done) rec.result else rec.partialResult
                val heard = VoskStore.text(json)
                if (heard.isNotBlank() && (heard != lastPartial || (done && lock))) {
                    lastPartial = heard
                    if (WakeMatch.matches(heard, words, Prefs.wakeSensitivity)) {
                        if (!lock) {
                            rec.reset(); lastPartial = ""
                            onWake()
                            break
                        }
                        pending = true
                    }
                }
                if (done) {
                    if (lock && pending) {
                        pending = false
                        val print = SpeakerLock.vectorOf(json)
                        val dist = if (print != null && myVoice != null) SpeakerLock.score(print) else 9.0
                        if (dist <= SpeakerLock.threshold()) {
                            if (print != null && dist <= SpeakerLock.threshold() * 0.8) SpeakerLock.learn(print)     // clearly me: the profile gets a bit better
                            rec.reset(); lastPartial = ""; onWake(); break
                        }
                        WakeState.set(tr("Wake Word von einer anderen Stimme ignoriert", "Wake word from another voice ignored"))
                    }
                    lastPartial = ""
                }
            }
        } finally {
            try { ar.stop() } catch (_: Exception) {}
            ar.release(); rec.close()
            wakeLock?.let { if (it.isHeld) it.release() }
        }
    }

    private suspend fun onWake() {
        if (Prefs.wakeBeep && !Prefs.wakeReplyOn) try { ToneGenerator(AudioManager.STREAM_MUSIC, 80).startTone(ToneGenerator.TONE_PROP_ACK, 150) } catch (_: Exception) {}
        if (Prefs.wakeVibrate) try { getSystemService(Vibrator::class.java).vibrate(VibrationEffect.createOneShot(80, VibrationEffect.DEFAULT_AMPLITUDE)) } catch (_: Exception) {}
        val panel = AssistOverlay.available || AssistOverlay.isShown
        if (panel) AssistOverlay.show(this)
        // her greeting plays first, on its own and in full quality (an open call microphone would switch many phones to telephone sound)
        try { WakeVoice.speak() } catch (_: Exception) {}
        CallEngine.request(oneShot = true, single = panel)
    }

    override fun onDestroy() {
        scope.cancel()
        wakeLock?.let { if (it.isHeld) it.release() }
        super.onDestroy()
    }

    companion object {
        const val ACTION_CALL = "net.yume.companion.CALL"
        const val ACTION_HANGUP = "net.yume.companion.HANGUP"
        const val ACTION_WAKE_OFF = "net.yume.companion.WAKE_OFF"
        const val ACTION_WAKE_ON = "net.yume.companion.WAKE_ON"

        private fun start(ctx: Context, i: Intent) = ContextCompat.startForegroundService(ctx, i)

        fun setWake(ctx: Context, on: Boolean) {
            Prefs.wakeEnabled = on
            if (on) start(ctx, Intent(ctx, VoiceService::class.java).setAction(ACTION_WAKE_ON))
            else WakeState.set("")
        }

        fun startCall(ctx: Context, oneShot: Boolean = false, car: Boolean = false, single: Boolean = false) =
            start(ctx, Intent(ctx, VoiceService::class.java).setAction(ACTION_CALL).putExtra("oneshot", oneShot).putExtra("car", car).putExtra("single", single))

        fun hangup(ctx: Context) { CallEngine.hangup() }
    }
}

/** Quick settings tile: wake word on / off with one swipe. */
class WakeTileService : TileService() {
    override fun onStartListening() = refresh()
    override fun onClick() {
        val on = !Prefs.wakeEnabled
        try { VoiceService.setWake(this, on) } catch (e: Exception) {
            startActivityAndCollapse(PendingIntent.getActivity(this, 3, Intent(this, MainActivity::class.java).putExtra("start_wake", true), PendingIntent.FLAG_IMMUTABLE))
        }
        refresh()
    }
    private fun refresh() {
        qsTile?.apply { state = if (Prefs.wakeEnabled) Tile.STATE_ACTIVE else Tile.STATE_INACTIVE; label = tr("Yume zuhören", "Listen to Yume"); updateTile() }
    }
}

/** Bluetooth car connected -> car mode (hands-free call). Android only allows the microphone to start from a visible app, so otherwise a notification asks. */
class CarReceiver : BroadcastReceiver() {
    override fun onReceive(ctx: Context, intent: Intent) {
        Prefs.init(ctx)
        if (!Prefs.paired || !Prefs.carAutoStart) return
        val dev: android.bluetooth.BluetoothDevice? = intent.getParcelableExtra(android.bluetooth.BluetoothDevice.EXTRA_DEVICE)
        val name = try { dev?.name ?: "" } catch (_: SecurityException) { "" }
        val names = Prefs.carBtNames.split(',').map { it.trim().lowercase() }.filter { it.isNotEmpty() }
        if (names.isEmpty() || names.none { name.lowercase().contains(it) }) return
        if (intent.action == android.bluetooth.BluetoothDevice.ACTION_ACL_DISCONNECTED) { if (CarMode.active) CallEngine.hangup(); return }
        try { VoiceService.startCall(ctx, car = true) } catch (_: Exception) {
            val open = PendingIntent.getActivity(ctx, 5, Intent(ctx, MainActivity::class.java).putExtra("start_car", true), PendingIntent.FLAG_IMMUTABLE or PendingIntent.FLAG_UPDATE_CURRENT)
            ctx.getSystemService(android.app.NotificationManager::class.java).notify(8,
                NotificationCompat.Builder(ctx, "confirm").setSmallIcon(android.R.drawable.ic_menu_directions).setContentTitle(tr("Auto verbunden", "Car connected"))
                    .setContentText(tr("Tippen, um den Yume Auto-Modus zu starten", "Tap to start Yume car mode")).setContentIntent(open).setFullScreenIntent(open, true).setAutoCancel(true).build())
        }
    }
}

// ---------------------------------------------------------------- Google-Assistant replacement
class YumeVoiceInteractionService : VoiceInteractionService()

class YumeSessionService : VoiceInteractionSessionService() {
    override fun onNewSession(args: android.os.Bundle?): VoiceInteractionSession = YumeSession(this)
}

class YumeSession(private val ctx: Context) : VoiceInteractionSession(ctx) {
    override fun onShow(args: android.os.Bundle?, showFlags: Int) {
        super.onShow(args, showFlags)
        ctx.startActivity(Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP).putExtra("start_call", true).putExtra("oneshot", true))
        hide()
    }
}

/** Required by Android for an assistant app; Yume uses its own speech pipeline. */
class YumeRecognitionService : RecognitionService() {
    override fun onStartListening(recognizerIntent: Intent?, listener: Callback?) { listener?.error(SpeechRecognizer.ERROR_CLIENT) }
    override fun onCancel(listener: Callback?) {}
    override fun onStopListening(listener: Callback?) {}
}
