// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.ui

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.webkit.JavascriptInterface
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebSettings
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext
import net.yume.companion.R
import net.yume.companion.core.Host
import net.yume.companion.core.Prefs
import okhttp3.Request
import java.io.File
import kotlin.math.PI
import kotlin.math.cos
import kotlin.math.sin

/** Small in-memory cache for avatars / backgrounds fetched from the PC. */
object ImageCache {
    private val map = HashMap<String, Bitmap>()

    suspend fun fetch(path: String, maxEdge: Int = 900): Bitmap? {
        val base = Host.baseUrl
        if (base.isEmpty()) return null
        val key = "$base$path"
        map[key]?.let { return it }
        return withContext(Dispatchers.IO) {
            try {
                Host.clientFor(base).newCall(Request.Builder().url(key).header("X-Yume-Token", Prefs.token).build()).execute().use { r ->
                    if (!r.isSuccessful) return@use null
                    val bytes = r.body?.bytes() ?: return@use null
                    val opts = BitmapFactory.Options().apply { inJustDecodeBounds = true }
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, opts)
                    var sample = 1
                    while (maxOf(opts.outWidth, opts.outHeight) / sample > maxEdge * 1.5) sample *= 2
                    BitmapFactory.decodeByteArray(bytes, 0, bytes.size, BitmapFactory.Options().apply { inSampleSize = sample })
                }?.also { map[key] = it }
            } catch (_: Exception) { null }
        }
    }
}

private fun enc(s: String) = java.net.URLEncoder.encode(s, "UTF-8").replace("+", "%20")

@Composable
fun AvatarImage(name: String, modifier: Modifier = Modifier, circle: Boolean = true, level: Float = 0f) {
    val base = Host.baseUrl
    val bmp by produceState<Bitmap?>(null, base, name) { value = if (name.isEmpty()) null else ImageCache.fetch("/api/avatar/" + enc(name), 700) }
    val pulse by animateFloatAsState(1f + level * 0.18f, tween(80), label = "pulse")
    val shape = if (circle) CircleShape else androidx.compose.foundation.shape.RoundedCornerShape(18.dp)
    Box(modifier.scale(pulse).clip(shape).background(Panel)) {
        val b = bmp
        if (b != null) Image(b.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        else Image(painterResource(R.drawable.logo), null, Modifier.fillMaxSize().padding(14.dp))
    }
}

/** Animated night-sky background (drifting colour clouds, floating petals) or the PC's / an own picture. */
@Composable
fun YumeBackground(modifier: Modifier = Modifier) {
    val mode = Prefs.bgMode
    val base = Host.baseUrl
    val picture by produceState<Bitmap?>(null, mode, base, Prefs.bgCustomPath) {
        value = when (mode) {
            "host" -> ImageCache.fetch("/api/background", 1600)
            "custom" -> withContext(Dispatchers.IO) { try { File(Prefs.bgCustomPath).takeIf { it.exists() }?.let { BitmapFactory.decodeFile(it.absolutePath) } } catch (_: Exception) { null } }
            else -> null
        }
    }
    val phase: Float = if (UiFlags.animations) {
        val t = rememberInfiniteTransition(label = "bg")
        val p by t.animateFloat(0f, 1f, infiniteRepeatable(tween(60_000, easing = LinearEasing)), label = "phase")
        p
    } else 0f
    val petals = remember { List(26) { i -> floatArrayOf(((i * 37) % 100) / 100f, ((i * 53) % 100) / 100f, 0.6f + ((i * 17) % 10) / 14f, ((i * 29) % 100) / 100f) } }

    Box(modifier.fillMaxSize().background(Night)) {
        val pic = picture
        if (pic != null) {
            Image(pic.asImageBitmap(), null, Modifier.fillMaxSize(), contentScale = ContentScale.Crop)
        } else {
            Canvas(Modifier.fillMaxSize()) {
                drawRect(Brush.verticalGradient(listOf(Color(0xFF140B22), Color(0xFF241238), Color(0xFF1A0E2B))))
                val w = size.width; val h = size.height
                val a = phase * 2 * PI.toFloat()
                fun blob(cx: Float, cy: Float, r: Float, c: Color) =
                    drawCircle(Brush.radialGradient(listOf(c.copy(alpha = 0.40f), Color.Transparent), center = Offset(cx, cy), radius = r), r, Offset(cx, cy))
                blob(w * (0.25f + 0.12f * sin(a)), h * (0.22f + 0.08f * cos(a * 1.0f)), w * 0.75f, Pink)
                blob(w * (0.80f + 0.10f * cos(a * 2)), h * (0.55f + 0.10f * sin(a * 2)), w * 0.85f, Violet)
                blob(w * (0.45f + 0.15f * sin(a * 3 + 1)), h * (0.92f + 0.05f * cos(a * 3)), w * 0.9f, Color(0xFF6C4BFF))
            }
        }
        if (Prefs.bgParticles) {
            Canvas(Modifier.fillMaxSize()) {
                val w = size.width; val h = size.height
                for (p in petals) {
                    val speed = 0.5f + p[2]
                    val prog = (phase * 8 * speed + p[3]) % 1f
                    val x = (p[0] + 0.05f * sin((prog + p[3]) * 6.28f * 2)) * w
                    val y = prog * (h + 40f) - 20f
                    val r = 3f + 5f * p[2]
                    drawCircle(Pink.copy(alpha = 0.22f * (1f - kotlin.math.abs(prog - 0.5f) * 1.2f).coerceIn(0f, 1f)), r, Offset(x, y))
                }
            }
        }
        Box(Modifier.fillMaxSize().background(Color.Black.copy(alpha = (Prefs.bgDim / 100f).coerceIn(0f, 0.85f))))
    }
}

/** Transparent web view that shows only the 3D (VRM) / Live2D model of the PC, with idle animation, blinking and emotions. */
class AvatarBridge(private val onState: (String, Boolean) -> Unit) {
    @JavascriptInterface fun avatarState(mode: String, ok: Boolean) { onState(mode, ok) }
}

@SuppressLint("SetJavaScriptEnabled")
@Composable
fun AvatarWebView(modifier: Modifier, onReady: (Boolean) -> Unit) {
    val base = Host.baseUrl
    val url = base + "/?mode=avatar&token=" + enc(Prefs.token)
    val voice = Prefs.chatVoice
    val cb by rememberUpdatedState(onReady)
    AndroidView(modifier = modifier, factory = { c ->
        WebView(c).apply {
            settings.javaScriptEnabled = true
            settings.domStorageEnabled = true
            settings.mediaPlaybackRequiresUserGesture = !voice
            settings.mixedContentMode = WebSettings.MIXED_CONTENT_ALWAYS_ALLOW
            setBackgroundColor(0x00000000)
            addJavascriptInterface(AvatarBridge { mode, ok -> post { cb(ok && mode != "none" && mode != "error") } }, "YumeBridge")
            webViewClient = WebViewClient()
            webChromeClient = object : WebChromeClient() {
                override fun onPermissionRequest(request: PermissionRequest) { request.grant(request.resources) }
            }
            loadUrl(url)
        }
    }, update = { w -> if (w.url?.substringBefore('?') != url.substringBefore('?')) w.loadUrl(url) }, onRelease = { it.destroy() })
}
