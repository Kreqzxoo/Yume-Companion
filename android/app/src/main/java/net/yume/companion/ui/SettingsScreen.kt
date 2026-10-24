package net.yume.companion.ui

import android.Manifest
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.core.content.ContextCompat
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import androidx.compose.ui.platform.LocalLifecycleOwner
import kotlinx.coroutines.launch
import net.yume.companion.core.*
import net.yume.companion.device.YumeAccessibilityService
import net.yume.companion.device.YumeNotificationListener
import net.yume.companion.voice.CarMode
import net.yume.companion.voice.SpeakerLock
import net.yume.companion.voice.VoiceService
import net.yume.companion.voice.VoskStore
import net.yume.companion.voice.WakeState

private val LANGS = mapOf("de" to "Deutsch", "en" to "English", "ru" to "Русский", "fr" to "Français", "es" to "Español", "it" to "Italiano",
    "pl" to "Polski", "nl" to "Nederlands", "tr" to "Türkçe", "ja" to "日本語", "zh" to "中文")

@Composable
fun SettingsScreen(withMic: (() -> Unit) -> Unit, onUnpaired: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    val link by HostLink.state.collectAsState()
    val where by HostLink.where.collectAsState()
    val wakeStatus by WakeState.status.collectAsState()
    var tick by remember { mutableIntStateOf(0) }      // refresh permission state when coming back from system settings
    val owner = LocalLifecycleOwner.current
    DisposableEffect(owner) {
        val o = LifecycleEventObserver { _, e -> if (e == Lifecycle.Event.ON_RESUME) tick++ }
        owner.lifecycle.addObserver(o); onDispose { owner.lifecycle.removeObserver(o) }
    }
    var wake by remember { mutableStateOf(Prefs.wakeEnabled) }
    var modelReady by remember(tick, Prefs.language) { mutableStateOf(VoskStore.installed(Prefs.language)) }
    var modelProgress by remember { mutableStateOf(-1f) }
    var modelError by remember { mutableStateOf("") }
    var testMsg by remember { mutableStateOf("") }
    var wolMsg by remember { mutableStateOf("") }
    var confirmUnpair by remember { mutableStateOf(false) }
    var confirmNewHost by remember { mutableStateOf(false) }
    var showMicTest by remember { mutableStateOf(false) }
    var showWakeVoices by remember { mutableStateOf(false) }
    if (showWakeVoices) WakeVoiceManager(onDismiss = { showWakeVoices = false })
    if (showMicTest) MicTestDialog(onDismiss = { showMicTest = false })
    var showWakeTest by remember { mutableStateOf(false) }
    if (showWakeTest) WakeTestDialog(onDismiss = { showWakeTest = false })
    var confirmReset by remember { mutableStateOf(false) }
    var resetModels by remember { mutableStateOf(false) }
    var bgVersion by remember { mutableIntStateOf(0) }
    var showVrm by remember { mutableStateOf(false) }
    if (showVrm) VrmPickerDialog(Prefs.character, onDismiss = { showVrm = false }, onChosen = { showVrm = false })
    val pickBg = rememberLauncherForActivityResult(ActivityResultContracts.GetContent()) { uri ->
        if (uri != null) {
            try {
                val out = java.io.File(ctx.filesDir, "bg_custom.jpg")
                ctx.contentResolver.openInputStream(uri)?.use { i -> out.outputStream().use { o -> i.copyTo(o) } }
                Prefs.bgCustomPath = out.absolutePath; Prefs.bgMode = "custom"; bgVersion++
            } catch (_: Exception) {}
        }
    }

    Column(Modifier.fillMaxSize().verticalScroll(rememberScrollState()).padding(bottom = 24.dp)) {
        Section("Verbindung") {
            Row(verticalAlignment = Alignment.CenterVertically) { LinkChip(); Spacer(Modifier.width(8.dp)); Text(Prefs.hostName.ifEmpty { "Yume PC" }, fontSize = 13.sp) }
            TextRow("Lokale Adresse (Heimnetz)", { Prefs.localUrl }, { Prefs.localUrl = it.trim() }, "http://192.168.0.20:8000")
            TextRow("Externe Domain (leer lassen, wenn nicht benötigt)", { Prefs.externalUrl }, { Prefs.externalUrl = it.trim() }, "https://meine-domain.de")
            Text("Die App probiert zuerst die lokale Adresse (direkt im Heimnetz) und nutzt unterwegs automatisch die externe Domain. Jede Domain, die auf den Yume-PC zeigt, funktioniert.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SwitchRow("Lokal bevorzugen", "Auch bei Mobilfunk zuerst die lokale Adresse versuchen (z. B. bei VPN)", { Prefs.preferLocal }, { Prefs.preferLocal = it })
            SwitchRow("Verbindung im Hintergrund halten", "Damit Yume dein Handy auf Zuruf bedienen kann (Dauer-Benachrichtigung)", { Prefs.keepConnected }, { Prefs.keepConnected = it; LinkService.ensure(ctx) })
            SwitchRow("Charakter des PCs übernehmen", "Wechselt der Charakter am PC, wechselt er hier mit", { Prefs.followHostCharacter }, { Prefs.followHostCharacter = it })
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { testMsg = "Prüfe …"; HostLink.restart(); scope.launch { kotlinx.coroutines.delay(2500); testMsg = if (HostLink.connected) "Verbunden (${HostLink.where.value})." else "Nicht erreichbar." } }) { Text("Verbindung testen") }
                OutlinedButton(onClick = { scope.launch { wolMsg = WakeOnLan.wake() } }, enabled = Prefs.wolEnabled) { Text("PC aufwecken") }
            }
            if (testMsg.isNotEmpty()) Text(testMsg, color = Violet)
            if (wolMsg.isNotEmpty()) Text(wolMsg, color = Violet)
            SwitchRow("Wake-on-LAN erlauben", "Schickt das Aufwecksignal an die MAC-Adresse deines PCs (nur im Heimnetz)", { Prefs.wolEnabled }, { Prefs.wolEnabled = it })
            SwitchRow("PC automatisch aufwecken", "Wenn er nicht erreichbar ist (alle paar Versuche)", { Prefs.wolAuto }, { Prefs.wolAuto = it })
            TextRow("MAC-Adresse(n) des PCs", { Prefs.macs }, { Prefs.macs = it.trim() }, "AA:BB:CC:DD:EE:FF, ...")
            TextRow("Aufweck-Webhook für unterwegs (optional)", { Prefs.wolWebhook }, { Prefs.wolWebhook = it.trim() }, "https://router/…")
            Button(onClick = { confirmNewHost = true }, modifier = Modifier.fillMaxWidth()) { Text("Mit neuem PC / Gerät verbinden") }
            Text("Zum Beispiel für eine andere Version oder einen zweiten PC: die App wird von diesem PC gelöst und zeigt die Kopplung (QR-Code) neu. Deine Einstellungen bleiben.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedButton(onClick = { confirmUnpair = true }) { Text("Nur Kopplung lösen …") }
        }

        Section("Sprache & Wake Word") {
            ChoiceRow("Sprache der Erkennung", LANGS.entries.map { it.key to it.value }, { Prefs.language }, { Prefs.language = it; modelReady = VoskStore.installed(it) },
                "Gilt für Wake Word, Offline-Modus und Spracherkennung am PC")
            Row(verticalAlignment = Alignment.CenterVertically) {
                Chip(if (modelReady) "Sprachmodell bereit" else "Sprachmodell fehlt", if (modelReady) Ok else Pink)
                Spacer(Modifier.width(8.dp))
                if (!modelReady) Button(onClick = {
                    modelProgress = 0f; modelError = ""
                    scope.launch { VoskStore.download(Prefs.language) { modelProgress = it }.onFailure { modelError = "Download fehlgeschlagen: ${it.message}" }; modelProgress = -1f; modelReady = VoskStore.installed(Prefs.language) }
                }, enabled = modelProgress < 0f) { Text("Laden (~50 MB)") }
            }
            if (modelProgress >= 0f) LinearProgressIndicator(progress = { modelProgress }, Modifier.fillMaxWidth())
            if (modelError.isNotEmpty()) Text(modelError, color = MaterialTheme.colorScheme.error)
            var wakeLangVer by remember { mutableIntStateOf(0) }
            ChoiceRow("Sprache des Wake Words", listOf("" to "Wie oben", "de" to "Deutsch", "en" to "English"), { Prefs.wakeLang }, { Prefs.wakeLang = it; wakeLangVer++ },
                "Englische Namen wie „Hey Yume“ erkennt das englische Modell viel besser als das deutsche")
            var wakeModelReady by remember(tick, wakeLangVer) { mutableStateOf(VoskStore.installed(Prefs.wakeLanguage())) }
            var wakeProgress by remember { mutableStateOf(-1f) }
            if (!wakeModelReady) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Chip("Modell für das Wake Word fehlt", Pink); Spacer(Modifier.width(8.dp))
                    Button(onClick = {
                        wakeProgress = 0f
                        scope.launch { VoskStore.download(Prefs.wakeLanguage()) { wakeProgress = it }; wakeProgress = -1f; wakeModelReady = VoskStore.installed(Prefs.wakeLanguage()); modelReady = VoskStore.installed(Prefs.language) }
                    }, enabled = wakeProgress < 0f) { Text("Laden (~40–50 MB)") }
                }
                if (wakeProgress >= 0f) LinearProgressIndicator(progress = { wakeProgress }, Modifier.fillMaxWidth())
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text("Wake Word aktiv")
                    Text(if (wake && wakeStatus.isNotEmpty()) wakeStatus else "Yume lauscht im Hintergrund auf „Yume“ (Mikrofon, offline, ohne Konto)", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(checked = wake, onCheckedChange = { on ->
                    if (on && !VoskStore.installed(Prefs.wakeLanguage())) { modelError = "Bitte zuerst das Sprachmodell für das Wake Word laden."; return@Switch }
                    wake = on
                    if (on) withMic { VoiceService.setWake(ctx, true) } else VoiceService.setWake(ctx, false)
                })
            }
            TextRow("Wake Words (Komma getrennt)", { Prefs.wakeWords }, { Prefs.wakeWords = it }, "yume, hey yume")
            SliderRow("Empfindlichkeit", 0f..100f, { Prefs.wakeSensitivity }, { Prefs.wakeSensitivity = it }, "", "Höher = reagiert schneller, aber öfter fälschlich")
            OutlinedButton(onClick = { withMic { showWakeTest = true } }, enabled = wakeModelReady) { Text("Wake Word testen …") }
            var speakerVer by remember { mutableIntStateOf(0) }
            var spkReady by remember(tick, speakerVer) { mutableStateOf(SpeakerLock.installed()) }
            var spkProgress by remember { mutableStateOf(-1f) }
            var spkNote by remember { mutableStateOf("") }
            var showEnroll by remember { mutableStateOf(false) }
            if (showEnroll) SpeakerEnrollDialog(onDismiss = { showEnroll = false; speakerVer++ })
            key(speakerVer) {
                SwitchRow("Nur auf meine Stimme reagieren", "Wie „Voice Match“ beim Google Assistant: du sprichst dein Wake Word ein paar Mal ein, danach weckt es nur noch deine Stimme (Fernseher, andere Personen werden ignoriert). Läuft komplett auf dem Handy.",
                    { Prefs.speakerLock && SpeakerLock.enrolled() != null }, { on ->
                        if (!on) { Prefs.speakerLock = false }
                        else if (!SpeakerLock.installed()) { spkNote = "Bitte zuerst das Stimm-Modell laden."; speakerVer++ }
                        else if (SpeakerLock.enrolled() == null) { withMic { showEnroll = true } }
                        else Prefs.speakerLock = true
                    })
            }
            if (!spkReady) {
                Button(onClick = {
                    spkProgress = 0f; spkNote = ""
                    scope.launch { VoskStore.download("spk") { spkProgress = it }.onFailure { spkNote = "Download fehlgeschlagen: ${it.message}" }; spkProgress = -1f; spkReady = SpeakerLock.installed() }
                }, enabled = spkProgress < 0f) { Text("Stimm-Modell laden (~13 MB)") }
                if (spkProgress >= 0f) LinearProgressIndicator(progress = { spkProgress }, Modifier.fillMaxWidth())
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { withMic { showEnroll = true } }) { Text(if (SpeakerLock.enrolled() == null) "Stimme anlernen …" else "Neu anlernen …") }
                    if (SpeakerLock.enrolled() != null) TextButton(onClick = { SpeakerLock.clear(); speakerVer++ }) { Text("Löschen", color = MaterialTheme.colorScheme.error) }
                }
                if (SpeakerLock.enrolled() != null) SliderRow("Toleranz beim Stimmabgleich", 20f..80f, { Prefs.speakerStrict }, { Prefs.speakerStrict = it }, "", "Niedriger = strenger (nur du), höher = verzeiht Erkältung und Lärm. Im Wake-Word-Test siehst du den Abstand deiner Stimme.")
            }
            if (spkNote.isNotEmpty()) Text(spkNote, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
            if (spkReady && SpeakerLock.enrolled() != null) {
                var guestVer by remember { mutableIntStateOf(0) }
                var guestName by remember { mutableStateOf("") }
                var enrollGuest by remember { mutableStateOf<String?>(null) }
                enrollGuest?.let { g -> SpeakerEnrollDialog(onDismiss = { enrollGuest = null; guestVer++ }, guestName = g) }
                SwitchRow("Stimmen unterscheiden", "Yume erkennt, wer spricht: du, angelernte Gäste oder Unbekannte. Private Werkzeuge (Mails, Tagebuch, Dateien, Wissen, Kontakte …) bleiben dir vorbehalten; andere Stimmen bekommen nur Smalltalk, Wetter, Musik und Ähnliches. Läuft auf dem Handy, nur der Name der erkannten Stimme geht an den PC.",
                    { Prefs.voiceId }, { Prefs.voiceId = it })
                key(guestVer) {
                    SpeakerLock.guests().keys.forEach { g ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text("Stimme: $g", Modifier.weight(1f))
                            TextButton(onClick = { SpeakerLock.deleteGuest(g); guestVer++ }) { Text("Löschen", color = MaterialTheme.colorScheme.error) }
                        }
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(value = guestName, onValueChange = { guestName = it.take(20) }, singleLine = true, label = { Text("Name des Gastes") }, modifier = Modifier.weight(1f))
                    OutlinedButton(onClick = { if (guestName.isNotBlank()) withMic { enrollGuest = guestName.trim() } }, enabled = guestName.isNotBlank()) { Text("Anlernen …") }
                }
            }
            SwitchRow("Signalton beim Erkennen", "Nur wenn Yume nicht mit Stimme antwortet", { Prefs.wakeBeep }, { Prefs.wakeBeep = it })
            var replyOn by remember { mutableStateOf(Prefs.wakeReplyOn) }
            var replies by remember { mutableStateOf(Prefs.wakeReplies) }
            SwitchRow("Yume antwortet mit Stimme", "Statt des Pieptons sagt sie z. B. „Ja, ich höre?“ – mit der Stimme (inkl. RVC), die am PC für den Charakter eingestellt ist. Wird einmal vom PC geladen und liegt dann auf dem Handy.", { replyOn }, { replyOn = it; Prefs.wakeReplyOn = it; if (it) net.yume.companion.voice.WakeVoice.sync() })
            if (replyOn) {
                OutlinedTextField(value = replies, onValueChange = { replies = it; Prefs.wakeReplies = it }, label = { Text("Sätze (einer pro Zeile, zufällig gewählt)") }, minLines = 2, maxLines = 6, modifier = Modifier.fillMaxWidth())
                Text(net.yume.companion.voice.WakeVoice.status.ifEmpty { "Mit Aufnahme vom PC: ${net.yume.companion.voice.WakeVoice.downloaded()} von ${net.yume.companion.voice.WakeVoice.phrases().size} Sätzen" }, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { showWakeVoices = true }) { Text("Sätze & Aufnahmen …") }
                    OutlinedButton(onClick = { scope.launch { net.yume.companion.voice.WakeVoice.speak() } }) { Text("Testen") }
                }
            }
            SwitchRow("Vibration beim Erkennen", "", { Prefs.wakeVibrate }, { Prefs.wakeVibrate = it })
            SwitchRow("Assistenten-Fenster beim Erkennen", "Durchsichtiges Fenster wie beim Google Assistant, wenn eine andere App oder der Startbildschirm vorne ist (braucht „Über anderen Apps einblenden“ unter Berechtigungen)", { Prefs.wakeOverlay }, { Prefs.wakeOverlay = it })
            SwitchRow("Nur beim Laden lauschen", "Spart Akku", { Prefs.wakeOnlyCharging }, { Prefs.wakeOnlyCharging = it })
            SliderRow("Nach Wake Word auflegen nach", 4f..60f, { Prefs.oneShotIdleSec }, { Prefs.oneShotIdleSec = it }, " s", "Stille, bis das Kurzgespräch endet")
        }

        Section("Gespräch") {
            ChoiceRow("Unterbrechen", listOf("voice" to "Durch Sprechen", "word" to "Nur mit Stopp-Wort", "off" to "Aus"), { Prefs.bargeIn }, { Prefs.bargeIn = it },
                "Wie du sie unterbrichst, während sie redet")
            TextRow("Stopp-Wörter", { Prefs.bargeWords }, { Prefs.bargeWords = it }, "yume, stopp, halt")
            TextRow("Auflege-Wörter", { Prefs.hangupWords }, { Prefs.hangupWords = it }, "auflegen, tschüss")
            SliderRow("Mikrofon-Empfindlichkeit", 0f..100f, { Prefs.vadSensitivity }, { Prefs.vadSensitivity = it })
            SliderRow("Lautstärke von Yume", 0f..200f, { Prefs.ttsVolume }, { Prefs.ttsVolume = it }, " %", "Über 100 % wird die Stimme verstärkt (kann bei sehr lauten Stellen verzerren)")
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { scope.launch { net.yume.companion.voice.WakeVoice.speak(force = true) } }) { Text("Lautstärke testen") }
                OutlinedButton(onClick = { withMic { showMicTest = true } }) { Text("Mikrofon testen …") }
            }
            SliderRow("Pause bis zum Satzende", 400f..2000f, { Prefs.silenceMs }, { Prefs.silenceMs = it }, " ms")
            SwitchRow("Echo-Unterdrückung", "Verhindert, dass sie sich selbst hört (am besten mit Kopfhörern)", { Prefs.echoCancel }, { Prefs.echoCancel = it })
            SwitchRow("Lautsprecher", "Aus = Hörmuschel", { Prefs.speaker }, { Prefs.speaker = it })
            SwitchRow("Bildschirm anlassen im Gespräch", "", { Prefs.callKeepScreenOn }, { Prefs.callKeepScreenOn = it })
            SliderRow("Sprechtempo (Offline-Stimme)", 60f..160f, { Prefs.phoneTtsRate }, { Prefs.phoneTtsRate = it }, " %")
        }

        Section("Handy-Steuerung durch die KI") {
            SwitchRow("Steuerung erlauben", "Hauptschalter für alles unten", { Prefs.allowControl }, { Prefs.allowControl = it })
            SwitchRow("Apps öffnen", "", { Prefs.allowApps }, { Prefs.allowApps = it })
            SwitchRow("Apps bedienen (Bildschirm lesen, tippen, scrollen)", "Braucht die Bedienungshilfe", { Prefs.allowScreen }, { Prefs.allowScreen = it })
            SwitchRow("Anrufe", "", { Prefs.allowCalls }, { Prefs.allowCalls = it })
            SwitchRow("SMS", "", { Prefs.allowSms }, { Prefs.allowSms = it })
            SwitchRow("Kontakte", "", { Prefs.allowContacts }, { Prefs.allowContacts = it })
            SwitchRow("Kamera", "Yume darf ein Foto machen und ansehen", { Prefs.allowCamera }, { Prefs.allowCamera = it })
            SwitchRow("Standort", "", { Prefs.allowLocation }, { Prefs.allowLocation = it })
            SwitchRow("Benachrichtigungen lesen", "", { Prefs.allowNotifications }, { Prefs.allowNotifications = it })
            SwitchRow("Riskante Aktionen bestätigen", "Anruf, SMS und Text-Eingabe müssen auf dem Handy bestätigt werden", { Prefs.confirmRisky }, { Prefs.confirmRisky = it })
            SwitchRow("Geteilte Dateien sofort ansehen", "Teilen > Yume: Sprachnachrichten, Bilder, PDFs und Texte werden an den PC geschickt, und Yume sagt dir gleich, was drin ist", { Prefs.shareAutoAsk }, { Prefs.shareAutoAsk = it })
            Text("Wand- / Tablet-Modus", fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            Text("Dauer-Anzeige mit Uhr, Wetter, Terminen, Listen und dem Charakter (3D-Modell, wenn geladen). Der Bildschirm bleibt an, das Wake Word ist aktiv. Mit dem Handy am Ladegerät als Nachttisch- oder Küchen-Display.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SwitchRow("Nachts abdunkeln", "Im Nachtzeitfenster (wie Ruhemodus, 22–7 Uhr) wird die Anzeige gedimmt", { Prefs.kioskNightDim }, { Prefs.kioskNightDim = it })
            Button(onClick = { KioskState.active = true }) { Text("Wand-/Tablet-Modus starten") }
            Text("Anrufschutz", fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            val roleManager = ctx.getSystemService(android.app.role.RoleManager::class.java)
            var roleHeld by remember { mutableStateOf(roleManager?.isRoleHeld(android.app.role.RoleManager.ROLE_CALL_SCREENING) == true) }
            val roleLauncher = androidx.activity.compose.rememberLauncherForActivityResult(androidx.activity.result.contract.ActivityResultContracts.StartActivityForResult()) {
                roleHeld = roleManager?.isRoleHeld(android.app.role.RoleManager.ROLE_CALL_SCREENING) == true
            }
            Text(if (roleHeld) "Yume ist als Anrufschutz-App eingetragen." else "Damit Yume Anrufe prüfen darf, muss sie in Android als „Anrufer-ID & Spam“-App festgelegt werden.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (!roleHeld) Button(onClick = { roleManager?.createRequestRoleIntent(android.app.role.RoleManager.ROLE_CALL_SCREENING)?.let { roleLauncher.launch(it) } }) { Text("Als Anrufschutz-App festlegen") }
            SwitchRow("Anrufschutz", "Bekannte Kontakte werden durchgestellt; Spam-Vorwahlen blockiert; Unbekannte angesagt", { Prefs.callScreenOn }, { Prefs.callScreenOn = it })
            SwitchRow("Anrufer ansagen", "Yume sagt laut, wer anruft (Name aus den Kontakten oder „Unbekannter Anruf“)", { Prefs.callAnnounce }, { Prefs.callAnnounce = it })
            SwitchRow("Unbekannte nachts lautlos", "Im Ruhemodus-Zeitfenster klingeln unbekannte Nummern nicht", { Prefs.callSilenceNight }, { Prefs.callSilenceNight = it })
            var blockPrefixes by remember { mutableStateOf(Prefs.callBlockPrefixes) }
            OutlinedTextField(value = blockPrefixes, onValueChange = { blockPrefixes = it; Prefs.callBlockPrefixes = it }, singleLine = true, label = { Text("Blockierte Vorwahlen (Komma getrennt)") }, modifier = Modifier.fillMaxWidth())
            Text("Ruhemodus", fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            SwitchRow("Ruhemodus nachts", "Leisere Stimme, und Yume antwortet kurz und ruhig (z. B. wenn du im Bett liegst)", { Prefs.quietOn }, { Prefs.quietOn = it })
            var qFrom by remember { mutableStateOf(Prefs.quietFrom) }
            var qTo by remember { mutableStateOf(Prefs.quietTo) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = qFrom, onValueChange = { qFrom = it.take(5); Prefs.quietFrom = qFrom }, singleLine = true, label = { Text("von (HH:MM)") }, modifier = Modifier.weight(1f))
                OutlinedTextField(value = qTo, onValueChange = { qTo = it.take(5); Prefs.quietTo = qTo }, singleLine = true, label = { Text("bis (HH:MM)") }, modifier = Modifier.weight(1f))
            }
            SliderRow("Lautstärke im Ruhemodus", 10f..100f, { Prefs.quietVolume }, { Prefs.quietVolume = it }, " %")
            Text("Automatisierung", fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            SwitchRow("Wenn ich nach Hause komme", "Yume führt einen Satz aus, sobald das Handy im Heim-WLAN ist (höchstens alle 30 Minuten)", { Prefs.autoWifiOn }, { Prefs.autoWifiOn = it })
            var ssid by remember { mutableStateOf(Prefs.autoWifiSsid) }
            var sentence by remember { mutableStateOf(Prefs.autoWifiSentence) }
            var autoMsg by remember { mutableStateOf("") }
            OutlinedTextField(value = ssid, onValueChange = { ssid = it; Prefs.autoWifiSsid = it }, singleLine = true, label = { Text("Name deines Heim-WLANs") }, modifier = Modifier.fillMaxWidth())
            TextButton(onClick = {
                val cur = net.yume.companion.device.Automations.currentSsid()
                if (cur.isNotEmpty()) { ssid = cur; Prefs.autoWifiSsid = cur; autoMsg = "Übernommen: $cur" } else autoMsg = "Name nicht lesbar: Standort-Berechtigung geben und Standort einschalten."
            }) { Text("Aktuelles WLAN übernehmen") }
            OutlinedTextField(value = sentence, onValueChange = { sentence = it; Prefs.autoWifiSentence = it }, label = { Text("Dieser Satz wird ausgeführt (z. B. „Guten Abend“ oder „Spiel meine Playlist Car“)") }, modifier = Modifier.fillMaxWidth())
            val autoScope = rememberCoroutineScope()
            TextButton(enabled = sentence.isNotBlank(), onClick = { autoScope.launch { autoMsg = net.yume.companion.device.Automations.run(sentence.trim()) } }) { Text("Jetzt ausprobieren") }
            if (autoMsg.isNotEmpty()) Text(autoMsg, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            var pinInput by remember { mutableStateOf("") }
            var hasPin by remember { mutableStateOf(Prefs.pinHash.isNotEmpty()) }
            Text(if (hasPin) "Sicherheits-PIN ist aktiv: Die Bestätigung riskanter Aktionen verlangt die PIN direkt in der Benachrichtigung." else "Sicherheits-PIN (optional): zusätzlich zur Bestätigung muss eine PIN eingegeben werden.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedTextField(value = pinInput, onValueChange = { pinInput = it.filter { c -> c.isDigit() }.take(8) }, singleLine = true,
                label = { Text(if (hasPin) "Neue PIN (4–8 Ziffern, ersetzt die alte)" else "PIN festlegen (4–8 Ziffern)") },
                visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.NumberPassword),
                modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = pinInput.length >= 4, onClick = { Prefs.pinHash = Prefs.hashPin(pinInput); pinInput = ""; hasPin = true }) { Text("PIN speichern") }
                if (hasPin) OutlinedButton(onClick = { Prefs.pinHash = ""; hasPin = false }) { Text("PIN entfernen") }
            }
            SwitchRow("Screenshot nach jedem Schritt", "Die KI sieht, was sie getan hat (Vision-Modell am PC)", { Prefs.autoScreenshot }, { Prefs.autoScreenshot = it })
            SliderRow("Screenshot-Qualität", 30f..95f, { Prefs.screenshotQuality }, { Prefs.screenshotQuality = it }, " %")
            SliderRow("Screenshot-Größe", 480f..2400f, { Prefs.screenshotMaxEdge }, { Prefs.screenshotMaxEdge = it }, " px")
        }

        Section("Spotify") {
            var clientId by remember { mutableStateOf(Prefs.spotifyClientId) }
            Text("Yume kann dann Musik für dich suchen und abspielen, pausieren, überspringen und sagen, was läuft. Die Fernsteuerung braucht Spotify Premium.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedTextField(value = clientId, onValueChange = { clientId = it.trim(); Prefs.spotifyClientId = clientId }, label = { Text("Client-ID deiner Spotify-App") }, singleLine = true, modifier = Modifier.fillMaxWidth())
            val uriHandler = androidx.compose.ui.platform.LocalUriHandler.current
            val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
            Text("Einmalig bei Spotify eine App anlegen (Name frei wählbar) und dort als Redirect-URI eintragen:  ${net.yume.companion.device.Spotify.REDIRECT}", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { uriHandler.openUri("https://developer.spotify.com/dashboard") }) { Text("Spotify-Entwicklerseite öffnen") }
                TextButton(onClick = { clipboard.setText(androidx.compose.ui.text.AnnotatedString(net.yume.companion.device.Spotify.REDIRECT)) }) { Text("URI kopieren") }
            }
            if (net.yume.companion.device.Spotify.connected) {
                Text("✓ Mit Spotify verbunden", color = Violet)
                OutlinedButton(onClick = { net.yume.companion.device.Spotify.logout() }) { Text("Trennen") }
            } else {
                Button(enabled = clientId.isNotBlank(), onClick = { net.yume.companion.device.Spotify.loginIntent()?.let { ctx.startActivity(it) } }) { Text("Bei Spotify anmelden") }
            }
            if (net.yume.companion.device.Spotify.status.isNotEmpty()) Text(net.yume.companion.device.Spotify.status, fontSize = 12.sp)
        }

        Section("Yume-Wecker") {
            var alarms by remember { mutableStateOf(net.yume.companion.device.YumeAlarms.all()) }
            Text("Sag einfach „Yume, weck mich morgen um 8“ – oder stell hier einen. Yume weckt dich dann mit eigenen Worten und fragt, ob du gut geschlafen hast.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (alarms.isEmpty()) Text("Kein Wecker gestellt.", fontSize = 13.sp)
            alarms.forEach { al ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(net.yume.companion.device.YumeAlarms.describe(al).substringBefore("  [id"), Modifier.weight(1f), fontSize = 13.sp)
                    TextButton(onClick = { net.yume.companion.device.YumeAlarms.cancel(al.id); alarms = net.yume.companion.device.YumeAlarms.all() }) { Text("Löschen") }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    val now = java.util.Calendar.getInstance()
                    android.app.TimePickerDialog(ctx, { _, h, m ->
                        net.yume.companion.device.YumeAlarms.add(net.yume.companion.device.YumeAlarms.nextTime(h, m), "")
                        alarms = net.yume.companion.device.YumeAlarms.all()
                    }, now.get(java.util.Calendar.HOUR_OF_DAY), now.get(java.util.Calendar.MINUTE), true).show()
                }) { Text("Wecker stellen") }
                OutlinedButton(onClick = {
                    net.yume.companion.device.YumeAlarms.add(System.currentTimeMillis() + 30_000, "Test")
                    alarms = net.yume.companion.device.YumeAlarms.all()
                }) { Text("Test in 30 s") }
            }
        }

        Section("Auto-Modus") {
            Text("Freihändig, große Bedienelemente, Benachrichtigungen werden vorgelesen.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = { withMic { VoiceService.startCall(ctx, car = true) } }) { Text("Auto-Modus jetzt starten") }
            SwitchRow("Automatisch starten", "Wenn das Auto-Bluetooth verbindet (Android erlaubt das nur, wenn die App kurz zuvor aktiv war – sonst kommt eine Benachrichtigung)", { Prefs.carAutoStart }, { Prefs.carAutoStart = it })
            TextRow("Bluetooth-Name(n) des Autos", { Prefs.carBtNames }, { Prefs.carBtNames = it }, "z. B. MyCar, BMW")
            SwitchRow("Benachrichtigungen vorlesen", "", { Prefs.carReadNotifications }, { Prefs.carReadNotifications = it })
            SwitchRow("Fahr-Dashboard", "Im Auto-Modus: nächster Termin mit Navigations-Knopf, Musiktasten, was Yume hört und sagt. Das ist Yumes eigener Bildschirm auf dem Handy (Handyhalterung) – nicht die Android-Auto-Anzeige im Auto, die Google für freie Assistenten nicht erlaubt.", { Prefs.driveDash }, { Prefs.driveDash = it })
            SwitchRow("Große Oberfläche", "", { Prefs.carBigUi }, { Prefs.carBigUi = it })
        }

        Section("Berechtigungen") { PermissionList(ctx, tick, withMic) }

        Section("Als Assistent einrichten") {
            Text("Ersetzt den Google Assistant: Home-Taste gedrückt halten / Wisch von der Ecke öffnet Yume.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = { ctx.startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }) { Text("Standard-Assistent wählen …") }
        }

        Section("Charaktere & Start") {
            SwitchRow("Beim Start Charakter wählen", "Zeigt die Direktwahl; aus = öffnet direkt den Standard-Charakter", { Prefs.askCharacterOnStart }, { Prefs.askCharacterOnStart = it })
            Text("Standard-Charakter: " + Prefs.defaultCharacter.ifEmpty { "– (in der Auswahl mit dem Stern festlegen)" }, fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (Prefs.defaultCharacter.isNotEmpty()) TextButton(onClick = { Prefs.defaultCharacter = ""; Prefs.askCharacterOnStart = true }) { Text("Standard entfernen") }
        }

        Section("Hintergrund & Avatar") {
            key(bgVersion) {
                ChoiceRow("Hintergrund", listOf("anim" to "Animierter Nachthimmel", "host" to "Bild vom PC (aktueller Hintergrund)", "custom" to "Eigenes Bild vom Handy"), { Prefs.bgMode }, { Prefs.bgMode = it })
            }
            OutlinedButton(onClick = { pickBg.launch("image/*") }) { Text("Eigenes Hintergrundbild wählen …") }
            SliderRow("Abdunkeln", 0f..85f, { Prefs.bgDim }, { Prefs.bgDim = it }, " %", "Damit Text gut lesbar bleibt")
            SwitchRow("Schwebende Blütenblätter", "", { Prefs.bgParticles }, { Prefs.bgParticles = it })
            SwitchRow("Avatar anzeigen (3D / Live2D)", "Animiertes Modell des PCs mit Mimik und Idle-Bewegung. Braucht Internet für die Grafik-Bibliotheken.", { Prefs.showAvatar }, { Prefs.showAvatar = it })
            SliderRow("Größe des 3D-Modells im Rahmen", 40f..140f, { Prefs.avatarZoom }, { Prefs.avatarZoom = it }, " %", "Kleiner = mehr vom Körper sichtbar (auch im Chat mit + / −)")
            SliderRow("Höhe des Avatars", 20f..70f, { Prefs.avatarPercent }, { Prefs.avatarPercent = it }, " %")
            SwitchRow("Körper-Animationen zu Gefühlen", "Das 3D-Modell spielt zu den Gefühlen aus dem Chat passende Bewegungen ab", { Prefs.avatarBodyAnim }, { Prefs.avatarBodyAnim = it })
            OutlinedButton(onClick = { showVrm = true }, enabled = Prefs.character.isNotEmpty()) { Text("3D-Modell für ${Prefs.character.ifEmpty { "…" }} wählen …") }
            SwitchRow("Stimme im Chat", "Aus = reiner Text-Chat: der Charakter antwortet nur geschrieben, es wird keine Stimme erzeugt. An = er spricht auch beim Schreiben. Anrufe sprechen immer.", { Prefs.chatVoice }, { Prefs.chatVoice = it })
            SliderRow("Schriftgröße im Chat", 80f..150f, { Prefs.chatFontPercent }, { Prefs.chatFontPercent = it }, " %")
        }

        Section("Darstellung & Sonstiges") {
            SwitchRow("Bildschirm anlassen (Startseite)", "", { Prefs.keepScreenOnHome }, { Prefs.keepScreenOnHome = it })
            SwitchRow("Vibration bei Bedienung", "", { Prefs.haptics }, { Prefs.haptics = it })
            SliderRow("Protokoll-Länge", 20f..500f, { Prefs.agentLogMax }, { Prefs.agentLogMax = it })
        }

        Section("Zurücksetzen") {
            Text("Setzt die App auf den Zustand nach der Installation zurück: Kopplung, alle Einstellungen, Wecker, Spotify-Anmeldung und gespeicherte Chats auf dem Handy.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedButton(onClick = { resetModels = false; confirmReset = true }, colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text("App zurücksetzen …") }
        }

        Section("Protokoll (was Yume am Handy getan hat)") {
            LogList()
            TextButton(onClick = { AgentLog.clear() }) { Text("Leeren") }
        }
        Text("Yume Companion für Android 1.0", Modifier.padding(16.dp), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    if (confirmNewHost) AlertDialog(
        onDismissRequest = { confirmNewHost = false },
        title = { Text("Mit neuem PC verbinden?") },
        text = { Text("Die Verbindung zu diesem PC, seine Adressen und der gewählte Charakter werden gelöscht. Danach koppelst du die App per QR-Code mit dem neuen PC. Deine übrigen Einstellungen (Wake Word, Stimme, Design …) bleiben.") },
        confirmButton = { TextButton(onClick = { confirmNewHost = false; AppReset.forNewHost(ctx); onUnpaired() }) { Text("Neu verbinden") } },
        dismissButton = { TextButton(onClick = { confirmNewHost = false }) { Text("Abbrechen") } },
    )

    if (confirmReset) AlertDialog(
        onDismissRequest = { confirmReset = false },
        title = { Text("App zurücksetzen?") },
        text = {
            Column {
                Text("Alles wird gelöscht und die App startet neu wie frisch installiert. Am PC bleibt das Gerät eingetragen – du kannst es dort unter Android Connector entfernen.")
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
                    Checkbox(checked = resetModels, onCheckedChange = { resetModels = it })
                    Text("Auch geladene Modelle löschen (3D-Modelle, Sprachmodell, Offline-KI)", fontSize = 13.sp)
                }
            }
        },
        confirmButton = { TextButton(onClick = { confirmReset = false; AppReset.everything(ctx, resetModels) }) { Text("Zurücksetzen", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirmReset = false }) { Text("Abbrechen") } },
    )

    if (confirmUnpair) AlertDialog(
        onDismissRequest = { confirmUnpair = false },
        title = { Text("Kopplung lösen?") },
        text = { Text("Das Handy wird vom PC getrennt. Danach musst du es per QR-Code neu koppeln. (Am PC kannst du den Zugriff zusätzlich entziehen.)") },
        confirmButton = { TextButton(onClick = {
            confirmUnpair = false
            VoiceService.setWake(ctx, false); HostLink.stop(); ctx.stopService(Intent(ctx, LinkService::class.java))
            Host.unpair(); onUnpaired()
        }) { Text("Lösen") } },
        dismissButton = { TextButton(onClick = { confirmUnpair = false }) { Text("Abbrechen") } },
    )
}

@Composable
private fun PermissionList(ctx: Context, tick: Int, withMic: (() -> Unit) -> Unit) {
    @Suppress("UNUSED_VARIABLE") val t = tick
    var refresh by remember { mutableIntStateOf(0) }
    @Suppress("UNUSED_VARIABLE") val r = refresh
    val launcher = rememberLauncherForActivityResult(ActivityResultContracts.RequestPermission()) { refresh++ }
    fun granted(p: String) = ContextCompat.checkSelfPermission(ctx, p) == PackageManager.PERMISSION_GRANTED

    @Composable fun runtime(label: String, perm: String) {
        val ok = granted(perm)
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(label, Modifier.weight(1f))
            if (ok) Chip("erteilt", Ok) else TextButton(onClick = { launcher.launch(perm) }) { Text("Erlauben") }
        }
    }
    @Composable fun special(label: String, ok: Boolean, intent: () -> Intent) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(label, Modifier.weight(1f))
            if (ok) Chip("aktiv", Ok) else TextButton(onClick = { ctx.startActivity(intent().addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }) { Text("Öffnen") }
        }
    }
    runtime("Mikrofon", Manifest.permission.RECORD_AUDIO)
    runtime("Benachrichtigungen", Manifest.permission.POST_NOTIFICATIONS)
    runtime("Kamera", Manifest.permission.CAMERA)
    runtime("Telefonieren", Manifest.permission.CALL_PHONE)
    runtime("SMS senden", Manifest.permission.SEND_SMS)
    runtime("Kontakte", Manifest.permission.READ_CONTACTS)
    runtime("Kalender", Manifest.permission.READ_CALENDAR)
    runtime("Standort", Manifest.permission.ACCESS_FINE_LOCATION)
    runtime("Bluetooth (Auto-Modus)", Manifest.permission.BLUETOOTH_CONNECT)
    special("Bedienungshilfe (Apps bedienen, Screenshots)", YumeAccessibilityService.active) { Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS) }
    special("Benachrichtigungszugriff", YumeNotificationListener.active) { Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS) }
    special("Über anderen Apps einblenden (Apps aus dem Hintergrund starten)", Settings.canDrawOverlays(ctx)) {
        Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${ctx.packageName}"))
    }
    val ignoring = ctx.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(ctx.packageName)
    special("Akku-Optimierung aus (für zuverlässiges Lauschen)", ignoring) {
        Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${ctx.packageName}"))
    }
    Text("Die Berechtigungen sind freiwillig – jede Funktion funktioniert nur, wenn du sie hier erlaubst.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
}
