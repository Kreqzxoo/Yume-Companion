package net.yume.companion.core

import java.util.Calendar

/** Quiet mode at night: softer voice (volume factor) and the PC is told to answer calmly and short. Time window and volume are in the settings. */
object Quiet {
    private fun minutes(s: String, fallback: Int): Int {
        val p = s.trim().split(":")
        val h = p.getOrNull(0)?.toIntOrNull() ?: return fallback
        val m = p.getOrNull(1)?.toIntOrNull() ?: 0
        return (h.coerceIn(0, 23) * 60 + m.coerceIn(0, 59))
    }

    fun active(): Boolean = Prefs.quietOn && inWindow()

    /** inside the night time window (22:00 - 07:00 by default), whether quiet mode is switched on or not */
    fun inWindow(): Boolean {
        val now = Calendar.getInstance().let { it.get(Calendar.HOUR_OF_DAY) * 60 + it.get(Calendar.MINUTE) }
        val from = minutes(Prefs.quietFrom, 22 * 60)
        val to = minutes(Prefs.quietTo, 7 * 60)
        return if (from <= to) now in from until to else (now >= from || now < to)      // 22:00 - 07:00 crosses midnight
    }

    /** 1.0 normally, e.g. 0.5 in the quiet hours */
    fun factor(): Float = if (active()) (Prefs.quietVolume / 100f).coerceIn(0.05f, 1f) else 1f
}
