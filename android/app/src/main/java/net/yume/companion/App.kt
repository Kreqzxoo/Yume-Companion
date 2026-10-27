// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion

import android.app.Application
import android.app.NotificationChannel
import android.app.NotificationManager
import net.yume.companion.core.Lang
import net.yume.companion.core.Prefs
import net.yume.companion.core.tr

class App : Application() {
    override fun onCreate() {
        super.onCreate()
        instance = this
        Prefs.init(this)
        Lang.load()
        CrashLog.install(this)
        if (Prefs.offlineLoading.isNotEmpty()) {            // the app died while an offline model was being loaded: do not try it again
            net.yume.companion.offline.OfflineModels.markBroken(Prefs.offlineLoading)
            CrashLog.note(tr("Absturz beim Laden des Offline-Modells „${Prefs.offlineLoading}“ (vermutlich zu wenig Arbeitsspeicher).",
                "Crash while loading the offline model \"${Prefs.offlineLoading}\" (probably not enough memory)."))
            Prefs.sp.edit().putString("offline_loading", "").commit()
        }
        net.yume.companion.device.Spotify.init()
        net.yume.companion.device.Spotify.watchHost()
        net.yume.companion.ui.ToolStatusRepo.start()
        net.yume.companion.device.Automations.start()
        net.yume.companion.voice.WakeVoice.watch()
        val nm = getSystemService(NotificationManager::class.java)
        nm.createNotificationChannel(NotificationChannel("voice", tr("Zuhören & Anrufe", "Listening & calls"), NotificationManager.IMPORTANCE_LOW))
        nm.createNotificationChannel(NotificationChannel("link", tr("Verbindung zum PC", "Connection to the PC"), NotificationManager.IMPORTANCE_MIN))
        nm.createNotificationChannel(NotificationChannel("confirm", tr("Rückfragen von Yume", "Questions from Yume"), NotificationManager.IMPORTANCE_HIGH))
        nm.createNotificationChannel(NotificationChannel("info", tr("Hinweise", "Notices"), NotificationManager.IMPORTANCE_DEFAULT))
    }

    companion object {
        lateinit var instance: App
            private set
        /** true while the app's own window is in front (the assistant panel is only needed when it is not) */
        @Volatile var uiVisible = false
    }
}
