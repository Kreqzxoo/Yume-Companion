// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.core

import android.content.Context
import android.content.Intent
import net.yume.companion.device.YumeAlarms
import net.yume.companion.voice.CallEngine
import net.yume.companion.voice.VoiceService
import java.io.File

/** "Connect to a new PC" and "Reset the app". */
object AppReset {
    private fun stopEverything(ctx: Context) {
        try { CallEngine.hangup() } catch (_: Exception) {}
        try { VoiceService.setWake(ctx, false) } catch (_: Exception) {}
        try { HostLink.stop() } catch (_: Exception) {}
        try { ctx.stopService(Intent(ctx, LinkService::class.java)) } catch (_: Exception) {}
    }

    /** The pairing and everything that belongs to this PC (addresses, MAC, character, her downloaded wake voice) goes; your own settings stay. */
    fun forNewHost(ctx: Context) {
        stopEverything(ctx)
        Host.unpair()
        Prefs.localUrl = ""; Prefs.externalUrl = ""; Prefs.lastUrl = ""; Prefs.hostName = ""; Prefs.macs = ""; Prefs.character = ""
        try { File(ctx.filesDir, "wake_voice").deleteRecursively() } catch (_: Exception) {}
    }

    /**
     * Back to the state of a fresh install: pairing, all settings, alarms, Spotify login, cached chats. Big downloads (3D models, speech models,
     * offline AI) stay unless [deleteModels]. The app restarts afterwards.
     */
    fun everything(ctx: Context, deleteModels: Boolean) {
        stopEverything(ctx)
        try { YumeAlarms.cancelAll() } catch (_: Exception) {}
        try { Host.unpair() } catch (_: Exception) {}
        Prefs.sp.edit().clear().commit()
        val keep = setOf("vrm", "vrm_anim", "vosk", "llm")
        ctx.filesDir.listFiles()?.forEach { f -> if (deleteModels || f.name !in keep) f.deleteRecursively() }
        try { ctx.cacheDir.listFiles()?.forEach { it.deleteRecursively() } } catch (_: Exception) {}
        val launch = ctx.packageManager.getLaunchIntentForPackage(ctx.packageName)
        if (launch != null) ctx.startActivity(launch.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_CLEAR_TASK))
        Runtime.getRuntime().exit(0)           // fresh process: every in-memory setting is gone, too
    }
}
