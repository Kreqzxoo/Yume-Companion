package net.yume.companion.device

import android.graphics.Bitmap
import android.graphics.Matrix
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import androidx.lifecycle.compose.LocalLifecycleOwner
import java.io.ByteArrayOutputStream
import java.util.concurrent.Executors

/**
 * Video call: the camera of the phone is shown small in the call and Yume "sees" it - with every sentence you say, the newest camera
 * picture goes to the PC, whose vision model describes it for her. (No continuous video stream: she sees one moment per sentence.)
 */
object VideoCall {
    var enabled by mutableStateOf(false)
    var front by mutableStateOf(true)
    @Volatile private var latest: ByteArray? = null

    fun snapshot(): ByteArray? = if (enabled) latest else null
    fun reset() { enabled = false; latest = null }
    internal fun store(jpeg: ByteArray) { latest = jpeg }
}

/** Camera preview that also keeps the newest frame (about every 1.5 s, at most 640 px) for [VideoCall.snapshot]. */
@Composable
fun VideoCallPreview(modifier: Modifier) {
    val ctx = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val front = VideoCall.front
    val executor = androidx.compose.runtime.remember { Executors.newSingleThreadExecutor() }

    AndroidView(modifier = modifier, factory = { c ->
        PreviewView(c).apply { scaleType = PreviewView.ScaleType.FILL_CENTER; implementationMode = PreviewView.ImplementationMode.COMPATIBLE }
    }, update = { view ->
        val future = ProcessCameraProvider.getInstance(ctx)
        future.addListener({
            try {
                val provider = future.get()
                val preview = Preview.Builder().build().also { it.setSurfaceProvider(view.surfaceProvider) }
                var last = 0L
                val analysis = ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build().also { a ->
                    a.setAnalyzer(executor) { image ->
                        try {
                            val now = System.currentTimeMillis()
                            if (now - last > 1500) {
                                last = now
                                var bmp: Bitmap = image.toBitmap()
                                val rot = image.imageInfo.rotationDegrees
                                val scale = 640f / maxOf(bmp.width, bmp.height)
                                val m = Matrix().apply { postRotate(rot.toFloat()); if (scale < 1f) postScale(scale, scale) }
                                bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, m, true)
                                val out = ByteArrayOutputStream()
                                bmp.compress(Bitmap.CompressFormat.JPEG, 70, out)
                                VideoCall.store(out.toByteArray())
                            }
                        } catch (_: Exception) {
                        } finally { image.close() }
                    }
                }
                provider.unbindAll()
                provider.bindToLifecycle(owner, if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
            } catch (_: Exception) {}
        }, ContextCompat.getMainExecutor(ctx))
    })

    DisposableEffect(Unit) {
        onDispose {
            try { ProcessCameraProvider.getInstance(ctx).get().unbindAll() } catch (_: Exception) {}
            executor.shutdown()
        }
    }
}
