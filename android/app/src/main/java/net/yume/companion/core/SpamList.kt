// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.core

import android.content.Context
import net.yume.companion.device.CallRules
import okhttp3.Request
import java.io.File

/**
 * Spam list for the call protection. One list for everybody, kept in the project repository (android/spamlist.txt) and downloaded
 * from there; a copy ships with the app (assets/spamlist.txt), so it works offline from the first start.
 * Format (plain text, one entry per line): "format: 1", "version: 2026-11-04", "prefix: 0900", "number: +4930123456", "# comment".
 * Your own prefixes in the settings are added on top of this list.
 */
object SpamList {
    const val URL = "https://raw.githubusercontent.com/Kreqzxoo/Yume-Companion/main/android/spamlist.txt"
    private const val MAX_BYTES = 256 * 1024L
    private const val MAX_ENTRIES = 5000
    private const val REFRESH_EVERY_MS = 3L * 24 * 3600 * 1000

    data class Data(val version: String, val prefixes: List<String>, val numbers: Set<String>) {
        val size get() = prefixes.size + numbers.size
    }

    private val valid = Regex("""[+0-9]{3,20}""")

    /** null = the text is not a valid list (wrong format, bad entry, too long) and must not be used */
    fun parse(text: String): Data? {
        var format = ""
        var version = ""
        val prefixes = LinkedHashSet<String>()
        val numbers = LinkedHashSet<String>()
        var count = 0
        for (raw in text.lineSequence()) {
            val line = raw.trim()
            if (line.isEmpty() || line.startsWith("#")) continue
            if (++count > MAX_ENTRIES + 4) return null
            val i = line.indexOf(':')
            if (i <= 0) return null
            val key = line.substring(0, i).trim().lowercase()
            val value = line.substring(i + 1).trim().replace(" ", "").replace("-", "")
            when (key) {
                "format" -> format = value
                "version" -> version = value
                "prefix" -> { if (!valid.matches(value)) return null; prefixes += CallRules.national(value) }
                "number" -> { if (!valid.matches(value)) return null; numbers += CallRules.national(value) }
                else -> return null
            }
        }
        if (format != "1" || version.isEmpty()) return null
        return Data(version, prefixes.toList(), numbers)
    }

    private val empty = Data("", emptyList(), emptySet())
    @Volatile private var cache: Data? = null

    private fun file(ctx: Context) = File(ctx.filesDir, "spamlist.txt")

    /** the downloaded list if there is a valid one, otherwise the list shipped with the app */
    fun current(ctx: Context): Data {
        cache?.let { return it }
        val loaded = try { file(ctx).takeIf { it.isFile }?.readText()?.let { parse(it) } } catch (_: Exception) { null }
            ?: try { ctx.assets.open("spamlist.txt").bufferedReader().use { parse(it.readText()) } } catch (_: Exception) { null }
            ?: empty
        cache = loaded
        return loaded
    }

    enum class Result { UPDATED, UP_TO_DATE, FAILED }

    /** Downloads the list (blocking - call from a background thread). A broken or older download is ignored. */
    fun refresh(ctx: Context): Result {
        Prefs.spamListChecked = System.currentTimeMillis()
        return try {
            val client = Host.http.newBuilder().connectTimeout(8, java.util.concurrent.TimeUnit.SECONDS).readTimeout(15, java.util.concurrent.TimeUnit.SECONDS).build()
            client.newCall(Request.Builder().url(URL).header("Cache-Control", "no-cache").build()).execute().use { r ->
                if (!r.isSuccessful || r.request.url.scheme != "https" || r.request.url.host != "raw.githubusercontent.com") return Result.FAILED
                val src = r.body?.source() ?: return Result.FAILED
                if (src.request(MAX_BYTES + 1)) return Result.FAILED          // longer than allowed
                val text = src.readUtf8()
                val fresh = parse(text) ?: return Result.FAILED
                val now = current(ctx)
                if (fresh.version < now.version || (fresh.version == now.version && fresh.size == now.size)) return Result.UP_TO_DATE
                val tmp = File(ctx.filesDir, "spamlist.tmp")
                tmp.writeText(text)
                if (!tmp.renameTo(file(ctx))) { file(ctx).delete(); tmp.renameTo(file(ctx)) }
                cache = fresh
                Result.UPDATED
            }
        } catch (_: Exception) { Result.FAILED }
    }

    /** background refresh when the last check is older than three days */
    fun refreshIfDue(ctx: Context) {
        if (!Prefs.spamListOn || System.currentTimeMillis() - Prefs.spamListChecked < REFRESH_EVERY_MS) return
        Prefs.spamListChecked = System.currentTimeMillis()            // also stops a second start while this one runs
        Thread({ refresh(ctx.applicationContext) }, "spamlist").start()
    }
}
