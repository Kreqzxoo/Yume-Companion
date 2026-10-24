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
        Section(tr("App-Sprache", "App language")) {
            ChoiceRow(tr("Sprache der App", "Language of the app"),
                listOf("auto" to tr("Automatisch (wie das Handy)", "Automatic (like the phone)"), "de" to "Deutsch", "en" to "English"),
                { Lang.current }, { Lang.set(it) },
                tr("Betrifft Texte und feste Antworten der App. Die Sprache der Spracherkennung stellst du unten bei „Sprache & Wake Word“ ein.",
                    "Applies to the app's texts and fixed phrases. You set the speech recognition language below under \"Speech & wake word\"."))
        }

        Section(tr("Verbindung", "Connection")) {
            Row(verticalAlignment = Alignment.CenterVertically) { LinkChip(); Spacer(Modifier.width(8.dp)); Text(Prefs.hostName.ifEmpty { "Yume PC" }, fontSize = 13.sp) }
            TextRow(tr("Lokale Adresse (Heimnetz)", "Local address (home network)"), { Prefs.localUrl }, { Prefs.localUrl = it.trim() }, "http://192.168.0.20:8000")
            TextRow(tr("Externe Domain (leer lassen, wenn nicht benötigt)", "External domain (leave empty if not needed)"), { Prefs.externalUrl }, { Prefs.externalUrl = it.trim() }, "https://my-domain.com")
            Text(tr("Die App probiert zuerst die lokale Adresse (direkt im Heimnetz) und nutzt unterwegs automatisch die externe Domain. Jede Domain, die auf den Yume-PC zeigt, funktioniert.",
                "The app tries the local address first (directly in the home network) and automatically uses the external domain on the go. Any domain that points to the Yume PC works."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SwitchRow(tr("Lokal bevorzugen", "Prefer local"), tr("Auch bei Mobilfunk zuerst die lokale Adresse versuchen (z. B. bei VPN)", "Try the local address first even on mobile data (e.g. with a VPN)"), { Prefs.preferLocal }, { Prefs.preferLocal = it })
            SwitchRow(tr("Verbindung im Hintergrund halten", "Keep the connection in the background"), tr("Damit Yume dein Handy auf Zuruf bedienen kann (Dauer-Benachrichtigung)", "So that Yume can operate your phone on request (permanent notification)"), { Prefs.keepConnected }, { Prefs.keepConnected = it; LinkService.ensure(ctx) })
            SwitchRow(tr("Charakter des PCs übernehmen", "Follow the PC's character"), tr("Wechselt der Charakter am PC, wechselt er hier mit", "If the character changes on the PC, it changes here too"), { Prefs.followHostCharacter }, { Prefs.followHostCharacter = it })
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { testMsg = tr("Prüfe …", "Checking …"); HostLink.restart(); scope.launch { kotlinx.coroutines.delay(2500); testMsg = if (HostLink.connected) tr("Verbunden (${HostLink.where.value}).", "Connected (${HostLink.where.value}).") else tr("Nicht erreichbar.", "Not reachable.") } }) { Text(tr("Verbindung testen", "Test connection")) }
                OutlinedButton(onClick = { scope.launch { wolMsg = WakeOnLan.wake() } }, enabled = Prefs.wolEnabled) { Text(tr("PC aufwecken", "Wake PC")) }
            }
            if (testMsg.isNotEmpty()) Text(testMsg, color = Violet)
            if (wolMsg.isNotEmpty()) Text(wolMsg, color = Violet)
            SwitchRow(tr("Wake-on-LAN erlauben", "Allow Wake-on-LAN"), tr("Schickt das Aufwecksignal an die MAC-Adresse deines PCs (nur im Heimnetz)", "Sends the wake signal to your PC's MAC address (home network only)"), { Prefs.wolEnabled }, { Prefs.wolEnabled = it })
            SwitchRow(tr("PC automatisch aufwecken", "Wake PC automatically"), tr("Wenn er nicht erreichbar ist (alle paar Versuche)", "When it is not reachable (every few attempts)"), { Prefs.wolAuto }, { Prefs.wolAuto = it })
            TextRow(tr("MAC-Adresse(n) des PCs", "MAC address(es) of the PC"), { Prefs.macs }, { Prefs.macs = it.trim() }, "AA:BB:CC:DD:EE:FF, ...")
            TextRow(tr("Aufweck-Webhook für unterwegs (optional)", "Wake webhook for on the go (optional)"), { Prefs.wolWebhook }, { Prefs.wolWebhook = it.trim() }, "https://router/…")
            Button(onClick = { confirmNewHost = true }, modifier = Modifier.fillMaxWidth()) { Text(tr("Mit neuem PC / Gerät verbinden", "Connect to a new PC / device")) }
            Text(tr("Zum Beispiel für eine andere Version oder einen zweiten PC: die App wird von diesem PC gelöst und zeigt die Kopplung (QR-Code) neu. Deine Einstellungen bleiben.",
                "For example for another version or a second PC: the app is detached from this PC and shows the pairing (QR code) again. Your settings stay."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedButton(onClick = { confirmUnpair = true }) { Text(tr("Nur Kopplung lösen …", "Only unpair …")) }
        }

        Section(tr("Sprache & Wake Word", "Speech & wake word")) {
            ChoiceRow(tr("Sprache der Erkennung", "Recognition language"), LANGS.entries.map { it.key to it.value }, { Prefs.language }, { Prefs.language = it; modelReady = VoskStore.installed(it) },
                tr("Gilt für Wake Word, Offline-Modus und Spracherkennung am PC", "Applies to the wake word, offline mode and speech recognition on the PC"))
            Row(verticalAlignment = Alignment.CenterVertically) {
                Chip(if (modelReady) tr("Sprachmodell bereit", "Speech model ready") else tr("Sprachmodell fehlt", "Speech model missing"), if (modelReady) Ok else Pink)
                Spacer(Modifier.width(8.dp))
                if (!modelReady) Button(onClick = {
                    modelProgress = 0f; modelError = ""
                    scope.launch { VoskStore.download(Prefs.language) { modelProgress = it }.onFailure { modelError = tr("Download fehlgeschlagen: ${it.message}", "Download failed: ${it.message}") }; modelProgress = -1f; modelReady = VoskStore.installed(Prefs.language) }
                }, enabled = modelProgress < 0f) { Text(tr("Laden (~50 MB)", "Download (~50 MB)")) }
            }
            if (modelProgress >= 0f) LinearProgressIndicator(progress = { modelProgress }, Modifier.fillMaxWidth())
            if (modelError.isNotEmpty()) Text(modelError, color = MaterialTheme.colorScheme.error)
            var wakeLangVer by remember { mutableIntStateOf(0) }
            ChoiceRow(tr("Sprache des Wake Words", "Wake word language"), listOf("" to tr("Wie oben", "Same as above"), "de" to "Deutsch", "en" to "English"), { Prefs.wakeLang }, { Prefs.wakeLang = it; wakeLangVer++ },
                tr("Englische Namen wie „Hey Yume“ erkennt das englische Modell viel besser als das deutsche", "English names like \"Hey Yume\" are recognized much better by the English model than by the German one"))
            var wakeModelReady by remember(tick, wakeLangVer) { mutableStateOf(VoskStore.installed(Prefs.wakeLanguage())) }
            var wakeProgress by remember { mutableStateOf(-1f) }
            if (!wakeModelReady) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Chip(tr("Modell für das Wake Word fehlt", "Wake word model missing"), Pink); Spacer(Modifier.width(8.dp))
                    Button(onClick = {
                        wakeProgress = 0f
                        scope.launch { VoskStore.download(Prefs.wakeLanguage()) { wakeProgress = it }; wakeProgress = -1f; wakeModelReady = VoskStore.installed(Prefs.wakeLanguage()); modelReady = VoskStore.installed(Prefs.language) }
                    }, enabled = wakeProgress < 0f) { Text(tr("Laden (~40–50 MB)", "Download (~40–50 MB)")) }
                }
                if (wakeProgress >= 0f) LinearProgressIndicator(progress = { wakeProgress }, Modifier.fillMaxWidth())
            }
            Row(verticalAlignment = Alignment.CenterVertically) {
                Column(Modifier.weight(1f)) {
                    Text(tr("Wake Word aktiv", "Wake word active"))
                    Text(if (wake && wakeStatus.isNotEmpty()) wakeStatus else tr("Yume lauscht im Hintergrund auf „Yume“ (Mikrofon, offline, ohne Konto)", "Yume listens in the background for \"Yume\" (microphone, offline, no account)"), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                }
                Switch(checked = wake, onCheckedChange = { on ->
                    if (on && !VoskStore.installed(Prefs.wakeLanguage())) { modelError = tr("Bitte zuerst das Sprachmodell für das Wake Word laden.", "Please download the speech model for the wake word first."); return@Switch }
                    wake = on
                    if (on) withMic { VoiceService.setWake(ctx, true) } else VoiceService.setWake(ctx, false)
                })
            }
            TextRow(tr("Wake Words (Komma getrennt)", "Wake words (comma separated)"), { Prefs.wakeWords }, { Prefs.wakeWords = it }, "yume, hey yume")
            SliderRow(tr("Empfindlichkeit", "Sensitivity"), 0f..100f, { Prefs.wakeSensitivity }, { Prefs.wakeSensitivity = it }, "", tr("Höher = reagiert schneller, aber öfter fälschlich", "Higher = reacts faster, but more often by mistake"))
            OutlinedButton(onClick = { withMic { showWakeTest = true } }, enabled = wakeModelReady) { Text(tr("Wake Word testen …", "Test wake word …")) }
            var speakerVer by remember { mutableIntStateOf(0) }
            var spkReady by remember(tick, speakerVer) { mutableStateOf(SpeakerLock.installed()) }
            var spkProgress by remember { mutableStateOf(-1f) }
            var spkNote by remember { mutableStateOf("") }
            var showEnroll by remember { mutableStateOf(false) }
            if (showEnroll) SpeakerEnrollDialog(onDismiss = { showEnroll = false; speakerVer++ })
            key(speakerVer) {
                SwitchRow(tr("Nur auf meine Stimme reagieren", "Only react to my voice"), tr("Wie „Voice Match“ beim Google Assistant: du sprichst dein Wake Word ein paar Mal ein, danach weckt es nur noch deine Stimme (Fernseher, andere Personen werden ignoriert). Läuft komplett auf dem Handy.",
                    "Like \"Voice Match\" of the Google Assistant: you say your wake word a few times, afterwards only your voice wakes her (TV and other people are ignored). Runs completely on the phone."),
                    { Prefs.speakerLock && SpeakerLock.enrolled() != null }, { on ->
                        if (!on) { Prefs.speakerLock = false }
                        else if (!SpeakerLock.installed()) { spkNote = tr("Bitte zuerst das Stimm-Modell laden.", "Please download the voice model first."); speakerVer++ }
                        else if (SpeakerLock.enrolled() == null) { withMic { showEnroll = true } }
                        else Prefs.speakerLock = true
                    })
            }
            if (!spkReady) {
                Button(onClick = {
                    spkProgress = 0f; spkNote = ""
                    scope.launch { VoskStore.download("spk") { spkProgress = it }.onFailure { spkNote = tr("Download fehlgeschlagen: ${it.message}", "Download failed: ${it.message}") }; spkProgress = -1f; spkReady = SpeakerLock.installed() }
                }, enabled = spkProgress < 0f) { Text(tr("Stimm-Modell laden (~13 MB)", "Download voice model (~13 MB)")) }
                if (spkProgress >= 0f) LinearProgressIndicator(progress = { spkProgress }, Modifier.fillMaxWidth())
            } else {
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { withMic { showEnroll = true } }) { Text(if (SpeakerLock.enrolled() == null) tr("Stimme anlernen …", "Teach my voice …") else tr("Neu anlernen …", "Teach again …")) }
                    if (SpeakerLock.enrolled() != null) TextButton(onClick = { SpeakerLock.clear(); speakerVer++ }) { Text(tr("Löschen", "Delete"), color = MaterialTheme.colorScheme.error) }
                }
                if (SpeakerLock.enrolled() != null) SliderRow(tr("Toleranz beim Stimmabgleich", "Tolerance of the voice match"), 20f..80f, { Prefs.speakerStrict }, { Prefs.speakerStrict = it }, "",
                    tr("Niedriger = strenger (nur du), höher = verzeiht Erkältung und Lärm. Im Wake-Word-Test siehst du den Abstand deiner Stimme.", "Lower = stricter (only you), higher = forgives a cold and noise. In the wake word test you see the distance of your voice."))
            }
            if (spkNote.isNotEmpty()) Text(spkNote, color = MaterialTheme.colorScheme.error, fontSize = 12.sp)
            if (spkReady && SpeakerLock.enrolled() != null) {
                var guestVer by remember { mutableIntStateOf(0) }
                var guestName by remember { mutableStateOf("") }
                var enrollGuest by remember { mutableStateOf<String?>(null) }
                enrollGuest?.let { g -> SpeakerEnrollDialog(onDismiss = { enrollGuest = null; guestVer++ }, guestName = g) }
                SwitchRow(tr("Stimmen unterscheiden", "Tell voices apart"), tr("Yume erkennt, wer spricht: du, angelernte Gäste oder Unbekannte. Private Werkzeuge (Mails, Tagebuch, Dateien, Wissen, Kontakte …) bleiben dir vorbehalten; andere Stimmen bekommen nur Smalltalk, Wetter, Musik und Ähnliches. Läuft auf dem Handy, nur der Name der erkannten Stimme geht an den PC.",
                    "Yume recognizes who is speaking: you, taught guests or unknown people. Private tools (mails, diary, files, knowledge, contacts …) stay reserved for you; other voices only get small talk, weather, music and similar. Runs on the phone, only the name of the recognized voice goes to the PC."),
                    { Prefs.voiceId }, { Prefs.voiceId = it })
                key(guestVer) {
                    SpeakerLock.guests().keys.forEach { g ->
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                            Text(tr("Stimme: $g", "Voice: $g"), Modifier.weight(1f))
                            TextButton(onClick = { SpeakerLock.deleteGuest(g); guestVer++ }) { Text(tr("Löschen", "Delete"), color = MaterialTheme.colorScheme.error) }
                        }
                    }
                }
                Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp), verticalAlignment = Alignment.CenterVertically) {
                    OutlinedTextField(value = guestName, onValueChange = { guestName = it.take(20) }, singleLine = true, label = { Text(tr("Name des Gastes", "Name of the guest")) }, modifier = Modifier.weight(1f))
                    OutlinedButton(onClick = { if (guestName.isNotBlank()) withMic { enrollGuest = guestName.trim() } }, enabled = guestName.isNotBlank()) { Text(tr("Anlernen …", "Teach …")) }
                }
            }
            SwitchRow(tr("Signalton beim Erkennen", "Beep on detection"), tr("Nur wenn Yume nicht mit Stimme antwortet", "Only if Yume does not answer with her voice"), { Prefs.wakeBeep }, { Prefs.wakeBeep = it })
            var replyOn by remember { mutableStateOf(Prefs.wakeReplyOn) }
            var replies by remember { mutableStateOf(Prefs.wakeReplies) }
            SwitchRow(tr("Yume antwortet mit Stimme", "Yume answers with her voice"), tr("Statt des Pieptons sagt sie z. B. „Ja, ich höre?“ – mit der Stimme (inkl. RVC), die am PC für den Charakter eingestellt ist. Wird einmal vom PC geladen und liegt dann auf dem Handy.",
                "Instead of the beep she says e.g. \"Yes, I'm listening?\" – with the voice (incl. RVC) set for the character on the PC. It is loaded from the PC once and then stored on the phone."), { replyOn }, { replyOn = it; Prefs.wakeReplyOn = it; if (it) net.yume.companion.voice.WakeVoice.sync() })
            if (replyOn) {
                OutlinedTextField(value = replies, onValueChange = { replies = it; Prefs.wakeReplies = it }, label = { Text(tr("Sätze (einer pro Zeile, zufällig gewählt)", "Phrases (one per line, chosen at random)")) }, minLines = 2, maxLines = 6, modifier = Modifier.fillMaxWidth())
                Text(net.yume.companion.voice.WakeVoice.status.ifEmpty { tr("Mit Aufnahme vom PC: ${net.yume.companion.voice.WakeVoice.downloaded()} von ${net.yume.companion.voice.WakeVoice.phrases().size} Sätzen", "With recording from the PC: ${net.yume.companion.voice.WakeVoice.downloaded()} of ${net.yume.companion.voice.WakeVoice.phrases().size} phrases") }, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    Button(onClick = { showWakeVoices = true }) { Text(tr("Sätze & Aufnahmen …", "Phrases & recordings …")) }
                    OutlinedButton(onClick = { scope.launch { net.yume.companion.voice.WakeVoice.speak() } }) { Text(tr("Testen", "Test")) }
                }
            }
            SwitchRow(tr("Vibration beim Erkennen", "Vibrate on detection"), "", { Prefs.wakeVibrate }, { Prefs.wakeVibrate = it })
            SwitchRow(tr("Assistenten-Fenster beim Erkennen", "Assistant panel on detection"), tr("Durchsichtiges Fenster wie beim Google Assistant, wenn eine andere App oder der Startbildschirm vorne ist (braucht „Über anderen Apps einblenden“ unter Berechtigungen)",
                "Translucent panel like the Google Assistant when another app or the home screen is in front (needs \"Display over other apps\" under permissions)"), { Prefs.wakeOverlay }, { Prefs.wakeOverlay = it })
            SwitchRow(tr("Nur beim Laden lauschen", "Listen only while charging"), tr("Spart Akku", "Saves battery"), { Prefs.wakeOnlyCharging }, { Prefs.wakeOnlyCharging = it })
            SliderRow(tr("Nach Wake Word auflegen nach", "Hang up after wake word after"), 4f..60f, { Prefs.oneShotIdleSec }, { Prefs.oneShotIdleSec = it }, " s", tr("Stille, bis das Kurzgespräch endet", "Silence until the short conversation ends"))
        }

        Section(tr("Gespräch", "Conversation")) {
            ChoiceRow(tr("Unterbrechen", "Interrupt"), listOf("voice" to tr("Durch Sprechen", "By speaking"), "word" to tr("Nur mit Stopp-Wort", "Only with stop word"), "off" to tr("Aus", "Off")), { Prefs.bargeIn }, { Prefs.bargeIn = it },
                tr("Wie du sie unterbrichst, während sie redet", "How you interrupt her while she talks"))
            TextRow(tr("Stopp-Wörter", "Stop words"), { Prefs.bargeWords }, { Prefs.bargeWords = it }, "yume, stop, wait")
            TextRow(tr("Auflege-Wörter", "Hang-up words"), { Prefs.hangupWords }, { Prefs.hangupWords = it }, "hang up, goodbye")
            SliderRow(tr("Mikrofon-Empfindlichkeit", "Microphone sensitivity"), 0f..100f, { Prefs.vadSensitivity }, { Prefs.vadSensitivity = it })
            SliderRow(tr("Lautstärke von Yume", "Yume's volume"), 0f..200f, { Prefs.ttsVolume }, { Prefs.ttsVolume = it }, " %", tr("Über 100 % wird die Stimme verstärkt (kann bei sehr lauten Stellen verzerren)", "Above 100 % the voice is amplified (may distort at very loud parts)"))
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { scope.launch { net.yume.companion.voice.WakeVoice.speak(force = true) } }) { Text(tr("Lautstärke testen", "Test volume")) }
                OutlinedButton(onClick = { withMic { showMicTest = true } }) { Text(tr("Mikrofon testen …", "Test microphone …")) }
            }
            SliderRow(tr("Pause bis zum Satzende", "Pause until end of sentence"), 400f..2000f, { Prefs.silenceMs }, { Prefs.silenceMs = it }, " ms")
            SwitchRow(tr("Echo-Unterdrückung", "Echo suppression"), tr("Verhindert, dass sie sich selbst hört (am besten mit Kopfhörern)", "Prevents her from hearing herself (works best with headphones)"), { Prefs.echoCancel }, { Prefs.echoCancel = it })
            SwitchRow(tr("Lautsprecher", "Speaker"), tr("Aus = Hörmuschel", "Off = earpiece"), { Prefs.speaker }, { Prefs.speaker = it })
            SwitchRow(tr("Bildschirm anlassen im Gespräch", "Keep screen on during conversation"), "", { Prefs.callKeepScreenOn }, { Prefs.callKeepScreenOn = it })
            SliderRow(tr("Sprechtempo (Offline-Stimme)", "Speaking rate (offline voice)"), 60f..160f, { Prefs.phoneTtsRate }, { Prefs.phoneTtsRate = it }, " %")
        }

        Section(tr("Handy-Steuerung durch die KI", "Phone control by the AI")) {
            SwitchRow(tr("Steuerung erlauben", "Allow control"), tr("Hauptschalter für alles unten", "Main switch for everything below"), { Prefs.allowControl }, { Prefs.allowControl = it })
            SwitchRow(tr("Apps öffnen", "Open apps"), "", { Prefs.allowApps }, { Prefs.allowApps = it })
            SwitchRow(tr("Apps bedienen (Bildschirm lesen, tippen, scrollen)", "Operate apps (read screen, type, scroll)"), tr("Braucht die Bedienungshilfe", "Needs the accessibility service"), { Prefs.allowScreen }, { Prefs.allowScreen = it })
            SwitchRow(tr("Anrufe", "Calls"), "", { Prefs.allowCalls }, { Prefs.allowCalls = it })
            SwitchRow(tr("SMS", "SMS"), "", { Prefs.allowSms }, { Prefs.allowSms = it })
            SwitchRow(tr("Kontakte", "Contacts"), "", { Prefs.allowContacts }, { Prefs.allowContacts = it })
            SwitchRow(tr("Kamera", "Camera"), tr("Yume darf ein Foto machen und ansehen", "Yume may take and look at a photo"), { Prefs.allowCamera }, { Prefs.allowCamera = it })
            SwitchRow(tr("Standort", "Location"), "", { Prefs.allowLocation }, { Prefs.allowLocation = it })
            SwitchRow(tr("Benachrichtigungen lesen", "Read notifications"), "", { Prefs.allowNotifications }, { Prefs.allowNotifications = it })
            SwitchRow(tr("Riskante Aktionen bestätigen", "Confirm risky actions"), tr("Anruf, SMS und Text-Eingabe müssen auf dem Handy bestätigt werden", "Calls, SMS and text input must be confirmed on the phone"), { Prefs.confirmRisky }, { Prefs.confirmRisky = it })
            SwitchRow(tr("Geteilte Dateien sofort ansehen", "Look at shared files right away"), tr("Teilen > Yume: Sprachnachrichten, Bilder, PDFs und Texte werden an den PC geschickt, und Yume sagt dir gleich, was drin ist", "Share > Yume: voice messages, pictures, PDFs and texts are sent to the PC, and Yume tells you right away what is in them"), { Prefs.shareAutoAsk }, { Prefs.shareAutoAsk = it })
            Text(tr("Wand- / Tablet-Modus", "Wall / tablet mode"), fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            Text(tr("Dauer-Anzeige mit Uhr, Wetter, Terminen, Listen und dem Charakter (3D-Modell, wenn geladen). Der Bildschirm bleibt an, das Wake Word ist aktiv. Mit dem Handy am Ladegerät als Nachttisch- oder Küchen-Display.",
                "Permanent display with clock, weather, appointments, lists and the character (3D model if loaded). The screen stays on, the wake word is active. With the phone on the charger as a bedside or kitchen display."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            SwitchRow(tr("Nachts abdunkeln", "Dim at night"), tr("Im Nachtzeitfenster (wie Ruhemodus, 22–7 Uhr) wird die Anzeige gedimmt", "In the night window (like quiet mode, 10 pm–7 am) the display is dimmed"), { Prefs.kioskNightDim }, { Prefs.kioskNightDim = it })
            Button(onClick = { KioskState.active = true }) { Text(tr("Wand-/Tablet-Modus starten", "Start wall/tablet mode")) }
            Text(tr("Anrufschutz", "Call protection"), fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            val roleManager = ctx.getSystemService(android.app.role.RoleManager::class.java)
            var roleHeld by remember { mutableStateOf(roleManager?.isRoleHeld(android.app.role.RoleManager.ROLE_CALL_SCREENING) == true) }
            val roleLauncher = androidx.activity.compose.rememberLauncherForActivityResult(androidx.activity.result.contract.ActivityResultContracts.StartActivityForResult()) {
                roleHeld = roleManager?.isRoleHeld(android.app.role.RoleManager.ROLE_CALL_SCREENING) == true
            }
            Text(if (roleHeld) tr("Yume ist als Anrufschutz-App eingetragen.", "Yume is set as the call protection app.") else tr("Damit Yume Anrufe prüfen darf, muss sie in Android als „Anrufer-ID & Spam“-App festgelegt werden.", "For Yume to screen calls, it must be set in Android as the \"Caller ID & spam\" app."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (!roleHeld) Button(onClick = { roleManager?.createRequestRoleIntent(android.app.role.RoleManager.ROLE_CALL_SCREENING)?.let { roleLauncher.launch(it) } }) { Text(tr("Als Anrufschutz-App festlegen", "Set as call protection app")) }
            SwitchRow(tr("Anrufschutz", "Call protection"), tr("Bekannte Kontakte werden durchgestellt; Spam-Vorwahlen blockiert; Unbekannte angesagt", "Known contacts are put through; spam prefixes blocked; unknown callers announced"), { Prefs.callScreenOn }, { Prefs.callScreenOn = it })
            SwitchRow(tr("Anrufer ansagen", "Announce callers"), tr("Yume sagt laut, wer anruft (Name aus den Kontakten oder „Unbekannter Anruf“)", "Yume says out loud who is calling (name from the contacts or \"Unknown call\")"), { Prefs.callAnnounce }, { Prefs.callAnnounce = it })
            SwitchRow(tr("Unbekannte nachts lautlos", "Silence unknown callers at night"), tr("Im Ruhemodus-Zeitfenster klingeln unbekannte Nummern nicht", "In the quiet mode window unknown numbers do not ring"), { Prefs.callSilenceNight }, { Prefs.callSilenceNight = it })
            var blockPrefixes by remember { mutableStateOf(Prefs.callBlockPrefixes) }
            OutlinedTextField(value = blockPrefixes, onValueChange = { blockPrefixes = it; Prefs.callBlockPrefixes = it }, singleLine = true, label = { Text(tr("Blockierte Vorwahlen (Komma getrennt)", "Blocked prefixes (comma separated)")) }, modifier = Modifier.fillMaxWidth())
            Text(tr("Ruhemodus", "Quiet mode"), fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            SwitchRow(tr("Ruhemodus nachts", "Quiet mode at night"), tr("Leisere Stimme, und Yume antwortet kurz und ruhig (z. B. wenn du im Bett liegst)", "Quieter voice, and Yume answers briefly and calmly (e.g. when you are in bed)"), { Prefs.quietOn }, { Prefs.quietOn = it })
            var qFrom by remember { mutableStateOf(Prefs.quietFrom) }
            var qTo by remember { mutableStateOf(Prefs.quietTo) }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedTextField(value = qFrom, onValueChange = { qFrom = it.take(5); Prefs.quietFrom = qFrom }, singleLine = true, label = { Text(tr("von (HH:MM)", "from (HH:MM)")) }, modifier = Modifier.weight(1f))
                OutlinedTextField(value = qTo, onValueChange = { qTo = it.take(5); Prefs.quietTo = qTo }, singleLine = true, label = { Text(tr("bis (HH:MM)", "to (HH:MM)")) }, modifier = Modifier.weight(1f))
            }
            SliderRow(tr("Lautstärke im Ruhemodus", "Volume in quiet mode"), 10f..100f, { Prefs.quietVolume }, { Prefs.quietVolume = it }, " %")
            Text(tr("Automatisierung", "Automation"), fontWeight = androidx.compose.ui.text.font.FontWeight.Bold)
            SwitchRow(tr("Wenn ich nach Hause komme", "When I come home"), tr("Yume führt einen Satz aus, sobald das Handy im Heim-WLAN ist (höchstens alle 30 Minuten)", "Yume carries out one sentence as soon as the phone is on the home Wi-Fi (at most every 30 minutes)"), { Prefs.autoWifiOn }, { Prefs.autoWifiOn = it })
            var ssid by remember { mutableStateOf(Prefs.autoWifiSsid) }
            var sentence by remember { mutableStateOf(Prefs.autoWifiSentence) }
            var autoMsg by remember { mutableStateOf("") }
            OutlinedTextField(value = ssid, onValueChange = { ssid = it; Prefs.autoWifiSsid = it }, singleLine = true, label = { Text(tr("Name deines Heim-WLANs", "Name of your home Wi-Fi")) }, modifier = Modifier.fillMaxWidth())
            TextButton(onClick = {
                val cur = net.yume.companion.device.Automations.currentSsid()
                if (cur.isNotEmpty()) { ssid = cur; Prefs.autoWifiSsid = cur; autoMsg = tr("Übernommen: $cur", "Adopted: $cur") } else autoMsg = tr("Name nicht lesbar: Standort-Berechtigung geben und Standort einschalten.", "Name not readable: grant the location permission and turn location on.")
            }) { Text(tr("Aktuelles WLAN übernehmen", "Adopt current Wi-Fi")) }
            OutlinedTextField(value = sentence, onValueChange = { sentence = it; Prefs.autoWifiSentence = it }, label = { Text(tr("Dieser Satz wird ausgeführt (z. B. „Guten Abend“ oder „Spiel meine Playlist Car“)", "This sentence is carried out (e.g. \"Good evening\" or \"Play my playlist Car\")")) }, modifier = Modifier.fillMaxWidth())
            val autoScope = rememberCoroutineScope()
            TextButton(enabled = sentence.isNotBlank(), onClick = { autoScope.launch { autoMsg = net.yume.companion.device.Automations.run(sentence.trim()) } }) { Text(tr("Jetzt ausprobieren", "Try it now")) }
            if (autoMsg.isNotEmpty()) Text(autoMsg, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            var pinInput by remember { mutableStateOf("") }
            var hasPin by remember { mutableStateOf(Prefs.pinHash.isNotEmpty()) }
            Text(if (hasPin) tr("Sicherheits-PIN ist aktiv: Die Bestätigung riskanter Aktionen verlangt die PIN direkt in der Benachrichtigung.", "Security PIN is active: confirming risky actions asks for the PIN right in the notification.") else tr("Sicherheits-PIN (optional): zusätzlich zur Bestätigung muss eine PIN eingegeben werden.", "Security PIN (optional): in addition to the confirmation a PIN must be entered."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedTextField(value = pinInput, onValueChange = { pinInput = it.filter { c -> c.isDigit() }.take(8) }, singleLine = true,
                label = { Text(if (hasPin) tr("Neue PIN (4–8 Ziffern, ersetzt die alte)", "New PIN (4–8 digits, replaces the old one)") else tr("PIN festlegen (4–8 Ziffern)", "Set PIN (4–8 digits)")) },
                visualTransformation = androidx.compose.ui.text.input.PasswordVisualTransformation(),
                keyboardOptions = androidx.compose.foundation.text.KeyboardOptions(keyboardType = androidx.compose.ui.text.input.KeyboardType.NumberPassword),
                modifier = Modifier.fillMaxWidth())
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(enabled = pinInput.length >= 4, onClick = { Prefs.pinHash = Prefs.hashPin(pinInput); pinInput = ""; hasPin = true }) { Text(tr("PIN speichern", "Save PIN")) }
                if (hasPin) OutlinedButton(onClick = { Prefs.pinHash = ""; hasPin = false }) { Text(tr("PIN entfernen", "Remove PIN")) }
            }
            SwitchRow(tr("Screenshot nach jedem Schritt", "Screenshot after every step"), tr("Die KI sieht, was sie getan hat (Vision-Modell am PC)", "The AI sees what it did (vision model on the PC)"), { Prefs.autoScreenshot }, { Prefs.autoScreenshot = it })
            SliderRow(tr("Screenshot-Qualität", "Screenshot quality"), 30f..95f, { Prefs.screenshotQuality }, { Prefs.screenshotQuality = it }, " %")
            SliderRow(tr("Screenshot-Größe", "Screenshot size"), 480f..2400f, { Prefs.screenshotMaxEdge }, { Prefs.screenshotMaxEdge = it }, " px")
        }

        Section("Spotify") {
            var clientId by remember { mutableStateOf(Prefs.spotifyClientId) }
            Text(tr("Yume kann dann Musik für dich suchen und abspielen, pausieren, überspringen und sagen, was läuft. Die Fernsteuerung braucht Spotify Premium.",
                "Yume can then search and play music for you, pause, skip and say what is playing. Remote control needs Spotify Premium."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedTextField(value = clientId, onValueChange = { clientId = it.trim(); Prefs.spotifyClientId = clientId }, label = { Text(tr("Client-ID deiner Spotify-App", "Client ID of your Spotify app")) }, singleLine = true, modifier = Modifier.fillMaxWidth())
            val uriHandler = androidx.compose.ui.platform.LocalUriHandler.current
            val clipboard = androidx.compose.ui.platform.LocalClipboardManager.current
            Text(tr("Einmalig bei Spotify eine App anlegen (Name frei wählbar) und dort als Redirect-URI eintragen:  ${net.yume.companion.device.Spotify.REDIRECT}", "Create an app at Spotify once (any name) and enter this as the redirect URI:  ${net.yume.companion.device.Spotify.REDIRECT}"), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                OutlinedButton(onClick = { uriHandler.openUri("https://developer.spotify.com/dashboard") }) { Text(tr("Spotify-Entwicklerseite öffnen", "Open Spotify developer page")) }
                TextButton(onClick = { clipboard.setText(androidx.compose.ui.text.AnnotatedString(net.yume.companion.device.Spotify.REDIRECT)) }) { Text(tr("URI kopieren", "Copy URI")) }
            }
            if (net.yume.companion.device.Spotify.connected) {
                Text(tr("✓ Mit Spotify verbunden", "✓ Connected to Spotify"), color = Violet)
                OutlinedButton(onClick = { net.yume.companion.device.Spotify.logout() }) { Text(tr("Trennen", "Disconnect")) }
            } else {
                Button(enabled = clientId.isNotBlank(), onClick = { net.yume.companion.device.Spotify.loginIntent()?.let { ctx.startActivity(it) } }) { Text(tr("Bei Spotify anmelden", "Sign in to Spotify")) }
            }
            if (net.yume.companion.device.Spotify.status.isNotEmpty()) Text(net.yume.companion.device.Spotify.status, fontSize = 12.sp)
        }

        Section(tr("Yume-Wecker", "Yume alarm clock")) {
            var alarms by remember { mutableStateOf(net.yume.companion.device.YumeAlarms.all()) }
            Text(tr("Sag einfach „Yume, weck mich morgen um 8“ – oder stell hier einen. Yume weckt dich dann mit eigenen Worten und fragt, ob du gut geschlafen hast.",
                "Just say \"Yume, wake me tomorrow at 8\" – or set one here. Yume then wakes you with her own words and asks whether you slept well."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (alarms.isEmpty()) Text(tr("Kein Wecker gestellt.", "No alarm set."), fontSize = 13.sp)
            alarms.forEach { al ->
                Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
                    Text(net.yume.companion.device.YumeAlarms.describe(al).substringBefore("  [id"), Modifier.weight(1f), fontSize = 13.sp)
                    TextButton(onClick = { net.yume.companion.device.YumeAlarms.cancel(al.id); alarms = net.yume.companion.device.YumeAlarms.all() }) { Text(tr("Löschen", "Delete")) }
                }
            }
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(onClick = {
                    val now = java.util.Calendar.getInstance()
                    android.app.TimePickerDialog(ctx, { _, h, m ->
                        net.yume.companion.device.YumeAlarms.add(net.yume.companion.device.YumeAlarms.nextTime(h, m), "")
                        alarms = net.yume.companion.device.YumeAlarms.all()
                    }, now.get(java.util.Calendar.HOUR_OF_DAY), now.get(java.util.Calendar.MINUTE), true).show()
                }) { Text(tr("Wecker stellen", "Set alarm")) }
                OutlinedButton(onClick = {
                    net.yume.companion.device.YumeAlarms.add(System.currentTimeMillis() + 30_000, "Test")
                    alarms = net.yume.companion.device.YumeAlarms.all()
                }) { Text(tr("Test in 30 s", "Test in 30 s")) }
            }
        }

        Section(tr("Auto-Modus", "Car mode")) {
            Text(tr("Freihändig, große Bedienelemente, Benachrichtigungen werden vorgelesen.", "Hands-free, large controls, notifications are read aloud."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = { withMic { VoiceService.startCall(ctx, car = true) } }) { Text(tr("Auto-Modus jetzt starten", "Start car mode now")) }
            SwitchRow(tr("Automatisch starten", "Start automatically"), tr("Wenn das Auto-Bluetooth verbindet (Android erlaubt das nur, wenn die App kurz zuvor aktiv war – sonst kommt eine Benachrichtigung)", "When the car's Bluetooth connects (Android only allows this if the app was active shortly before – otherwise a notification appears)"), { Prefs.carAutoStart }, { Prefs.carAutoStart = it })
            TextRow(tr("Bluetooth-Name(n) des Autos", "Bluetooth name(s) of the car"), { Prefs.carBtNames }, { Prefs.carBtNames = it }, tr("z. B. MyCar, BMW", "e.g. MyCar, BMW"))
            SwitchRow(tr("Benachrichtigungen vorlesen", "Read notifications aloud"), "", { Prefs.carReadNotifications }, { Prefs.carReadNotifications = it })
            SwitchRow(tr("Fahr-Dashboard", "Driving dashboard"), tr("Im Auto-Modus: nächster Termin mit Navigations-Knopf, Musiktasten, was Yume hört und sagt. Das ist Yumes eigener Bildschirm auf dem Handy (Handyhalterung) – nicht die Android-Auto-Anzeige im Auto, die Google für freie Assistenten nicht erlaubt.",
                "In car mode: next appointment with a navigation button, music keys, what Yume hears and says. This is Yume's own screen on the phone (phone mount) – not the Android Auto display in the car, which Google does not allow for free assistants."), { Prefs.driveDash }, { Prefs.driveDash = it })
            SwitchRow(tr("Große Oberfläche", "Large interface"), "", { Prefs.carBigUi }, { Prefs.carBigUi = it })
        }

        Section(tr("Berechtigungen", "Permissions")) { PermissionList(ctx, tick, withMic) }

        Section(tr("Als Assistent einrichten", "Set up as assistant")) {
            Text(tr("Ersetzt den Google Assistant: Home-Taste gedrückt halten / Wisch von der Ecke öffnet Yume.", "Replaces the Google Assistant: long-pressing the home button / swiping from the corner opens Yume."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            Button(onClick = { ctx.startActivity(Intent(Settings.ACTION_VOICE_INPUT_SETTINGS).addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }) { Text(tr("Standard-Assistent wählen …", "Choose default assistant …")) }
        }

        Section(tr("Charaktere & Start", "Characters & start")) {
            SwitchRow(tr("Beim Start Charakter wählen", "Choose character at start"), tr("Zeigt die Direktwahl; aus = öffnet direkt den Standard-Charakter", "Shows the quick selection; off = opens the default character directly"), { Prefs.askCharacterOnStart }, { Prefs.askCharacterOnStart = it })
            Text(tr("Standard-Charakter: ", "Default character: ") + Prefs.defaultCharacter.ifEmpty { tr("– (in der Auswahl mit dem Stern festlegen)", "– (set it with the star in the selection)") }, fontSize = 13.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            if (Prefs.defaultCharacter.isNotEmpty()) TextButton(onClick = { Prefs.defaultCharacter = ""; Prefs.askCharacterOnStart = true }) { Text(tr("Standard entfernen", "Remove default")) }
        }

        Section(tr("Hintergrund & Avatar", "Background & avatar")) {
            key(bgVersion) {
                ChoiceRow(tr("Hintergrund", "Background"), listOf("anim" to tr("Animierter Nachthimmel", "Animated night sky"), "host" to tr("Bild vom PC (aktueller Hintergrund)", "Picture from the PC (current background)"), "custom" to tr("Eigenes Bild vom Handy", "Own picture from the phone")), { Prefs.bgMode }, { Prefs.bgMode = it })
            }
            OutlinedButton(onClick = { pickBg.launch("image/*") }) { Text(tr("Eigenes Hintergrundbild wählen …", "Choose own background picture …")) }
            SliderRow(tr("Abdunkeln", "Dim"), 0f..85f, { Prefs.bgDim }, { Prefs.bgDim = it }, " %", tr("Damit Text gut lesbar bleibt", "So that text stays readable"))
            SwitchRow(tr("Schwebende Blütenblätter", "Floating petals"), "", { Prefs.bgParticles }, { Prefs.bgParticles = it })
            SwitchRow(tr("Avatar anzeigen (3D / Live2D)", "Show avatar (3D / Live2D)"), tr("Animiertes Modell des PCs mit Mimik und Idle-Bewegung. Braucht Internet für die Grafik-Bibliotheken.", "Animated model from the PC with facial expressions and idle movement. Needs internet for the graphics libraries."), { Prefs.showAvatar }, { Prefs.showAvatar = it })
            SliderRow(tr("Größe des 3D-Modells im Rahmen", "Size of the 3D model in its frame"), 40f..140f, { Prefs.avatarZoom }, { Prefs.avatarZoom = it }, " %", tr("Kleiner = mehr vom Körper sichtbar (auch im Chat mit + / −)", "Smaller = more of the body visible (also in the chat with + / −)"))
            SliderRow(tr("Höhe des Avatars", "Height of the avatar"), 20f..70f, { Prefs.avatarPercent }, { Prefs.avatarPercent = it }, " %")
            SwitchRow(tr("Körper-Animationen zu Gefühlen", "Body animations for emotions"), tr("Das 3D-Modell spielt zu den Gefühlen aus dem Chat passende Bewegungen ab", "The 3D model plays movements that fit the emotions from the chat"), { Prefs.avatarBodyAnim }, { Prefs.avatarBodyAnim = it })
            OutlinedButton(onClick = { showVrm = true }, enabled = Prefs.character.isNotEmpty()) { Text(tr("3D-Modell für ${Prefs.character.ifEmpty { "…" }} wählen …", "Choose 3D model for ${Prefs.character.ifEmpty { "…" }} …")) }
            SwitchRow(tr("Stimme im Chat", "Voice in chat"), tr("Aus = reiner Text-Chat: der Charakter antwortet nur geschrieben, es wird keine Stimme erzeugt. An = er spricht auch beim Schreiben. Anrufe sprechen immer.", "Off = text-only chat: the character only answers in writing, no voice is generated. On = it also speaks while you type. Calls always speak."), { Prefs.chatVoice }, { Prefs.chatVoice = it })
            SliderRow(tr("Schriftgröße im Chat", "Font size in chat"), 80f..150f, { Prefs.chatFontPercent }, { Prefs.chatFontPercent = it }, " %")
        }

        Section(tr("Darstellung & Sonstiges", "Appearance & other")) {
            SwitchRow(tr("Bildschirm anlassen (Startseite)", "Keep screen on (home page)"), "", { Prefs.keepScreenOnHome }, { Prefs.keepScreenOnHome = it })
            SwitchRow(tr("Vibration bei Bedienung", "Vibration on touch"), "", { Prefs.haptics }, { Prefs.haptics = it })
            SliderRow(tr("Protokoll-Länge", "Log length"), 20f..500f, { Prefs.agentLogMax }, { Prefs.agentLogMax = it })
        }

        Section(tr("Zurücksetzen", "Reset")) {
            Text(tr("Setzt die App auf den Zustand nach der Installation zurück: Kopplung, alle Einstellungen, Wecker, Spotify-Anmeldung und gespeicherte Chats auf dem Handy.",
                "Resets the app to the state after installation: pairing, all settings, alarms, Spotify login and saved chats on the phone."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            OutlinedButton(onClick = { resetModels = false; confirmReset = true }, colors = ButtonDefaults.outlinedButtonColors(contentColor = MaterialTheme.colorScheme.error)) { Text(tr("App zurücksetzen …", "Reset app …")) }
        }

        Section(tr("Protokoll (was Yume am Handy getan hat)", "Log (what Yume did on the phone)")) {
            LogList()
            TextButton(onClick = { AgentLog.clear() }) { Text(tr("Leeren", "Clear")) }
        }
        Text(tr("Yume Companion für Android 1.0", "Yume Companion for Android 1.0"), Modifier.padding(16.dp), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
    }

    if (confirmNewHost) AlertDialog(
        onDismissRequest = { confirmNewHost = false },
        title = { Text(tr("Mit neuem PC verbinden?", "Connect to a new PC?")) },
        text = { Text(tr("Die Verbindung zu diesem PC, seine Adressen und der gewählte Charakter werden gelöscht. Danach koppelst du die App per QR-Code mit dem neuen PC. Deine übrigen Einstellungen (Wake Word, Stimme, Design …) bleiben.",
            "The connection to this PC, its addresses and the chosen character are deleted. Afterwards you pair the app with the new PC via QR code. Your other settings (wake word, voice, design …) stay.")) },
        confirmButton = { TextButton(onClick = { confirmNewHost = false; AppReset.forNewHost(ctx); onUnpaired() }) { Text(tr("Neu verbinden", "Connect anew")) } },
        dismissButton = { TextButton(onClick = { confirmNewHost = false }) { Text(tr("Abbrechen", "Cancel")) } },
    )

    if (confirmReset) AlertDialog(
        onDismissRequest = { confirmReset = false },
        title = { Text(tr("App zurücksetzen?", "Reset app?")) },
        text = {
            Column {
                Text(tr("Alles wird gelöscht und die App startet neu wie frisch installiert. Am PC bleibt das Gerät eingetragen – du kannst es dort unter Android Connector entfernen.",
                    "Everything is deleted and the app restarts like freshly installed. On the PC the device stays registered – you can remove it there under Android Connector."))
                Row(verticalAlignment = Alignment.CenterVertically, modifier = Modifier.padding(top = 8.dp)) {
                    Checkbox(checked = resetModels, onCheckedChange = { resetModels = it })
                    Text(tr("Auch geladene Modelle löschen (3D-Modelle, Sprachmodell, Offline-KI)", "Also delete downloaded models (3D models, speech model, offline AI)"), fontSize = 13.sp)
                }
            }
        },
        confirmButton = { TextButton(onClick = { confirmReset = false; AppReset.everything(ctx, resetModels) }) { Text(tr("Zurücksetzen", "Reset"), color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirmReset = false }) { Text(tr("Abbrechen", "Cancel")) } },
    )

    if (confirmUnpair) AlertDialog(
        onDismissRequest = { confirmUnpair = false },
        title = { Text(tr("Kopplung lösen?", "Unpair?")) },
        text = { Text(tr("Das Handy wird vom PC getrennt. Danach musst du es per QR-Code neu koppeln. (Am PC kannst du den Zugriff zusätzlich entziehen.)",
            "The phone is disconnected from the PC. Afterwards you must pair it again via QR code. (On the PC you can additionally revoke the access.)")) },
        confirmButton = { TextButton(onClick = {
            confirmUnpair = false
            VoiceService.setWake(ctx, false); HostLink.stop(); ctx.stopService(Intent(ctx, LinkService::class.java))
            Host.unpair(); onUnpaired()
        }) { Text(tr("Lösen", "Unpair")) } },
        dismissButton = { TextButton(onClick = { confirmUnpair = false }) { Text(tr("Abbrechen", "Cancel")) } },
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
            if (ok) Chip(tr("erteilt", "granted"), Ok) else TextButton(onClick = { launcher.launch(perm) }) { Text(tr("Erlauben", "Allow")) }
        }
    }
    @Composable fun special(label: String, ok: Boolean, intent: () -> Intent) {
        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically) {
            Text(label, Modifier.weight(1f))
            if (ok) Chip(tr("aktiv", "active"), Ok) else TextButton(onClick = { ctx.startActivity(intent().addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)) }) { Text(tr("Öffnen", "Open")) }
        }
    }
    runtime(tr("Mikrofon", "Microphone"), Manifest.permission.RECORD_AUDIO)
    runtime(tr("Benachrichtigungen", "Notifications"), Manifest.permission.POST_NOTIFICATIONS)
    runtime(tr("Kamera", "Camera"), Manifest.permission.CAMERA)
    runtime(tr("Telefonieren", "Making calls"), Manifest.permission.CALL_PHONE)
    runtime(tr("SMS senden", "Sending SMS"), Manifest.permission.SEND_SMS)
    runtime(tr("Kontakte", "Contacts"), Manifest.permission.READ_CONTACTS)
    runtime(tr("Kalender", "Calendar"), Manifest.permission.READ_CALENDAR)
    runtime(tr("Standort", "Location"), Manifest.permission.ACCESS_FINE_LOCATION)
    runtime(tr("Bluetooth (Auto-Modus)", "Bluetooth (car mode)"), Manifest.permission.BLUETOOTH_CONNECT)
    special(tr("Bedienungshilfe (Apps bedienen, Screenshots)", "Accessibility service (operate apps, screenshots)"), YumeAccessibilityService.active) { Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS) }
    special(tr("Benachrichtigungszugriff", "Notification access"), YumeNotificationListener.active) { Intent(Settings.ACTION_NOTIFICATION_LISTENER_SETTINGS) }
    special(tr("Über anderen Apps einblenden (Apps aus dem Hintergrund starten)", "Display over other apps (start apps from the background)"), Settings.canDrawOverlays(ctx)) {
        Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:${ctx.packageName}"))
    }
    val ignoring = ctx.getSystemService(PowerManager::class.java).isIgnoringBatteryOptimizations(ctx.packageName)
    special(tr("Akku-Optimierung aus (für zuverlässiges Lauschen)", "Battery optimization off (for reliable listening)"), ignoring) {
        Intent(Settings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS, Uri.parse("package:${ctx.packageName}"))
    }
    Text(tr("Die Berechtigungen sind freiwillig – jede Funktion funktioniert nur, wenn du sie hier erlaubst.", "The permissions are voluntary – each function only works if you allow it here."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
}
