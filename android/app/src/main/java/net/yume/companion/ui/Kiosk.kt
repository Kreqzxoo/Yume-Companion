package net.yume.companion.ui

import net.yume.companion.core.Lang
import net.yume.companion.core.tr


import android.app.Activity
import android.view.WindowManager
import androidx.activity.compose.BackHandler
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsCompat
import androidx.core.view.WindowInsetsControllerCompat
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import net.yume.companion.core.Host
import net.yume.companion.core.Prefs
import net.yume.companion.core.Quiet
import net.yume.companion.voice.CallEngine
import net.yume.companion.voice.Phase
import net.yume.companion.voice.VoiceService
import net.yume.companion.voice.WakeState
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** Wall / tablet mode: clock, weather, appointments, lists and the character (3D model if downloaded) - and she hears the wake word. */
object KioskState { var active by mutableStateOf(false) }

private fun parse(s: String): JSONObject = try { JSONObject(s) } catch (_: Exception) { JSONObject() }

@Composable
fun KioskScreen(withMic: (() -> Unit) -> Unit) {
    val ctx = LocalContext.current
    val activity = ctx as? Activity
    val call by CallEngine.ui.collectAsState()
    val wake by WakeState.status.collectAsState()
    var data by remember { mutableStateOf(parse(Prefs.kioskCache)) }
    var now by remember { mutableStateOf(System.currentTimeMillis()) }
    val character = Prefs.character

    DisposableEffect(Unit) {
        val w = activity?.window
        w?.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        val c = w?.let { WindowCompat.getInsetsController(it, it.decorView) }
        c?.systemBarsBehavior = WindowInsetsControllerCompat.BEHAVIOR_SHOW_TRANSIENT_BARS_BY_SWIPE
        c?.hide(WindowInsetsCompat.Type.systemBars())
        onDispose {
            c?.show(WindowInsetsCompat.Type.systemBars())
            if (!Prefs.callKeepScreenOn) w?.clearFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
        }
    }
    BackHandler { KioskState.active = false }
    LaunchedEffect(Unit) { while (true) { now = System.currentTimeMillis(); delay(10_000) } }
    LaunchedEffect(Unit) {
        while (true) {
            val j = withContext(Dispatchers.IO) { Host.getJson("/api/kiosk") }
            if (j != null) { data = j; Prefs.kioskCache = j.toString() }
            delay(60_000)
        }
    }
    LaunchedEffect(Unit) { if (wake.isEmpty()) withMic { try { VoiceService.setWake(ctx, true) } catch (_: Exception) {} } }

    val chosen = remember(character) { net.yume.companion.ui.VrmStore.chosen(character) }
    val localVrm = chosen.isNotEmpty() && chosen != net.yume.companion.ui.VrmStore.NONE && net.yume.companion.ui.VrmStore.downloaded(chosen)
    var live by remember(chosen) { mutableStateOf(avatarReady(chosen)) }
    val night = Prefs.kioskNightDim && Quiet.inWindow()
    val phaseText = when {
        call.active -> when (call.phase) {
            Phase.LISTENING -> tr("Ich höre zu …", "I'm listening …"); Phase.HEARING -> "…"
            Phase.THINKING -> (ToolStatusRepo.current?.takeIf { it.state == "running" }?.label ?: tr("denkt nach …", "thinking …")); Phase.SPEAKING -> tr("spricht", "speaking"); Phase.IDLE -> ""
        }
        wake.isNotEmpty() -> tr("Sag das Wake Word oder tippe auf mich", "Say the wake word or tap me")
        else -> tr("Tippe auf mich zum Sprechen", "Tap me to speak")
    }
    fun listen() { if (!CallEngine.wantCall) withMic { VoiceService.startCall(ctx, oneShot = true) } }

    BoxWithConstraints(Modifier.fillMaxSize()) {
        val landscape = maxWidth > maxHeight
        YumeBackground()
        Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = if (night) 0.55f else 0f)))
        IconButton(onClick = { KioskState.active = false }, Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(8.dp)) { Icon(Icons.Filled.Close, tr("Beenden", "Exit"), tint = Color.White.copy(alpha = 0.4f)) }

        @Composable fun avatar(mod: Modifier) {
            Column(mod, horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                Box(Modifier.weight(1f).fillMaxWidth().clickable(enabled = !call.active) { listen() }, contentAlignment = Alignment.Center) {
                    if (!localVrm || !live) AvatarImage(character, Modifier.size(if (landscape) 220.dp else 160.dp), level = call.level)
                    if (localVrm) LocalAvatar(chosen, Modifier.fillMaxSize().then(if (live) Modifier else Modifier.size(1.dp)), zoom = Prefs.avatarZoom, onReady = { live = it },
                        appState = when (call.phase) { Phase.LISTENING, Phase.HEARING -> "LISTENING"; Phase.THINKING -> "PROCESSING"; else -> "STOPPED" })
                }
                Text(phaseText, color = Pink, fontSize = 16.sp, fontWeight = FontWeight.Medium)
                if (call.active && call.heard.isNotEmpty()) Text("„" + call.heard + "“", color = Color.White.copy(alpha = 0.75f), fontSize = 13.sp, maxLines = 2)
                if (call.active && call.reply.isNotEmpty()) Text(call.reply.takeLast(160), color = Color.White, fontSize = 15.sp, maxLines = 3)
                ToolStatusLine()
            }
        }

        @Composable fun info(mod: Modifier) {
            Column(mod.verticalScroll(rememberScrollState()), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                Text(SimpleDateFormat("HH:mm", if (Lang.isEn) Locale.ENGLISH else Locale.GERMAN).format(Date(now)), color = Color.White, fontSize = if (landscape) 96.sp else 72.sp, fontWeight = FontWeight.Light)
                Text(SimpleDateFormat(tr("EEEE, d. MMMM", "EEEE, MMMM d"), if (Lang.isEn) Locale.ENGLISH else Locale.GERMAN).format(Date(now)), color = Color.White.copy(alpha = 0.75f), fontSize = 18.sp)
                val w = data.optJSONObject("weather")
                if (w != null && w.has("temp")) KioskCard {
                    Text("${w.optInt("temp")} °C  ${w.optString("text")}", color = Color.White, fontSize = 22.sp)
                    Text("${w.optString("place")}  ·  ${tr("heute", "today")} ${w.optInt("tmin")}–${w.optInt("tmax")} °C" + (if (w.has("rain") && !w.isNull("rain")) "  ·  ${tr("Regen", "rain")} ${w.optInt("rain")} %" else ""), color = Color.White.copy(alpha = 0.7f), fontSize = 13.sp)
                    w.optString("tip").takeIf { it.isNotBlank() }?.let { Text(tr("Heute: $it", "Today: $it"), color = Pink, fontSize = 13.sp) }
                }
                val ev = data.optJSONArray("events")
                if (ev != null && ev.length() > 0) KioskCard {
                    Text(tr("Termine", "Appointments"), color = Color.White.copy(alpha = 0.6f), fontSize = 12.sp)
                    for (i in 0 until ev.length()) ev.optJSONObject(i)?.let { e ->
                        Text("${e.optString("day")} ${e.optString("time")}  ${e.optString("title")}" + (e.optString("place").takeIf { it.isNotBlank() }?.let { " @ $it" } ?: ""), color = Color.White, fontSize = 15.sp)
                    }
                }
                val rem = data.optJSONArray("reminders")
                if (rem != null && rem.length() > 0) KioskCard {
                    Text(tr("Erinnerungen", "Reminders"), color = Color.White.copy(alpha = 0.6f), fontSize = 12.sp)
                    for (i in 0 until rem.length()) rem.optJSONObject(i)?.let { r -> Text("${r.optString("when")}  ${r.optString("text")}", color = Color.White, fontSize = 15.sp) }
                }
                val lists = data.optJSONObject("lists")
                lists?.keys()?.forEach { name ->
                    val items = lists.optJSONArray(name)
                    if (items != null && items.length() > 0) KioskCard {
                        Text(name, color = Color.White.copy(alpha = 0.6f), fontSize = 12.sp)
                        Text((0 until items.length()).joinToString("  ·  ") { items.optString(it) }, color = Color.White, fontSize = 14.sp)
                    }
                }
                val bd = data.optJSONArray("birthdays")
                if (bd != null && bd.length() > 0) KioskCard {
                    for (i in 0 until bd.length()) bd.optJSONObject(i)?.let { b ->
                        val d = b.optInt("in_days")
                        Text("🎂 ${b.optString("name")}  " + (if (d == 0) tr("heute", "today") else if (d == 1) tr("morgen", "tomorrow") else tr("in $d Tagen", "in $d days")), color = Color.White, fontSize = 15.sp)
                    }
                }
                val music = data.optJSONObject("music")
                if (music != null) KioskCard { Text((if (music.optBoolean("playing")) "▶ " else "⏸ ") + music.optString("title") + " – " + music.optString("artist"), color = Color.White, fontSize = 14.sp) }
                if (data.has("unread_mails") && !data.isNull("unread_mails")) Text("✉ " + tr("${data.optInt("unread_mails")} ungelesene Mail(s)", "${data.optInt("unread_mails")} unread mail(s)"), color = Color.White.copy(alpha = 0.7f), fontSize = 13.sp)
            }
        }

        if (landscape) {
            Row(Modifier.fillMaxSize().statusBarsPadding().padding(28.dp), horizontalArrangement = Arrangement.spacedBy(24.dp)) {
                info(Modifier.weight(1.1f).fillMaxHeight())
                avatar(Modifier.weight(1f).fillMaxHeight())
            }
        } else {
            Column(Modifier.fillMaxSize().statusBarsPadding().padding(20.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                avatar(Modifier.weight(1f).fillMaxWidth())
                info(Modifier.weight(1.2f).fillMaxWidth())
            }
        }
    }
}

@Composable
private fun KioskCard(content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth().background(Color(0x771A1226), RoundedCornerShape(16.dp)).padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(2.dp), content = content)
}
