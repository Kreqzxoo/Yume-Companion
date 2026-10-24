package net.yume.companion

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import net.yume.companion.core.Prefs

class App : Application() {
    override fun onCreate() {
        super.onCreate()
        instance = this
        Prefs.init(this)
        CrashLog.install(this)
        if (Prefs.offlineLoading.isNotEmpty()) {            // the app died while an offline model was being loaded: do not try it again
            net.yume.companion.offline.OfflineModels.markBroken(Prefs.offlineLoading)
            CrashLog.note("Absturz beim Laden des Offline-Modells „${Prefs.offlineLoading}“ (vermutlich zu wenig Arbeitsspeicher).")
            Prefs.sp.edit().putString("offline_loading", "").commit()
        }
        net.yume.companion.device.Spotify.init()
        net.yume.companion.device.Spotify.watchHost()
        net.yume.companion.ui.ToolStatusRepo.start()
        net.yume.companion.device.Automations.start()
        net.yume.companion.voice.WakeVoice.watch()
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("voice", "Zuhören & Anrufe", NotificationManager.IMPORTANCE_LOW))
        nm.createNotificationChannel(NotificationChannel("link", "Verbindung zum PC", NotificationManager.IMPORTANCE_MIN))
        nm.createNotificationChannel(NotificationChannel("confirm", "Rückfragen von Yume", NotificationManager.IMPORTANCE_HIGH))
        nm.createNotificationChannel(NotificationChannel("info", "Hinweise", NotificationManager.IMPORTANCE_DEFAULT))
    }

    companion object {
        lateinit var instance: App
            private set
        /** true while the app's own window is in front (the assistant panel is only needed when it is not) */
        @Volatile var uiVisible = false
    }
}
