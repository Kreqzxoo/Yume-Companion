package net.yume.companion

import android.graphics.Bitmap
import android.graphics.Canvas
import androidx.activity.ComponentActivity
import androidx.compose.ui.test.junit4.createAndroidComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import androidx.compose.ui.test.performScrollTo
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
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/**
 * Bilder fuer die Dokumentation (docs/images/android): rendert die echten Bildschirme ohne Handy.
 * Aufruf:  set YUME_SHOTS=C:\Pfad\docs\images\android  und  run-unit-tests.ps1
 * Es werden nur erfundene Demo-Daten verwendet (Charaktere "Aiko" und "Mika", Adresse 192.168.1.50).
 */
@RunWith(RobolectricTestRunner::class)
@GraphicsMode(GraphicsMode.Mode.NATIVE)
@Config(sdk = [34], qualifiers = "w411dp-h891dp-xxhdpi")
class DocShotsTest {
    @get:Rule val rule = createAndroidComposeRule<ComponentActivity>()
    private val out = File(System.getenv("YUME_SHOTS") ?: "build/doc-shots").also { it.mkdirs() }

    private fun shot(name: String, height: Int = 2340) {
        rule.mainClock.advanceTimeBy(600)
        rule.waitForIdle()
        Shadows.shadowOf(android.os.Looper.getMainLooper()).idle()
        val v = rule.activity.window.decorView
        v.measure(android.view.View.MeasureSpec.makeMeasureSpec(1080, android.view.View.MeasureSpec.EXACTLY),
            android.view.View.MeasureSpec.makeMeasureSpec(height, android.view.View.MeasureSpec.EXACTLY))
        v.layout(0, 0, 1080, height)
        val bmp = Bitmap.createBitmap(1080, height, Bitmap.Config.ARGB_8888)
        v.draw(Canvas(bmp))
        File(out, "$name.png").outputStream().use { bmp.compress(Bitmap.CompressFormat.PNG, 100, it) }
    }

    private fun demoPrefs(askOnStart: Boolean) {
        Prefs.token = "t"; Prefs.localUrl = "http://192.168.1.50:8000"; Prefs.hostId = "h"
        Prefs.askCharacterOnStart = askOnStart; Prefs.defaultCharacter = "Aiko"; Prefs.character = "Aiko"
        Prefs.cachedCharacters = "Aiko,Mika"
        UiFlags.animations = false
    }

    private fun root() {
        rule.setContent { YumeTheme { Root(null, {}, false, {}, { it() }) } }
        rule.mainClock.advanceTimeBy(300)
    }

    @Test fun pair() {
        Prefs.token = ""; Prefs.hostId = ""; UiFlags.animations = false
        rule.setContent { YumeTheme { Root(null, {}, false, {}, { it() }) } }
        rule.mainClock.advanceTimeBy(300)
        shot("01_koppeln")
    }

    @Test fun picker() { demoPrefs(true); root(); shot("02_charakter_waehlen") }

    @Test fun homeOffline() { demoPrefs(false); root(); shot("03_start_offline") }

    @Test fun connectedChat() {
        val f = net.yume.companion.core.HostLink::class.java.getDeclaredField("_state"); f.isAccessible = true
        @Suppress("UNCHECKED_CAST")
        (f.get(net.yume.companion.core.HostLink) as kotlinx.coroutines.flow.MutableStateFlow<net.yume.companion.core.Link>).value = net.yume.companion.core.Link.CONNECTED
        net.yume.companion.core.Host.baseUrl = "http://192.168.1.50:8000"
        net.yume.companion.core.ChatRepo.msgs.add(net.yume.companion.core.Msg("1", false, "Hallo! *winkt dir zu* Wie war dein Tag?"))
        net.yume.companion.core.ChatRepo.msgs.add(net.yume.companion.core.Msg("2", true, "Gut, danke! Setz bitte Milch auf die Einkaufsliste."))
        net.yume.companion.core.ChatRepo.msgs.add(net.yume.companion.core.Msg("3", false, "Erledigt: Milch steht auf der Einkaufsliste."))
        demoPrefs(false); root()
        shot("04_chat_verbunden")
    }

    @Test fun tabs() {
        demoPrefs(false); root()
        rule.onNodeWithText("Anruf").performClick(); shot("05_anruf_start")
        rule.onNodeWithText("Offline").performClick(); shot("06_offline_notfallmodus")
        rule.onNodeWithText("Einstellungen").performClick(); shot("07_einstellungen")
    }

    /** Scrollt die lange Einstellungsseite Abschnitt fuer Abschnitt durch. */
    @Test fun settingsSections() {
        demoPrefs(false); root()
        rule.onNodeWithText("Einstellungen").performClick()
        val sections = listOf(
            "Sprache & Wake Word" to "07a_einstellungen_wake_word",
            "Gespräch" to "07b_einstellungen_gespraech",
            "Handy-Steuerung durch die KI" to "07c_einstellungen_handy_steuerung",
            "Als Anrufschutz-App festlegen" to "07d_einstellungen_anrufschutz",
            "Automatisierung" to "07e_einstellungen_automatisierung",
            "Spotify" to "07f_einstellungen_spotify",
            "Auto-Modus" to "07g_einstellungen_auto_modus",
            "Berechtigungen" to "07h_einstellungen_berechtigungen",
            "Charaktere & Start" to "07i_einstellungen_charaktere",
            "Hintergrund & Avatar" to "07j_einstellungen_avatar",
            "Zurücksetzen" to "07k_einstellungen_zuruecksetzen",
        )
        for ((title, file) in sections) {
            try {
                rule.onNodeWithText(title, ignoreCase = true).performScrollTo()
                shot(file)
            } catch (e: Throwable) { println("Abschnitt nicht gefunden: $title (" + e.message + ")") }
        }
    }

    @Test fun callScreen() {
        Prefs.character = "Aiko"; UiFlags.animations = false
        rule.setContent {
            YumeTheme {
                net.yume.companion.ui.CallScreen(
                    net.yume.companion.voice.CallUi(active = true, phase = net.yume.companion.voice.Phase.LISTENING, seconds = 42,
                        heard = "Wie wird das Wetter morgen?", reply = "Morgen wird es sonnig, bis zu 21 Grad."), false)
            }
        }
        rule.mainClock.advanceTimeBy(300)
        shot("09_im_gespraech")
    }

    /** Assistenten-Fenster ueber dem Startbildschirm (der Startbildschirm ist nachgebaut, die Platte ist das echte Fenster) */
    @Test fun assistHome() {
        demoPrefs(false); UiFlags.animations = false
        val ui = net.yume.companion.voice.CallEngine::class.java.getDeclaredField("_ui").also { it.isAccessible = true }
        @Suppress("UNCHECKED_CAST")
        (ui.get(net.yume.companion.voice.CallEngine) as kotlinx.coroutines.flow.MutableStateFlow<net.yume.companion.voice.CallUi>).value =
            net.yume.companion.voice.CallUi(active = true, phase = net.yume.companion.voice.Phase.LISTENING, level = 0.6f,
                heard = "Yume, wie wird das Wetter morgen?", reply = "Morgen wird es sonnig, bis zu 21 Grad. Soll ich dich vor dem Regen am Wochenende erinnern?")
        rule.setContent {
            YumeTheme {
                androidx.compose.foundation.layout.Box(androidx.compose.ui.Modifier.fillMaxSize()) {
                    MockHomeScreen()
                    androidx.compose.foundation.layout.Box(androidx.compose.ui.Modifier.align(androidx.compose.ui.Alignment.BottomCenter)) {
                        net.yume.companion.voice.AssistOverlay.Panel()
                    }
                }
            }
        }
        rule.mainClock.advanceTimeBy(300)
        shot("13_assistent_startbildschirm")
        (ui.get(net.yume.companion.voice.CallEngine) as kotlinx.coroutines.flow.MutableStateFlow<net.yume.companion.voice.CallUi>).value = net.yume.companion.voice.CallUi()   // Zustand fuer die anderen Tests zuruecksetzen
    }

    @Test fun kiosk() {
        demoPrefs(false); UiFlags.animations = false
        rule.setContent { YumeTheme { net.yume.companion.ui.KioskScreen({ it() }) } }
        rule.mainClock.advanceTimeBy(300)
        shot("10_wandmodus")
    }

    @Test fun drive() {
        demoPrefs(false); UiFlags.animations = false
        rule.setContent { YumeTheme { net.yume.companion.ui.DriveScreen(net.yume.companion.voice.CallUi(active = true, phase = net.yume.companion.voice.Phase.LISTENING, seconds = 3)) } }
        rule.mainClock.advanceTimeBy(300)
        shot("11_auto_modus")
    }

    @Test fun micTest() {
        demoPrefs(false); UiFlags.animations = false
        rule.setContent { YumeTheme { net.yume.companion.ui.MicTestDialog({}) } }
        rule.mainClock.advanceTimeBy(300)
        shot("12_mikrofontest")
    }
}

/** Nachgebauter Startbildschirm mit neutralen Platzhalter-Symbolen (keine echten App-Logos) */
@androidx.compose.runtime.Composable
private fun MockHomeScreen() {
    androidx.compose.foundation.layout.Column(
        androidx.compose.ui.Modifier.fillMaxSize()
            .background(androidx.compose.ui.graphics.Brush.verticalGradient(listOf(androidx.compose.ui.graphics.Color(0xFF3B2A6B), androidx.compose.ui.graphics.Color(0xFF14102A))))
            .padding(horizontal = 24.dp, vertical = 48.dp),
    ) {
        androidx.compose.material3.Text("09:41", color = androidx.compose.ui.graphics.Color.White, fontSize = 64.sp, fontWeight = androidx.compose.ui.text.font.FontWeight.Light)
        androidx.compose.material3.Text("Freitag, 24. Oktober", color = androidx.compose.ui.graphics.Color.White.copy(alpha = 0.8f), fontSize = 16.sp)
        androidx.compose.foundation.layout.Spacer(androidx.compose.ui.Modifier.height(48.dp))
        val colors = listOf(0xFFE57373, 0xFF64B5F6, 0xFF81C784, 0xFFFFB74D, 0xFFBA68C8, 0xFF4DB6AC, 0xFFF06292, 0xFF9575CD)
        repeat(3) { row ->
            androidx.compose.foundation.layout.Row(androidx.compose.ui.Modifier.fillMaxWidth().padding(bottom = 28.dp), horizontalArrangement = androidx.compose.foundation.layout.Arrangement.SpaceBetween) {
                repeat(4) { col ->
                    androidx.compose.foundation.layout.Box(
                        androidx.compose.ui.Modifier.size(60.dp).background(androidx.compose.ui.graphics.Color(colors[(row * 4 + col) % colors.size]).copy(alpha = 0.85f), androidx.compose.foundation.shape.RoundedCornerShape(16.dp)),
                    )
                }
            }
        }
    }
}
