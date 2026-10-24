package net.yume.companion

import android.content.Context
import java.io.File
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Writes the stack trace of an app crash to a file (shown in the offline settings), so a crash can be found without a cable. */
object CrashLog {
    private var file: File? = null

    fun install(ctx: Context) {
        file = File(ctx.filesDir, "crash.txt")
        val old = Thread.getDefaultUncaughtExceptionHandler()
        Thread.setDefaultUncaughtExceptionHandler { t, e ->
            try { note("Thread ${t.name}: " + android.util.Log.getStackTraceString(e).take(3000)) } catch (_: Throwable) {}
            old?.uncaughtException(t, e)
        }
    }

    fun note(text: String) {
        try { file?.writeText(SimpleDateFormat("dd.MM. HH:mm:ss", Locale.GERMAN).format(Date()) + "\n" + text) } catch (_: Throwable) {}
    }

    fun last(): String = try { file?.takeIf { it.exists() }?.readText() ?: "" } catch (_: Throwable) { "" }
    fun clear() { try { file?.delete() } catch (_: Throwable) {} }
}
