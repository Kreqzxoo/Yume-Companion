// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.voice

import net.yume.companion.core.tr

import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import android.graphics.PixelFormat
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.Gravity
import android.view.KeyEvent
import android.view.MotionEvent
import android.view.WindowManager
import android.widget.FrameLayout
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.ComposeView
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleOwner
import androidx.lifecycle.LifecycleRegistry
import androidx.lifecycle.setViewTreeLifecycleOwner
import androidx.savedstate.SavedStateRegistry
import androidx.savedstate.SavedStateRegistryController
import androidx.savedstate.SavedStateRegistryOwner
import androidx.savedstate.setViewTreeSavedStateRegistryOwner
import kotlinx.coroutines.delay
import net.yume.companion.App
import net.yume.companion.MainActivity
import net.yume.companion.core.Prefs
import net.yume.companion.ui.AvatarImage
import net.yume.companion.ui.Pink
import net.yume.companion.ui.Violet
import net.yume.companion.ui.YumeTheme

private class OverlayOwner : LifecycleOwner, SavedStateRegistryOwner {
    private val registry = LifecycleRegistry(this)
    private val controller = SavedStateRegistryController.create(this)
    init { controller.performAttach(); controller.performRestore(null); registry.currentState = Lifecycle.State.RESUMED }
    override val lifecycle: Lifecycle get() = registry
    override val savedStateRegistry: SavedStateRegistry get() = controller.savedStateRegistry
    fun destroy() { registry.currentState = Lifecycle.State.DESTROYED }
}

/** Root of the panel: reports the back key and touches outside of it (= tap on the home screen / the app behind) so the panel can close. */
private class PanelRoot(ctx: Context, private val onDismiss: () -> Unit) : FrameLayout(ctx) {
    override fun dispatchKeyEvent(event: KeyEvent): Boolean {
        if (event.keyCode == KeyEvent.KEYCODE_BACK) { if (event.action == KeyEvent.ACTION_UP) onDismiss(); return true }
        return super.dispatchKeyEvent(event)
    }
    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (event.action == MotionEvent.ACTION_OUTSIDE) { onDismiss(); return true }
        return super.onTouchEvent(event)
    }
}

/**
 * Like the Google Assistant: when the wake word is heard while another app (or the home screen) is in front, a translucent panel slides up
 * from the bottom and shows that Yume is listening, what she understood and what she answers.
 * It stays until YOU close it: tr("Schließen", "Close"), the back key, the home button or a tap outside of the panel. It does not listen all the time:
 * one question, one answer - then it waits for the wake word again or a tap on her picture / the microphone button.
 * Needs "display over other apps".
 */
object AssistOverlay {
    private var view: PanelRoot? = null
    private var owner: OverlayOwner? = null
    private var homeReceiver: BroadcastReceiver? = null
    private val main = Handler(Looper.getMainLooper())

    val isShown: Boolean get() = view != null
    val available: Boolean get() = Prefs.wakeOverlay && !App.uiVisible && Settings.canDrawOverlays(App.instance)

    fun show(ctx: Context) = main.post {
        if (view != null || !available) return@post
        val app = ctx.applicationContext
        val o = OverlayOwner()
        val root = PanelRoot(app) { dismiss() }
        val compose = ComposeView(app).apply { setContent { YumeTheme { Panel() } } }
        root.addView(compose, FrameLayout.LayoutParams(FrameLayout.LayoutParams.MATCH_PARENT, FrameLayout.LayoutParams.WRAP_CONTENT))
        root.setViewTreeLifecycleOwner(o); root.setViewTreeSavedStateRegistryOwner(o)
        compose.setViewTreeLifecycleOwner(o); compose.setViewTreeSavedStateRegistryOwner(o)
        val lp = WindowManager.LayoutParams(
            WindowManager.LayoutParams.MATCH_PARENT, WindowManager.LayoutParams.WRAP_CONTENT,
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY,
            // focusable (gets the back key), touches next to the panel go to the app behind AND tell us to close
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH or WindowManager.LayoutParams.FLAG_LAYOUT_IN_SCREEN,
            PixelFormat.TRANSLUCENT,
        ).apply { gravity = Gravity.BOTTOM }
        try {
            app.getSystemService(WindowManager::class.java).addView(root, lp)
            view = root; owner = o
            // home button / recent apps: the system announces it with this broadcast (best effort - newer Android versions may not deliver it)
            val receiver = object : BroadcastReceiver() {
                override fun onReceive(c: Context, i: Intent) {
                    val reason = i.getStringExtra("reason") ?: return
                    if (reason == "homekey" || reason == "recentapps") dismiss()
                }
            }
            @Suppress("DEPRECATION")
            try { app.registerReceiver(receiver, IntentFilter(Intent.ACTION_CLOSE_SYSTEM_DIALOGS)); homeReceiver = receiver } catch (_: Exception) {}
        } catch (_: Exception) { o.destroy() }
    }

    /** the user closed it (back, home, tap outside): the speech stops, too */
    fun dismiss() { AudioPlayer.stop(); PhoneTts.stop(); hide() }

    fun hide() = main.post {
        val v = view ?: return@post
        try { App.instance.getSystemService(WindowManager::class.java).removeView(v) } catch (_: Exception) {}
        homeReceiver?.let { try { App.instance.unregisterReceiver(it) } catch (_: Exception) {} }
        homeReceiver = null
        owner?.destroy(); owner = null; view = null
        if (CallEngine.singleTurn) CallEngine.hangup()          // closed in the middle of a turn: stop listening
    }

    @Composable
    internal fun Panel() {
        val call by CallEngine.ui.collectAsState()
        var seenActive by remember { mutableStateOf(false) }
        var heard by remember { mutableStateOf("") }
        var reply by remember { mutableStateOf("") }
        var problem by remember { mutableStateOf("") }
        if (call.active) seenActive = true
        LaunchedEffect(call.error) { if (call.error.isNotEmpty()) problem = call.error }      // e.g. "PC not reachable": it must be visible, not silent
        // the panel keeps the last words readable after the turn is over
        LaunchedEffect(call.heard) { if (call.heard.isNotEmpty()) heard = call.heard }
        LaunchedEffect(call.reply) { if (call.reply.isNotEmpty()) reply = call.reply }
        LaunchedEffect(call.active) { if (call.active && call.heard.isEmpty()) { heard = ""; if (call.reply.isEmpty()) reply = "" } }
        // only a false alarm (nothing was ever started) closes it by itself
        LaunchedEffect(Unit) { delay(10_000); if (!seenActive && !CallEngine.ui.value.active) hide() }

        val idle = !call.active
        val phaseText = when {
            call.active -> when (call.phase) {
                Phase.LISTENING -> tr("Ich höre zu …", "I'm listening …"); Phase.HEARING -> "…"; Phase.THINKING -> (net.yume.companion.ui.ToolStatusRepo.current?.takeIf { it.state == "running" }?.label ?: tr("denkt nach …", "thinking …")); Phase.SPEAKING -> tr("spricht", "speaking"); Phase.IDLE -> tr("Ich höre zu …", "I'm listening …")
            }
            seenActive -> tr("Tippe auf mich oder sag das Wake Word", "Tap me or say the wake word")
            else -> tr("Ich höre zu …", "I'm listening …")
        }
        val level by animateFloatAsState(if (call.active && call.phase == Phase.SPEAKING) 0.55f else call.level, tween(90), label = "level")
        fun listen() {
            if (!CallEngine.wantCall) try { VoiceService.startCall(App.instance, oneShot = true, single = true) } catch (_: Exception) {}
        }

        Column(
            Modifier.fillMaxWidth().background(Color(0xE61A1226), RoundedCornerShape(topStart = 28.dp, topEnd = 28.dp)).navigationBarsPadding()
                .padding(horizontal = 20.dp, vertical = 16.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                AvatarImage(Prefs.character, Modifier.size(52.dp).clickable(enabled = idle) { listen() }, level = level)
                Spacer(Modifier.width(12.dp))
                Column(Modifier.weight(1f)) {
                    Text(Prefs.character.ifEmpty { "Yume" }, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 16.sp)
                    Text(phaseText, color = Pink, fontSize = 13.sp)
                }
                // level bars: they move with the voice (yours while listening, hers while speaking)
                Row(horizontalArrangement = Arrangement.spacedBy(4.dp), verticalAlignment = Alignment.CenterVertically, modifier = Modifier.height(28.dp)) {
                    listOf(0.6f, 1f, 0.75f, 0.9f, 0.5f).forEach { k ->
                        Box(Modifier.width(5.dp).height((6 + 22 * (level * k).coerceIn(0f, 1f)).dp).background(Violet, RoundedCornerShape(3.dp)))
                    }
                }
            }
            net.yume.companion.ui.ToolStatusLine(Modifier.padding(top = 8.dp))
            Column(Modifier.heightIn(max = 260.dp).verticalScroll(rememberScrollState())) {
                if (heard.isNotEmpty()) { Spacer(Modifier.height(10.dp)); Text(heard, color = Color.White.copy(alpha = 0.7f), fontSize = 14.sp) }
                if (reply.isNotEmpty()) { Spacer(Modifier.height(8.dp)); Text(reply, color = Color.White, fontSize = 16.sp) }
                if (problem.isNotEmpty() && reply.isEmpty()) { Spacer(Modifier.height(8.dp)); Text(problem, color = Color(0xFFFF8A8A), fontSize = 14.sp) }
            }
            Spacer(Modifier.height(10.dp))
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                TextButton(onClick = { CallEngine.hangup(); AudioPlayer.stop(); PhoneTts.stop(); hide() }) { Text(tr("Schließen", "Close"), color = Color.White.copy(alpha = 0.8f)) }
                if (idle) Button(onClick = { listen() }) { Text("Sprechen") }
                TextButton(onClick = {
                    val ctx = App.instance
                    ctx.startActivity(Intent(ctx, MainActivity::class.java).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK or Intent.FLAG_ACTIVITY_SINGLE_TOP))
                    hide()
                }) { Text(tr("App öffnen", "Open app"), color = Pink) }
            }
        }
    }
}
