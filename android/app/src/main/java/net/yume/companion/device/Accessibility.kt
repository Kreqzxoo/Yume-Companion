package net.yume.companion.device

import net.yume.companion.core.tr

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Bitmap
import android.graphics.Path
import android.graphics.Rect
import android.os.Bundle
import android.service.notification.NotificationListenerService
import android.service.notification.StatusBarNotification
import android.view.accessibility.AccessibilityEvent
import android.view.accessibility.AccessibilityNodeInfo
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.withTimeoutOrNull
import net.yume.companion.App
import net.yume.companion.core.Prefs
import net.yume.companion.voice.CarMode
import net.yume.companion.voice.PhoneTts
import java.util.concurrent.Executors

/** Lets Yume read the screen and operate other apps (tap, type, scroll, back, home, screenshot). */
class YumeAccessibilityService : AccessibilityService() {
    override fun onServiceConnected() { instance = this }
    override fun onAccessibilityEvent(event: AccessibilityEvent?) {}
    override fun onInterrupt() {}
    override fun onUnbind(intent: android.content.Intent?): Boolean { if (instance === this) instance = null; return super.onUnbind(intent) }
    override fun onDestroy() { if (instance === this) instance = null; super.onDestroy() }

    private class Item(val text: String, val bounds: Rect, val clickable: Boolean, val editable: Boolean)

    private fun collect(node: AccessibilityNodeInfo?, out: MutableList<Item>, depth: Int = 0) {
        if (node == null || depth > 40 || out.size > 400) return
        if (node.isVisibleToUser) {
            val label = listOfNotNull(node.text?.toString(), node.contentDescription?.toString(), node.hintText?.toString())
                .firstOrNull { it.isNotBlank() }
            val r = Rect(); node.getBoundsInScreen(r)
            if ((label != null || node.isClickable || node.isEditable) && r.width() > 0 && r.height() > 0) {
                out += Item((label ?: node.viewIdResourceName?.substringAfterLast('/') ?: node.className?.toString()?.substringAfterLast('.') ?: "").take(160),
                    r, node.isClickable || node.isLongClickable, node.isEditable)
            }
        }
        for (i in 0 until node.childCount) collect(node.getChild(i), out, depth + 1)
    }

    fun readScreen(): String {
        val root = rootInActiveWindow ?: return tr("(Kein Bildschirminhalt lesbar – eventuell gesperrt oder geschützt)", "(No screen content readable – possibly locked or protected)")
        val items = ArrayList<Item>()
        collect(root, items)
        val sb = StringBuilder("App: ${root.packageName}\n")
        items.forEachIndexed { i, it ->
            sb.append(i + 1).append(". ").append(if (it.editable) tr("[Eingabe] ", "[input] ") else if (it.clickable) tr("[Button] ", "[button] ") else "").append(it.text)
                .append("  @(").append(it.bounds.centerX()).append(',').append(it.bounds.centerY()).append(")\n")
        }
        return sb.toString().take(12000)
    }

    private fun findByText(root: AccessibilityNodeInfo?, text: String): AccessibilityNodeInfo? {
        root ?: return null
        val exact = root.findAccessibilityNodeInfosByText(text)
        if (exact.isNullOrEmpty()) return null
        val needle = text.lowercase()
        return exact.firstOrNull { (it.text?.toString() ?: it.contentDescription?.toString() ?: "").lowercase() == needle && it.isVisibleToUser }
            ?: exact.firstOrNull { it.isVisibleToUser } ?: exact.first()
    }

    fun tapText(text: String): Boolean {
        var node = findByText(rootInActiveWindow, text) ?: return false
        var hops = 0
        while (!node.isClickable && hops < 6) { node = node.parent ?: break; hops++ }
        if (node.isClickable && node.performAction(AccessibilityNodeInfo.ACTION_CLICK)) return true
        val r = Rect(); node.getBoundsInScreen(r)
        return tapXY(r.centerX().toFloat(), r.centerY().toFloat())
    }

    fun tapXY(x: Float, y: Float): Boolean {
        val p = Path().apply { moveTo(x, y) }
        return dispatch(GestureDescription.StrokeDescription(p, 0, 60))
    }

    fun swipe(x1: Float, y1: Float, x2: Float, y2: Float, ms: Long = 350): Boolean {
        val p = Path().apply { moveTo(x1, y1); lineTo(x2, y2) }
        return dispatch(GestureDescription.StrokeDescription(p, 0, ms))
    }

    private fun dispatch(stroke: GestureDescription.StrokeDescription): Boolean {
        val done = java.util.concurrent.CountDownLatch(1)
        var ok = false
        val accepted = dispatchGesture(GestureDescription.Builder().addStroke(stroke).build(), object : GestureResultCallback() {
            override fun onCompleted(g: GestureDescription?) { ok = true; done.countDown() }
            override fun onCancelled(g: GestureDescription?) { done.countDown() }
        }, null)
        if (!accepted) return false
        done.await(3, java.util.concurrent.TimeUnit.SECONDS)
        return ok
    }

    fun typeText(text: String, append: Boolean = false): Boolean {
        val root = rootInActiveWindow ?: return false
        val target = root.findFocus(AccessibilityNodeInfo.FOCUS_INPUT) ?: firstEditable(root) ?: return false
        val base = if (append) (target.text?.toString() ?: "") else ""
        val args = Bundle().apply { putCharSequence(AccessibilityNodeInfo.ACTION_ARGUMENT_SET_TEXT_CHARSEQUENCE, base + text) }
        return target.performAction(AccessibilityNodeInfo.ACTION_SET_TEXT, args)
    }

    private fun firstEditable(n: AccessibilityNodeInfo?): AccessibilityNodeInfo? {
        n ?: return null
        if (n.isEditable && n.isVisibleToUser) return n
        for (i in 0 until n.childCount) firstEditable(n.getChild(i))?.let { return it }
        return null
    }

    fun scroll(direction: String): Boolean {
        val dm = resources.displayMetrics
        val w = dm.widthPixels.toFloat(); val h = dm.heightPixels.toFloat()
        return when (direction) {
            "down" -> swipe(w / 2, h * 0.72f, w / 2, h * 0.28f)      // content moves up = scroll down
            "up" -> swipe(w / 2, h * 0.28f, w / 2, h * 0.72f)
            "left" -> swipe(w * 0.2f, h / 2, w * 0.8f, h / 2)
            "right" -> swipe(w * 0.8f, h / 2, w * 0.2f, h / 2)
            else -> false
        }
    }

    suspend fun screenshot(): Bitmap? {
        val result = CompletableDeferred<Bitmap?>()
        val exec = Executors.newSingleThreadExecutor()
        try {
            takeScreenshot(android.view.Display.DEFAULT_DISPLAY, exec, object : TakeScreenshotCallback {
                override fun onSuccess(shot: ScreenshotResult) {
                    val hw = Bitmap.wrapHardwareBuffer(shot.hardwareBuffer, shot.colorSpace)
                    val soft = hw?.copy(Bitmap.Config.ARGB_8888, false)
                    shot.hardwareBuffer.close()
                    result.complete(soft)
                }
                override fun onFailure(errorCode: Int) { result.complete(null) }
            })
        } catch (_: Exception) { result.complete(null) }
        val bmp = withTimeoutOrNull(5000) { result.await() }
        exec.shutdown()
        return bmp
    }

    companion object {
        @Volatile var instance: YumeAccessibilityService? = null
        val active: Boolean get() = instance != null
    }
}

/** Remembers the latest notifications so Yume can read them out on request (or in car mode). */
class YumeNotificationListener : NotificationListenerService() {
    override fun onListenerConnected() { instance = this }
    override fun onListenerDisconnected() { if (instance === this) instance = null }

    override fun onNotificationPosted(sbn: StatusBarNotification) {
        if (sbn.packageName == packageName || sbn.isOngoing) return
        val e = sbn.notification.extras
        val title = e.getCharSequence("android.title")?.toString() ?: ""
        val text = e.getCharSequence("android.text")?.toString() ?: ""
        if (title.isEmpty() && text.isEmpty()) return
        val app = try { packageManager.getApplicationLabel(packageManager.getApplicationInfo(sbn.packageName, 0)).toString() } catch (_: Exception) { sbn.packageName }
        // messengers offer a "reply" action with a text field (RemoteInput): that is how Yume can answer for you
        val replyAction = sbn.notification.actions?.firstOrNull { a -> a.remoteInputs?.isNotEmpty() == true }
        synchronized(recent) {
            recent.add(0, Note(app, title, text, System.currentTimeMillis(), replyAction))
            while (recent.size > 40) recent.removeAt(recent.size - 1)
        }
        if (CarMode.active && Prefs.carReadNotifications && Prefs.allowNotifications)
            PhoneTts.speak(("$app: $title. $text").take(240) + if (replyAction != null) tr(" Zum Antworten sag: antworte, und deinen Text.", " To reply say: reply, and your text.") else "")
    }

    class Note(val app: String, val title: String, val text: String, val time: Long, val replyAction: android.app.Notification.Action? = null)

    companion object {
        @Volatile var instance: YumeNotificationListener? = null
        val recent = ArrayList<Note>()
        val active: Boolean get() = instance != null

        /** Answers the latest message (last 10 minutes) through the messenger's own reply action. Asks on the phone first (PIN if set). */
        suspend fun reply(text: String): String {
            val note = synchronized(recent) { recent.firstOrNull { it.replyAction != null && System.currentTimeMillis() - it.time < 10 * 60_000 } }
                ?: return tr("Es gibt gerade keine Nachricht, auf die ich antworten könnte.", "There is currently no message I could reply to.")
            val to = note.title.ifEmpty { note.app }
            if (Prefs.confirmRisky && !Confirm.ask(tr("Yume möchte antworten", "Yume wants to reply"), tr("An $to: \"${text.take(160)}\"", "To $to: \"${text.take(160)}\""))) return tr("Vom Nutzer auf dem Handy abgelehnt.", "Declined by the user on the phone.")
            val action = note.replyAction!!
            return try {
                val ri = action.remoteInputs[0]
                val intent = android.content.Intent()
                val bundle = android.os.Bundle().apply { putCharSequence(ri.resultKey, text) }
                android.app.RemoteInput.addResultsToIntent(action.remoteInputs, intent, bundle)
                action.actionIntent.send(App.instance, 0, intent)
                tr("Geantwortet an $to: $text", "Replied to $to: $text")
            } catch (e: Exception) { tr("Antworten fehlgeschlagen: ${e.message}", "Reply failed: ${e.message}") }
        }

        fun summary(max: Int = 10): String = synchronized(recent) {
            if (recent.isEmpty()) tr("Keine neuen Benachrichtigungen.", "No new notifications.")
            else recent.take(max).joinToString("\n") { "- ${it.app}: ${it.title} ${it.text}".trim() }
        }
    }
}
