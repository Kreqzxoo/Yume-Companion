// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.ui

import net.yume.companion.core.tr

import android.annotation.SuppressLint
import android.graphics.Bitmap
import android.graphics.BitmapFactory
import android.webkit.PermissionRequest
import android.webkit.WebChromeClient
import android.webkit.WebView
import android.webkit.WebViewClient
import androidx.compose.animation.core.*
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.res.painterResource
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.viewinterop.AndroidView
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.yume.companion.R
import net.yume.companion.core.*
import net.yume.companion.offline.OfflineChat
import net.yume.companion.offline.OfflineModels
import net.yume.companion.voice.*
import okhttp3.Request

@Composable
fun LinkChip() {
    val link by HostLink.state.collectAsState()
    val where by HostLink.where.collectAsState()
    when (link) {
        Link.CONNECTED -> Chip(if (where == "local") tr("● Heimnetz", "● Home network") else tr("● Extern", "● External"), Ok)
        Link.CONNECTING -> Chip(tr("… verbinde", "… connecting"), Violet)
        Link.OFFLINE -> Chip("○ Offline", Pink)
    }
}

@Composable
fun CallStartScreen(onCall: () -> Unit, onCar: () -> Unit) {
    val link by HostLink.state.collectAsState()
    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(14.dp)) {
        Spacer(Modifier.height(12.dp))
        Avatar(Modifier.size(150.dp), 0f)
        Text(Prefs.character.ifEmpty { "Yume" }, style = MaterialTheme.typography.headlineSmall)
        LinkChip()
        Text(
            if (link == Link.CONNECTED) tr("Freihändiges Gespräch: einfach reden. Du kannst sie jederzeit unterbrechen.", "Hands-free conversation: just talk. You can interrupt her at any time.")
            else if (OfflineModels.installed()) tr("Der PC ist nicht erreichbar – das Gespräch läuft im Offline-Notfallmodus auf dem Handy.", "The PC is not reachable – the conversation runs in offline emergency mode on the phone.")
            else tr("Der PC ist nicht erreichbar. Für Gespräche ohne PC den Offline-Notfallmodus einrichten.", "The PC is not reachable. Set up the offline emergency mode for conversations without a PC."),
            textAlign = TextAlign.Center, color = MaterialTheme.colorScheme.onSurfaceVariant,
        )
        BigButton(tr("Anruf starten", "Start call"), onClick = onCall)
        OutlinedButton(onClick = onCar, modifier = Modifier.fillMaxWidth().heightIn(min = 52.dp)) { Icon(Icons.Filled.DirectionsCar, null); Spacer(Modifier.width(8.dp)); Text(tr("Auto-Modus", "Car mode")) }
        val wake = remember { mutableStateOf(Prefs.wakeEnabled) }
        val state by WakeState.status.collectAsState()
        if (wake.value && state.isNotEmpty()) Text(state, color = Ok, fontSize = 12.sp)
    }
}

@Composable
fun Avatar(modifier: Modifier, level: Float) = AvatarImage(Prefs.character, modifier, true, level)

@Composable
fun CallScreen(call: CallUi, carMode: Boolean) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    val big = carMode && Prefs.carBigUi
    val phaseText = when (call.phase) {
        Phase.LISTENING -> tr("Ich höre zu …", "I'm listening …"); Phase.HEARING -> "…"; Phase.THINKING -> (ToolStatusRepo.current?.takeIf { it.state == "running" }?.label ?: tr("denkt nach …", "thinking …")); Phase.SPEAKING -> tr("spricht – du kannst unterbrechen", "speaking – you can interrupt"); Phase.IDLE -> ""
    }
    val character = Prefs.character
    val chosen = remember(character) { VrmStore.chosen(character) }
    val localVrm = chosen.isNotEmpty() && chosen != VrmStore.NONE && VrmStore.downloaded(chosen)
    var live by remember(chosen) { mutableStateOf(avatarReady(chosen)) }
    val appState = when (call.phase) { Phase.LISTENING, Phase.HEARING -> "LISTENING"; Phase.THINKING -> "PROCESSING"; else -> "STOPPED" }
    val cameraPermission = androidx.activity.compose.rememberLauncherForActivityResult(androidx.activity.result.contract.ActivityResultContracts.RequestPermission()) { granted ->
        net.yume.companion.device.VideoCall.enabled = granted
    }
    fun toggleVideo() {
        val v = net.yume.companion.device.VideoCall
        if (v.enabled) { v.enabled = false; return }
        val has = androidx.core.content.ContextCompat.checkSelfPermission(ctx, android.Manifest.permission.CAMERA) == android.content.pm.PackageManager.PERMISSION_GRANTED
        if (has) v.enabled = true else cameraPermission.launch(android.Manifest.permission.CAMERA)
    }
    Box(Modifier.fillMaxSize()) {
        YumeBackground()
        if (net.yume.companion.device.VideoCall.enabled && !call.offline) {
            // your own camera, small in the corner: this is what Yume sees
            net.yume.companion.device.VideoCallPreview(Modifier.align(Alignment.TopEnd).statusBarsPadding().padding(top = 52.dp, end = 14.dp).size(width = 104.dp, height = 144.dp).clip(androidx.compose.foundation.shape.RoundedCornerShape(14.dp)))
        }
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(horizontal = 20.dp).padding(top = 12.dp, bottom = 20.dp),
            horizontalAlignment = Alignment.CenterHorizontally) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
                Chip(if (carMode) tr("Auto-Modus", "Car mode") else tr("Anruf", "Call"), Violet)
                if (call.offline) Chip(tr("Offline-Modus", "Offline mode"), Pink) else LinkChip()
                Text("%d:%02d".format(call.seconds / 60, call.seconds % 60), color = Color.White.copy(alpha = 0.75f))
            }
            // the character: her 3D model (animated, lip sync, emotions) when one is chosen, otherwise the picture
            Box(Modifier.fillMaxWidth().weight(if (localVrm) 1.3f else 0.8f), contentAlignment = Alignment.Center) {
                if (!localVrm || !live) Avatar(Modifier.size(if (big) 240.dp else 180.dp),
                    if (call.phase == Phase.HEARING || call.phase == Phase.LISTENING) call.level else if (call.phase == Phase.SPEAKING) 0.5f else 0f)
                if (localVrm) LocalAvatar(chosen, Modifier.fillMaxSize().alpha(if (live) 1f else 0f), zoom = Prefs.avatarZoom, appState = appState, onReady = { live = it })
            }
            Text(character.ifEmpty { "Yume" }, style = if (big) MaterialTheme.typography.headlineLarge else MaterialTheme.typography.headlineSmall, color = Color.White)
            Text(phaseText, color = Pink, fontSize = if (big) 20.sp else 14.sp)
            Spacer(Modifier.height(10.dp))
            Column(Modifier.weight(0.9f).fillMaxWidth().verticalScroll(rememberScrollState())) {
                if (call.heard.isNotEmpty()) Text(tr("Du: ${call.heard}", "You: ${call.heard}"), color = Color.White.copy(alpha = 0.7f), fontSize = if (big) 20.sp else 15.sp)
                if (call.reply.isNotEmpty()) { Spacer(Modifier.height(8.dp)); Text(call.reply, color = Color.White, fontSize = if (big) 24.sp else 17.sp) }
                if (call.error.isNotEmpty()) { Spacer(Modifier.height(8.dp)); Text(call.error, color = MaterialTheme.colorScheme.error) }
            }
            Spacer(Modifier.height(12.dp))
            if (!call.offline) Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth().padding(bottom = 8.dp)) {
                OutlinedButton(onClick = { toggleVideo() }, modifier = Modifier.weight(1f)) {
                    Icon(if (net.yume.companion.device.VideoCall.enabled) Icons.Filled.Videocam else Icons.Filled.VideocamOff, null); Spacer(Modifier.width(6.dp))
                    Text(if (net.yume.companion.device.VideoCall.enabled) tr("Video aus", "Video off") else tr("Video an", "Video on"))
                }
                if (net.yume.companion.device.VideoCall.enabled) OutlinedButton(onClick = { net.yume.companion.device.VideoCall.front = !net.yume.companion.device.VideoCall.front }, modifier = Modifier.weight(1f)) {
                    Icon(Icons.Filled.Cameraswitch, null); Spacer(Modifier.width(6.dp)); Text(tr("Kamera wechseln", "Switch camera"))
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(12.dp), modifier = Modifier.fillMaxWidth()) {
                OutlinedButton(onClick = {
                    if (call.phase == Phase.SPEAKING || call.phase == Phase.THINKING) { AudioPlayer.stop(); PhoneTts.stop(); Thread { Host.stopGeneration() }.start() }
                }, modifier = Modifier.weight(1f).heightIn(min = if (big) 72.dp else 56.dp)) { Icon(Icons.Filled.Stop, null); Spacer(Modifier.width(6.dp)); Text(tr("Stopp", "Stop")) }
                BigButton(tr("Auflegen", "Hang up"), onClick = { VoiceService.hangup(ctx) }, modifier = Modifier.weight(1f).heightIn(min = if (big) 72.dp else 56.dp), danger = true)
            }
        }
    }
}

@Composable
fun OfflineScreen() {
    val scope = rememberCoroutineScope()
    val link by HostLink.state.collectAsState()
    val dlProgress by OfflineModels.progress.collectAsState()
    val dlActive by OfflineModels.activeId.collectAsState()
    val dlError by OfflineModels.error.collectAsState()
    val fileVersion by OfflineModels.version.collectAsState()
    var pick by remember { mutableIntStateOf(0) }                       // counts up when another model is chosen (redraw)
    val installed = remember(fileVersion, pick) { OfflineModels.installed() }
    val broken = remember(fileVersion, pick) { OfflineModels.broken() }
    var crashText by remember { mutableStateOf(net.yume.companion.CrashLog.last()) }
    var progress by remember { mutableStateOf(-1f) }
    var error by remember { mutableStateOf("") }
    var input by remember { mutableStateOf("") }
    var busy by remember { mutableStateOf(false) }
    val log = remember { mutableStateListOf<Pair<Boolean, String>>() }
    var syncMsg by remember { mutableStateOf("") }
    var langProgress by remember { mutableStateOf(-1f) }
    var langReady by remember { mutableStateOf(VoskStore.installed(Prefs.language)) }
    val model = remember(pick) { OfflineModels.current() }
    val downloadingThis = dlActive == model.id

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 16.dp)) {
        Section(tr("Offline-Notfallmodus", "Offline emergency mode")) {
            Text(tr("Wenn dein PC nicht erreichbar ist, antwortet ein kleines Sprachmodell direkt auf dem Handy (viel einfacher als die PC-KI, aber sie bleibt ansprechbar). Charakter und letzter Chatverlauf werden vom PC synchronisiert, solange er erreichbar ist.", "When your PC is not reachable, a small language model answers directly on the phone (much simpler than the PC AI, but she stays available). Character and the latest chat history are synchronized from the PC as long as it is reachable."), fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            ChoiceRow(tr("Modell", "Model"), OfflineModels.all.map { it.id to it.title }, { Prefs.offlineModel }, { Prefs.offlineModel = it; OfflineChat.unload(); pick++ })
            Row(verticalAlignment = Alignment.CenterVertically) {
                Chip(if (broken) tr("Modell stürzte ab", "Model crashed") else if (installed) tr("Modell geladen", "Model loaded") else tr("Modell fehlt", "Model missing"), if (installed && !broken) Ok else Pink)
                Spacer(Modifier.width(8.dp))
                Chip(if (langReady) tr("Spracherkennung ${Prefs.language} bereit", "Speech recognition ${Prefs.language} ready") else tr("Spracherkennung fehlt", "Speech recognition missing"), if (langReady) Ok else Pink)
            }
            if (dlProgress >= 0f) {
                LinearProgressIndicator(progress = { dlProgress }, Modifier.fillMaxWidth())
                Text(tr("Lädt „${OfflineModels.all.firstOrNull { it.id == dlActive }?.title ?: ""}“ – ${(dlProgress * 100).toInt()} %. Das läuft auch weiter, wenn du diese Seite verlässt.", "Downloading “${OfflineModels.all.firstOrNull { it.id == dlActive }?.title ?: ""}” – ${(dlProgress * 100).toInt()} %. It keeps running even if you leave this page."), fontSize = 12.sp, color = Violet)
            }
            if (langProgress >= 0f) LinearProgressIndicator(progress = { langProgress }, Modifier.fillMaxWidth())
            if (!installed) Button(onClick = { OfflineModels.start(model) }, enabled = dlActive.isEmpty()) {
                Text(if (downloadingThis) tr("Lädt …", "Downloading …") else tr("Modell laden (${model.sizeMb} MB, WLAN empfohlen)", "Download model (${model.sizeMb} MB, Wi-Fi recommended)"))
            }
            if (installed && broken) {
                Text(tr("Dieses Modell ist auf diesem Handy beim Laden abgestürzt (zu wenig Arbeitsspeicher?). Nimm das kleinere Modell – oder lösche und lade dieses neu, falls die Datei kaputt war.", "This model crashed while loading on this phone (not enough memory?). Take the smaller model – or delete and download this one again if the file was broken."), color = MaterialTheme.colorScheme.error, fontSize = 13.sp)
                OutlinedButton(onClick = { OfflineChat.unload(); OfflineModels.delete(model) }, enabled = dlActive.isEmpty()) { Text(tr("Datei löschen (neu laden)", "Delete file (download again)")) }
            }
            if (dlError.isNotEmpty()) Text(dlError, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
            if (crashText.isNotEmpty()) {
                Text(tr("Letzter Absturz:", "Last crash:"), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Text(crashText.take(700), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                TextButton(onClick = { net.yume.companion.CrashLog.clear(); crashText = "" }) { Text(tr("Ausblenden", "Hide")) }
            }
            if (!langReady) Button(onClick = {
                langProgress = 0f; error = ""
                scope.launch { VoskStore.download(Prefs.language) { langProgress = it }.onFailure { error = tr("Download fehlgeschlagen: ${it.message}", "Download failed: ${it.message}") }; langProgress = -1f; langReady = VoskStore.installed(Prefs.language) }
            }, enabled = langProgress < 0f) { Text(tr("Spracherkennung laden (~50 MB)", "Download speech recognition (~50 MB)")) }
            if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
            SwitchRow(tr("Automatisch umschalten", "Switch automatically"), tr("Ist der PC weg, antwortet das Handy im Gespräch selbst", "If the PC is gone, the phone answers by itself in the conversation"), { Prefs.offlineAutoSwitch }, { Prefs.offlineAutoSwitch = it })
            SwitchRow(tr("Offline-Gespräche dem PC erzählen", "Tell the PC about offline conversations"), tr("Sobald der PC wieder da ist, bekommt er eine Kurzfassung (Gesprächsübergabe)", "As soon as the PC is back it gets a short summary (conversation handover)"), { Prefs.offlineHandoverBack }, { Prefs.offlineHandoverBack = it })
            SwitchRow(tr("Beim Verbinden synchronisieren", "Synchronize on connecting"), tr("Charakter + letzte Nachrichten für den Offline-Betrieb holen", "Fetch character + latest messages for offline use"), { Prefs.syncOnConnect }, { Prefs.syncOnConnect = it })
            OutlinedButton(onClick = {
                scope.launch { syncMsg = if (withContext(Dispatchers.IO) { Sync.refresh() }) tr("Synchronisiert.", "Synchronized.") else tr("Synchronisieren nicht möglich (PC nicht erreichbar?).", "Synchronization not possible (PC not reachable?).") }
            }, enabled = link == Link.CONNECTED) { Text(tr("Jetzt synchronisieren", "Synchronize now")) }
            if (syncMsg.isNotEmpty()) Text(syncMsg, color = Violet)
            val pending = OfflineHandover.pending()
            if (pending > 0) Text(tr("$pending Offline-Gespräch(e) warten auf Übergabe an den PC.", "$pending offline conversation(s) waiting to be handed over to the PC."), color = Violet, fontSize = 13.sp)
        }
        Section(tr("Offline-Chat testen", "Test offline chat")) {
            log.forEach { (mine, text) -> Text((if (mine) tr("Du: ", "You: ") else "${Prefs.character.ifEmpty { "Yume" }}: ") + text, color = if (mine) MaterialTheme.colorScheme.onSurfaceVariant else MaterialTheme.colorScheme.onSurface) }
            OutlinedTextField(input, { input = it }, label = { Text(tr("Nachricht", "Message")) }, modifier = Modifier.fillMaxWidth(), enabled = !busy && installed && !broken)
            Button(onClick = {
                val q = input.trim(); if (q.isEmpty()) return@Button
                input = ""; busy = true; log += true to q
                scope.launch {
                    val a = OfflineChat.reply(q); log += false to a; OfflineHandover.record(q, a); busy = false
                }
            }, enabled = !busy && installed && !broken) { Text(if (busy) tr("Denke nach …", "Thinking …") else tr("Senden", "Send")) }
        }
    }
}

@Composable
fun LogList() {
    val entries by AgentLog.entries.collectAsState()
    if (entries.isEmpty()) Text(tr("Noch nichts passiert.", "Nothing has happened yet."), color = MaterialTheme.colorScheme.onSurfaceVariant)
    else entries.take(60).forEach { Text("${it.time}  ${it.text}", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant) }
}
