// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.device

import android.content.Context
import android.content.Intent
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.graphics.Matrix
import android.os.Bundle
import android.util.Base64
import androidx.activity.ComponentActivity
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageCapture
import androidx.camera.core.ImageCaptureException
import androidx.camera.core.ImageProxy
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.core.content.ContextCompat
import kotlinx.coroutines.CompletableDeferred
import kotlinx.coroutines.withTimeoutOrNull
import net.yume.companion.core.Prefs
import java.io.ByteArrayOutputStream

/** One photo for the AI ("look at what I see"): a short, invisible activity takes the picture and finishes again. */
object CameraCapture {
    @Volatile var result: CompletableDeferred<String?>? = null

    suspend fun capture(ctx: Context, front: Boolean): String? {
        val d = CompletableDeferred<String?>()
        result = d
        ctx.startActivity(Intent(ctx, CaptureActivity::class.java).putExtra("front", front).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK))
        val r = withTimeoutOrNull(15_000) { d.await() }
        result = null
        return r
    }
}

class CaptureActivity : ComponentActivity() {
    private var finished = false

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        val front = intent.getBooleanExtra("front", false)
        val providerFuture = ProcessCameraProvider.getInstance(this)
        providerFuture.addListener({
            try {
                val provider = providerFuture.get()
                val capture = ImageCapture.Builder().setCaptureMode(ImageCapture.CAPTURE_MODE_MINIMIZE_LATENCY).build()
                provider.unbindAll()
                provider.bindToLifecycle(this, if (front) CameraSelector.DEFAULT_FRONT_CAMERA else CameraSelector.DEFAULT_BACK_CAMERA, capture)
                // give auto exposure a moment
                window.decorView.postDelayed({
                    capture.takePicture(ContextCompat.getMainExecutor(this), object : ImageCapture.OnImageCapturedCallback() {
                        override fun onCaptureSuccess(image: ImageProxy) {
                            val b64 = try { encode(image) } catch (_: Exception) { null } finally { image.close() }
                            done(b64)
                        }
                        override fun onError(exception: ImageCaptureException) { done(null) }
                    })
                }, 700)
            } catch (_: Exception) { done(null) }
        }, ContextCompat.getMainExecutor(this))
    }

    private fun encode(image: ImageProxy): String {
        val buf = image.planes[0].buffer
        val bytes = ByteArray(buf.remaining()); buf.get(bytes)
        var bmp = BitmapFactory.decodeByteArray(bytes, 0, bytes.size)
        val rot = image.imageInfo.rotationDegrees
        if (rot != 0) bmp = Bitmap.createBitmap(bmp, 0, 0, bmp.width, bmp.height, Matrix().apply { postRotate(rot.toFloat()) }, true)
        val edge = Prefs.screenshotMaxEdge.coerceIn(480, 2400)
        val scale = minOf(1f, edge / maxOf(bmp.width, bmp.height).toFloat())
        if (scale < 1f) bmp = Bitmap.createScaledBitmap(bmp, (bmp.width * scale).toInt(), (bmp.height * scale).toInt(), true)
        val bos = ByteArrayOutputStream()
        bmp.compress(Bitmap.CompressFormat.JPEG, Prefs.screenshotQuality.coerceIn(30, 95), bos)
        return Base64.encodeToString(bos.toByteArray(), Base64.NO_WRAP)
    }

    private fun done(b64: String?) {
        if (finished) return
        finished = true
        CameraCapture.result?.complete(b64)
        try { ProcessCameraProvider.getInstance(this).get().unbindAll() } catch (_: Exception) {}
        finish()
        overridePendingTransition(0, 0)
    }

    override fun onDestroy() { if (!finished) CameraCapture.result?.complete(null); super.onDestroy() }
}
