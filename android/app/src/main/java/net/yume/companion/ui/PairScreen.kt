// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.ui

import net.yume.companion.core.tr

import android.Manifest
import android.content.pm.PackageManager
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.camera.core.CameraSelector
import androidx.camera.core.ImageAnalysis
import androidx.camera.core.Preview
import androidx.camera.lifecycle.ProcessCameraProvider
import androidx.camera.view.PreviewView
import androidx.compose.foundation.Image
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.ContextCompat
import com.google.mlkit.vision.barcode.BarcodeScanning
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.common.InputImage
import kotlinx.coroutines.launch
import net.yume.companion.R
import net.yume.companion.core.Host
import net.yume.companion.core.PairInfo
import net.yume.companion.core.Prefs
import java.util.UUID
import java.util.concurrent.Executors

@Composable
fun PairScreen(pendingLink: String?, consumeLink: () -> Unit, onPaired: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    var scanning by remember { mutableStateOf(false) }
    var busy by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var manual by remember { mutableStateOf(false) }
    var link by remember { mutableStateOf("") }
    var url by remember { mutableStateOf("") }
    var code by remember { mutableStateOf("") }

    fun doPair(info: PairInfo) {
        if (busy) return
        busy = true; error = ""; scanning = false
        scope.launch {
            val deviceId = Prefs.deviceId.ifEmpty { UUID.randomUUID().toString().replace("-", "").take(16) }
            val r = Host.pair(info, Host.deviceName(), deviceId)
            busy = false
            r.onSuccess { onPaired() }.onFailure { error = it.message ?: tr("Koppeln fehlgeschlagen", "Pairing failed") }
        }
    }

    LaunchedEffect(pendingLink) {
        val l = pendingLink ?: return@LaunchedEffect
        consumeLink()
        Host.parsePairUrl(l)?.let { doPair(it) } ?: run { error = tr("Ungültiger Kopplungs-Link", "Invalid pairing link") }
    }

    val camPermission = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { scanning = it }

    if (scanning) {
        Box(Modifier.fillMaxSize()) {
            QrScanner { text -> Host.parsePairUrl(text)?.let { doPair(it) } ?: run { error = tr("Das ist kein Yume-QR-Code", "This is not a Yume QR code"); scanning = false } }
            OutlinedButton(onClick = { scanning = false }, modifier = Modifier.align(Alignment.TopStart).padding(16.dp)) { Text(tr("Abbrechen", "Cancel")) }
        }
        return
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Spacer(Modifier.height(24.dp))
        Image(painterResource(R.drawable.logo), null, Modifier.size(112.dp))
        Text("Yume Companion", style = MaterialTheme.typography.headlineMedium, color = Pink)
        Text(
            tr("Die App ist nur der Client – die Rechenleistung bleibt auf deinem PC. Öffne am PC „Android Connector“ in den Einstellungen und scanne den QR-Code.", "The app is only the client – the computing power stays on your PC. On the PC open \"Android Connector\" in the settings and scan the QR code."),
            textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        BigButton(if (busy) tr("Verbinde …", "Connecting …") else tr("Mit QR-Code koppeln", "Pair with QR code"), onClick = {
            if (ContextCompat.checkSelfPermission(ctx, Manifest.permission.CAMERA) == PackageManager.PERMISSION_GRANTED) scanning = true
            else camPermission.launch(Manifest.permission.CAMERA)
        })
        TextButton(onClick = { manual = !manual }) { Text(if (manual) tr("Eingabe ausblenden", "Hide input") else tr("Link oder Adresse von Hand eingeben", "Enter link or address manually")) }
        if (manual) {
            OutlinedTextField(link, { link = it }, label = { Text(tr("Kopplungs-Link (yume://pair?…)", "Pairing link (yume://pair?…)")) }, modifier = Modifier.fillMaxWidth())
            BigButton(tr("Mit Link koppeln", "Pair with link"), onClick = { Host.parsePairUrl(link)?.let { doPair(it) } ?: run { error = tr("Ungültiger Link", "Invalid link") } })
            Text(tr("oder", "or"), color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedTextField(url, { url = it }, label = { Text(tr("Adresse des PCs (z. B. 192.168.0.20:8000)", "Address of the PC (e.g. 192.168.0.20:8000)")) }, modifier = Modifier.fillMaxWidth())
            OutlinedTextField(code, { code = it }, label = { Text(tr("Kopplungs-Code", "Pairing code")) }, modifier = Modifier.fillMaxWidth())
            BigButton(tr("Koppeln", "Pair"), onClick = { doPair(PairInfo("", "Yume PC", code.trim(), url.trim(), "", "")) })
        }
        if (busy) CircularProgressIndicator(color = Pink)
        if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error, textAlign = TextAlign.Center)
    }
}

@Composable
fun QrScanner(onCode: (String) -> Unit) {
    val ctx = LocalContext.current
    val owner = LocalLifecycleOwner.current
    val scanner = remember { BarcodeScanning.getClient(com.google.mlkit.vision.barcode.BarcodeScannerOptions.Builder().setBarcodeFormats(Barcode.FORMAT_QR_CODE).build()) }
    val executor = remember { Executors.newSingleThreadExecutor() }
    var done by remember { mutableStateOf(false) }
    AndroidView(modifier = Modifier.fillMaxSize(), factory = { c ->
        val view = PreviewView(c)
        val future = ProcessCameraProvider.getInstance(c)
        future.addListener({
            val provider = future.get()
            val preview = Preview.Builder().build().also { it.setSurfaceProvider(view.surfaceProvider) }
            val analysis = ImageAnalysis.Builder().setBackpressureStrategy(ImageAnalysis.STRATEGY_KEEP_ONLY_LATEST).build()
            analysis.setAnalyzer(executor) { proxy ->
                try {
                    if (!done) {
                        val bmp = proxy.toBitmap()
                        val img = InputImage.fromBitmap(bmp, proxy.imageInfo.rotationDegrees)
                        scanner.process(img).addOnSuccessListener { codes ->
                            codes.firstOrNull { it.rawValue?.startsWith("yume://") == true }?.rawValue?.let { if (!done) { done = true; onCode(it) } }
                        }.addOnCompleteListener { proxy.close() }
                    } else proxy.close()
                } catch (_: Exception) { proxy.close() }
            }
            provider.unbindAll()
            provider.bindToLifecycle(owner, CameraSelector.DEFAULT_BACK_CAMERA, preview, analysis)
        }, ContextCompat.getMainExecutor(c))
        view
    })
    DisposableEffect(Unit) { onDispose { executor.shutdown(); try { ProcessCameraProvider.getInstance(ctx).get().unbindAll() } catch (_: Exception) {} } }
}
