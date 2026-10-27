// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion

import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import net.yume.companion.core.Prefs
import net.yume.companion.ui.UiFlags
import net.yume.companion.ui.YumeTheme
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.Shadows
import org.robolectric.annotation.Config
import org.robolectric.annotation.GraphicsMode
import java.io.File

/** Renders the real screens headless and writes PNGs, so layout problems (missing menu bar ...) show up without a phone. */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w411dp-h891dp-xxhdpi")
class LayoutTest {
    @get:org.junit.Rule val phone = PhoneLocale(if (System.getenv("YUME_LANG") == "en") java.util.Locale.ENGLISH else java.util.Locale.GERMAN)
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val out = File(System.getenv("YUME_SHOTS") ?: "build/shots").also { it.mkdirs() }

    private fun shot(name: String) {
        rule.mainClock.advanceTimeBy(600)
        rule.waitForIdle()
        Shadows.shadowOf(android.os.Looper.getMainLooper()).idle()
        val v = rule.activity.window.decorView
        v.measure(android.view.View.MeasureSpec.makeMeasureSpec(1080, android.view.View.MeasureSpec.EXACTLY),
            android.view.View.MeasureSpec.makeMeasureSpec(2340, android.view.View.MeasureSpec.EXACTLY))
        v.layout(0, 0, 1080, 2340)
        val bmp = Bitmap.createBitmap(1080, 2340, Bitmap.Config.ARGB_8888)
        v.draw(Canvas(bmp))
        File(out, "$name.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private fun setup(askOnStart: Boolean) {
        Prefs.token = "t"; Prefs.localUrl = "http://192.168.1.50:8000"; Prefs.hostId = "h"
        Prefs.askCharacterOnStart = askOnStart; Prefs.defaultCharacter = "Aiko"; Prefs.character = "Aiko"
        Prefs.cachedCharacters = "Aiko,Mika"
        UiFlags.animations = false
        rule.setContent { YumeTheme { Root(null, {}, false, {}, { it() }) } }
        rule.mainClock.advanceTimeBy(300)
    }

    @Test fun picker() { setup(true); shot("1_picker") }

    @Test fun connectedChat() {
        // pretend the PC is connected: avatar web view + messages
        val f = net.yume.companion.core.HostLink::class.java.getDeclaredField("_state"); f.isAccessible = true
        @Suppress("UNCHECKED_CAST")
        (f.get(net.yume.companion.core.HostLink) as kotlinx.coroutines.flow.MutableStateFlow<net.yume.companion.core.Link>).value = net.yume.companion.core.Link.CONNECTED
        net.yume.companion.core.Host.baseUrl = "http://192.168.1.50:8000"
        net.yume.companion.core.ChatRepo.msgs.add(net.yume.companion.core.Msg("1", false, "Hallo! *winkt dir zu* Wie war dein Tag?"))
        net.yume.companion.core.ChatRepo.msgs.add(net.yume.companion.core.Msg("2", true, "Gut, danke! Und bei dir?"))
        setup(false)
        shot("5_connected")
    }

    @Test fun callScreen() {
        Prefs.character = "Aiko"
        UiFlags.animations = false
        rule.setContent { YumeTheme { net.yume.companion.ui.CallScreen(net.yume.companion.voice.CallUi(active = true, phase = net.yume.companion.voice.Phase.LISTENING, seconds = 5, heard = "Hallo", reply = "Hi!"), false) } }
        rule.mainClock.advanceTimeBy(300)
        shot("6_call_screen")
    }

    @Test fun homeAndTabs() {
        setup(false)
        shot("2_home")
        rule.onNodeWithText("Anruf").performClick(); shot("3_call")
        rule.onNodeWithText("Einstellungen").performClick(); shot("4_settings")
    }
}
