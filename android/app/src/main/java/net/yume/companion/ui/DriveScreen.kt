package net.yume.companion.ui

import android.content.Context
import android.content.Intent
import android.media.AudioManager
import android.net.Uri
import android.view.KeyEvent
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext
import net.yume.companion.core.Host
import net.yume.companion.core.Prefs
import net.yume.companion.voice.CallEngine
import net.yume.companion.voice.CallUi
import net.yume.companion.voice.Phase
import org.json.JSONObject
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * Drive dashboard (car mode): big and calm. Next appointment with a "Navigate" button, music keys, what Yume hears and says.
 * This is Yume's own screen on the phone (or on a phone holder) - NOT the Android Auto car display: Google does not allow
 * free-form assistant apps there. Yume keeps listening by voice while this screen is shown.
 */
@Composable
fun DriveScreen(call: CallUi) {
    val ctx = LocalContext.current
    var data by remember { mutableStateOf(try { JSONObject(Prefs.kioskCache) } catch (_: Exception) { JSONObject() }) }
    var now by remember { mutableStateOf(System.currentTimeMillis()) }
    LaunchedEffect(Unit) { while (true) { now = System.currentTimeMillis(); delay(10_000) } }
    LaunchedEffect(Unit) {
        while (true) {
            val j = withContext(Dispatchers.IO) { Host.getJson("/api/kiosk") }
            if (j != null) { data = j; Prefs.kioskCache = j.toString() }
            delay(120_000)
        }
    }
    val next = remember(data) {
        val ev = data.optJSONArray("events")
        (0 until (ev?.length() ?: 0)).mapNotNull { ev?.optJSONObject(it) }.let { list -> list.firstOrNull { it.optString("place").isNotBlank() } ?: list.firstOrNull() }
    }
    val status = when (call.phase) {
        Phase.LISTENING -> "Ich höre zu …"; Phase.HEARING -> "…"
        Phase.THINKING -> (ToolStatusRepo.current?.takeIf { it.state == "running" }?.label ?: "denkt nach …"); Phase.SPEAKING -> "spricht"; Phase.IDLE -> ""
    }

    Column(Modifier.fillMaxSize().background(Color(0xFF0B0714)).statusBarsPadding().navigationBarsPadding().padding(20.dp), verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(SimpleDateFormat("HH:mm", Locale.GERMAN).format(Date(now)), color = Color.White, fontSize = 64.sp, fontWeight = FontWeight.Light, modifier = Modifier.weight(1f))
            val w = data.optJSONObject("weather")
            if (w != null && w.has("temp")) Text("${w.optInt("temp")} °C", color = Color.White.copy(alpha = 0.85f), fontSize = 28.sp)
        }
        Column(Modifier.fillMaxWidth().background(Color(0xFF1A1226), RoundedCornerShape(20.dp)).padding(18.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            if (next != null) {
                Text("Nächster Termin", color = Color.White.copy(alpha = 0.6f), fontSize = 14.sp)
                Text("${next.optString("day")} ${next.optString("time")}  ${next.optString("title")}", color = Color.White, fontSize = 24.sp, fontWeight = FontWeight.Medium)
                val place = next.optString("place")
                if (place.isNotBlank()) {
                    Text(place, color = Violet, fontSize = 16.sp)
                    Button(onClick = { navigate(ctx, place) }, Modifier.fillMaxWidth().height(64.dp)) { Text("Navigation starten", fontSize = 20.sp) }
                }
            } else Text("Keine Termine in nächster Zeit.", color = Color.White.copy(alpha = 0.8f), fontSize = 20.sp)
        }
        val music = data.optJSONObject("music")
        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
            OutlinedButton(onClick = { key(ctx, KeyEvent.KEYCODE_MEDIA_PREVIOUS) }, Modifier.weight(1f).height(72.dp)) { Text("⏮", fontSize = 28.sp) }
            OutlinedButton(onClick = { key(ctx, KeyEvent.KEYCODE_MEDIA_PLAY_PAUSE) }, Modifier.weight(1.4f).height(72.dp)) { Text("⏯", fontSize = 28.sp) }
            OutlinedButton(onClick = { key(ctx, KeyEvent.KEYCODE_MEDIA_NEXT) }, Modifier.weight(1f).height(72.dp)) { Text("⏭", fontSize = 28.sp) }
        }
        if (music != null && music.optString("title").isNotBlank()) Text("♪ ${music.optString("title")} – ${music.optString("artist")}", color = Color.White.copy(alpha = 0.7f), fontSize = 14.sp, maxLines = 1)
        Spacer(Modifier.weight(1f))
        Column(Modifier.fillMaxWidth(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Text(status, color = Pink, fontSize = 22.sp, fontWeight = FontWeight.Medium)
            if (call.heard.isNotEmpty()) Text("„" + call.heard + "“", color = Color.White.copy(alpha = 0.75f), fontSize = 16.sp, maxLines = 2)
            if (call.reply.isNotEmpty()) Text(call.reply.takeLast(200), color = Color.White, fontSize = 18.sp, maxLines = 4)
            ToolStatusLine()
        }
        OutlinedButton(onClick = { CallEngine.hangup() }, Modifier.fillMaxWidth().height(56.dp)) { Text("Auto-Modus beenden", fontSize = 16.sp) }
    }
}

private fun key(ctx: Context, code: Int) {
    val am = ctx.getSystemService(AudioManager::class.java)
    am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_DOWN, code)); am.dispatchMediaKeyEvent(KeyEvent(KeyEvent.ACTION_UP, code))
}

private fun navigate(ctx: Context, place: String) {
    val q = Uri.encode(place)
    val tries = listOf(Intent(Intent.ACTION_VIEW, Uri.parse("google.navigation:q=$q")).setPackage("com.google.android.apps.maps"), Intent(Intent.ACTION_VIEW, Uri.parse("geo:0,0?q=$q")))
    for (i in tries) {
        try { ctx.startActivity(i.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)); return } catch (_: Exception) {}
    }
}
