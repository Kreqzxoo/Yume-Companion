package net.yume.companion

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.os.Bundle
import android.view.WindowManager
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.unit.dp
import androidx.core.content.ContextCompat
import net.yume.companion.core.Host
import net.yume.companion.core.HostLink
import net.yume.companion.core.Link
import net.yume.companion.core.LinkService
import net.yume.companion.core.Prefs
import net.yume.companion.ui.*
import net.yume.companion.voice.CallEngine
import net.yume.companion.voice.CarMode
import net.yume.companion.voice.VoiceService

class MainActivity : ComponentActivity() {
    private var pendingPair by mutableStateOf<String?>(null)
    private var startCall by mutableStateOf(false)

    private val micPermission = registerForActivityResult(ActivityResultContracts.RequestMultiplePermissions()) {
        if (it[Manifest.permission.RECORD_AUDIO] == true) launchPending()
    }
    private var pendingAction: (() -> Unit)? = null
    private fun launchPending() { pendingAction?.invoke(); pendingAction = null }

    fun withMic(action: () -> Unit) {
        if (ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) action()
        else {
            pendingAction = action
            micPermission.launch(arrayOf(Manifest.permission.RECORD_AUDIO, Manifest.permission.POST_NOTIFICATIONS))
        }
    }

    override fun onStart() { super.onStart(); App.uiVisible = true; net.yume.companion.voice.AssistOverlay.hide() }
    override fun onStop() { App.uiVisible = false; super.onStop() }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        handleIntent(intent)
        setContent {
            YumeTheme {
                Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
                    Root(
                        pendingPair = pendingPair, consumePair = { pendingPair = null },
                        startCallFlag = startCall, consumeCall = { startCall = false },
                        withMic = { withMic(it) },
                    )
                }
            }
        }
    }

    override fun onNewIntent(intent: Intent) { super.onNewIntent(intent); handleIntent(intent) }

    override fun onResume() {
        super.onResume()
        LinkService.ensure(this)
        net.yume.companion.voice.WakeVoice.sync()
        // the wake word is switched on but nothing listens yet (app freshly started, phone restarted): start listening as soon as the app is open
        if (Prefs.wakeEnabled && Prefs.paired && !CallEngine.wantCall && net.yume.companion.voice.WakeState.status.value.isEmpty() &&
            ContextCompat.checkSelfPermission(this, Manifest.permission.RECORD_AUDIO) == PackageManager.PERMISSION_GRANTED) {
            try { VoiceService.setWake(this, true) } catch (_: Exception) {}
        }
        if (Prefs.callKeepScreenOn) window.addFlags(WindowManager.LayoutParams.FLAG_KEEP_SCREEN_ON)
    }

    private fun handleIntent(i: Intent?) {
        i ?: return
        i.data?.toString()?.takeIf { it.startsWith("yume://pair") }?.let { pendingPair = it }
        i.data?.takeIf { it.scheme == "yume" && it.host == "spotify" }?.let { net.yume.companion.device.Spotify.finishLogin(it) }
        if (i.getBooleanExtra("start_call", false) || i.action == Intent.ACTION_ASSIST || i.action == Intent.ACTION_VOICE_COMMAND) startCall = true
        if (i.getBooleanExtra("start_wake", false)) withMic { VoiceService.setWake(this, true) }
        if (i.getBooleanExtra("start_car", false)) withMic { VoiceService.startCall(this, car = true) }
        i.removeExtra("start_call"); i.removeExtra("start_wake"); i.removeExtra("start_car")
    }
}

enum class Tab(val label: String) { HOME("Yume"), CALL("Anruf"), OFFLINE("Offline"), SETTINGS("Einstellungen") }

@Composable
fun Root(pendingPair: String?, consumePair: () -> Unit, startCallFlag: Boolean, consumeCall: () -> Unit, withMic: (() -> Unit) -> Unit) {
    val ctx = androidx.compose.ui.platform.LocalContext.current
    var paired by remember { mutableStateOf(Prefs.paired) }
    var tab by remember { mutableStateOf(Tab.HOME) }
    val call by CallEngine.ui.collectAsState()
    // direct choice of the character at every start (unless a default character is set and "always ask" is off)
    var picking by remember { mutableStateOf(Prefs.askCharacterOnStart || Prefs.defaultCharacter.isEmpty()) }
    LaunchedEffect(Unit) {
        if (!picking && Prefs.defaultCharacter.isNotEmpty()) Prefs.character = Prefs.defaultCharacter
    }
    val link by HostLink.state.collectAsState()
    LaunchedEffect(link) {
        // quiet start with the default character: tell the PC once connected
        if (link == Link.CONNECTED && !picking && Prefs.character.isNotEmpty()) {
            kotlinx.coroutines.withContext(kotlinx.coroutines.Dispatchers.IO) {
                val active = Host.getJson("/api/mobile/bootstrap")?.optString("active_character") ?: ""
                if (active != Prefs.character) Host.switchCharacter(Prefs.character)
            }
        }
    }

    LaunchedEffect(paired) { if (paired) LinkService.ensure(ctx) }
    LaunchedEffect(startCallFlag) {
        if (startCallFlag && paired) { consumeCall(); withMic { VoiceService.startCall(ctx, oneShot = true) } }
        else if (startCallFlag) consumeCall()
    }

    if (!paired) {
        PairScreen(pendingLink = pendingPair, consumeLink = consumePair, onPaired = { paired = true })
        return
    }
    if (KioskState.active) {
        KioskScreen(withMic)
        return
    }
    if (call.active && CarMode.active && Prefs.driveDash) {
        DriveScreen(call)
        return
    }
    if (call.active) {
        CallScreen(call, carMode = CarMode.active)
        return
    }
    var pickerSettings by remember { mutableStateOf(false) }
    if (picking) {
        if (pickerSettings) {
            // settings opened from the start screen: a back button returns to the character choice
            Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).statusBarsPadding().navigationBarsPadding()) {
                TextButton(onClick = { pickerSettings = false }) { Icon(Icons.Filled.ArrowBack, null); Spacer(Modifier.width(6.dp)); Text("Zurück zur Auswahl") }
                Box(Modifier.weight(1f).fillMaxWidth()) { SettingsScreen(withMic = withMic, onUnpaired = { paired = false; pickerSettings = false }) }
            }
        } else {
            CharacterPicker(onChosen = { picking = false }, onSettings = { pickerSettings = true })
        }
        return
    }

    // content on top, the menu bar always at the bottom (plain column: nothing can push the bar out of the window)
    val keyboardOpen = WindowInsets.ime.getBottom(androidx.compose.ui.platform.LocalDensity.current) > 0
    Column(Modifier.fillMaxSize().background(MaterialTheme.colorScheme.background).imePadding()) {
        Box(Modifier.weight(1f).fillMaxWidth().statusBarsPadding()) {
            when (tab) {
                Tab.HOME -> ChatScreen(
                    onCall = { withMic { VoiceService.startCall(ctx) } }, onPickCharacter = { picking = true },
                    onOffline = { tab = Tab.OFFLINE }, onSettings = { tab = Tab.SETTINGS },
                )
                Tab.CALL -> CallStartScreen(
                    onCall = { withMic { VoiceService.startCall(ctx) } },
                    onCar = { withMic { VoiceService.startCall(ctx, car = true) } },
                )
                Tab.OFFLINE -> OfflineScreen()
                Tab.SETTINGS -> SettingsScreen(withMic = withMic, onUnpaired = { paired = false })
            }
        }
        if (!keyboardOpen) NavigationBar(containerColor = MaterialTheme.colorScheme.surface) {
            val icons = mapOf(Tab.HOME to Icons.Filled.Face, Tab.CALL to Icons.Filled.Call, Tab.OFFLINE to Icons.Filled.CloudOff, Tab.SETTINGS to Icons.Filled.Settings)
            Tab.values().forEach { t ->
                NavigationBarItem(selected = tab == t, onClick = { tab = t }, icon = { Icon(icons.getValue(t), t.label) }, label = { Text(t.label, maxLines = 1) })
            }
        }
    }
}
