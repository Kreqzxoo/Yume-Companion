package net.yume.companion.ui

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.grid.GridCells
import androidx.compose.foundation.lazy.grid.LazyVerticalGrid
import androidx.compose.foundation.lazy.grid.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.alpha
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.scale
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import net.yume.companion.core.*
import net.yume.companion.offline.OfflineModels

/** `*actions*` in italics, everything else normal. */
private fun styled(text: String, base: Color): AnnotatedString = buildAnnotatedString {
    var italic = false
    var i = 0
    while (i < text.length) {
        val c = text[i]
        if (c == '*' ) { italic = !italic; i++; continue }
        val start = i
        while (i < text.length && text[i] != '*') i++
        val part = text.substring(start, i)
        if (italic) withStyle(SpanStyle(fontStyle = FontStyle.Italic, color = base.copy(alpha = 0.72f))) { append(part) } else append(part)
    }
}

@Composable
fun ChatScreen(onCall: () -> Unit, onPickCharacter: () -> Unit, onOffline: () -> Unit, onSettings: () -> Unit = {}) {
    val scope = rememberCoroutineScope()
    val link by HostLink.state.collectAsState()
    val detail by HostLink.detail.collectAsState()
    var input by remember { mutableStateOf("") }
    var modelVersion by remember { mutableIntStateOf(0) }
    var zoom by remember { mutableIntStateOf(Prefs.avatarZoom) }
    var showPicker by remember { mutableStateOf(false) }
    var avatarLog by remember { mutableStateOf("") }
    var avatarOpen by remember { mutableStateOf(true) }
    var wolMsg by remember { mutableStateOf("") }
    val listState = rememberLazyListState()
    val imeVisible = WindowInsets.ime.getBottom(androidx.compose.ui.platform.LocalDensity.current) > 0
    val connected = link == Link.CONNECTED
    val base = if (connected) Host.baseUrl else ""
    val character = Prefs.character
    val fs = (15f * Prefs.chatFontPercent / 100f).sp
    // only start the 3D / Live2D view when the PC really has a usable model for this character (otherwise: the picture)
    val avatarMode by produceState("", character, base) {
        value = if (base.isEmpty() || character.isEmpty()) "" else withContext(Dispatchers.IO) {
            Host.getJson("/api/avatar_config/" + java.net.URLEncoder.encode(character, "UTF-8").replace("+", "%20"))?.optString("mode") ?: ""
        }
    }
    // 3D avatar: the VRM model of the PC is downloaded once and then animated on the phone (works without the PC, too)
    val chosen = remember(character, modelVersion) { VrmStore.chosen(character) }
    LaunchedEffect(character, connected, modelVersion) {
        if (connected && character.isNotEmpty()) {
            val picked = VrmStore.chosen(character)
            if (picked.isEmpty()) {
                val current = VrmStore.list(character)?.second.orEmpty()               // the model configured for this character on the PC
                if (current.isNotEmpty() && VrmStore.download(current)) { VrmStore.choose(character, current); modelVersion++ }
            } else if (picked != VrmStore.NONE && !VrmStore.downloaded(picked)) {
                // chosen earlier, but the file is gone (new installation, app data cleared): fetch it again in the background
                if (VrmStore.download(picked)) modelVersion++
            }
        }
    }
    val localVrm = chosen.isNotEmpty() && chosen != VrmStore.NONE && VrmStore.downloaded(chosen)
    val liveHost = !localVrm && avatarMode == "Live2D Model"            // Live2D still comes from the PC's web page
    var avatarLive by remember(character, chosen) { mutableStateOf(avatarReady(chosen)) }
    LaunchedEffect(liveHost) { ChatRepo.nativeVoice = !liveHost }

    LaunchedEffect(Unit) { ChatRepo.start() }
    LaunchedEffect(character, connected) { ChatRepo.load(character) }
    LaunchedEffect(ChatRepo.msgs.size, ChatRepo.msgs.lastOrNull()?.text?.length) {
        if (ChatRepo.msgs.isNotEmpty()) listState.animateScrollToItem(0)   // reversed list: item 0 is the bottom, so the newest message stays in view
    }

    if (showPicker) VrmPickerDialog(character, onDismiss = { showPicker = false }, onChosen = { modelVersion++; showPicker = false })

    Box(Modifier.fillMaxSize()) {
        YumeBackground()
        Column(Modifier.fillMaxSize()) {
            // ---- top bar
            Row(Modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                AvatarImage(character, Modifier.size(38.dp))
                Spacer(Modifier.width(10.dp))
                Column(Modifier.weight(1f)) {
                    Text(character.ifEmpty { "Yume" }, fontWeight = FontWeight.Bold, fontSize = 17.sp, color = Color.White, maxLines = 1)
                    LinkChip()
                }
                IconButton(onClick = { avatarOpen = !avatarOpen }) { Icon(if (avatarOpen) Icons.Filled.ExpandLess else Icons.Filled.Face, "Avatar", tint = Violet) }
                IconButton(onClick = onPickCharacter) { Icon(Icons.Filled.SwitchAccount, "Charakter wechseln", tint = Violet) }
                IconButton(onClick = onCall, enabled = connected || OfflineModels.installed()) { Icon(Icons.Filled.Call, "Anrufen", tint = Pink) }
                IconButton(onClick = onSettings) { Icon(Icons.Filled.Settings, "Einstellungen", tint = Violet) }
            }

            // ---- avatar (3D / Live2D with animations)
            if (Prefs.showAvatar && avatarOpen && !imeVisible) {
                Box(Modifier.fillMaxWidth().weight(Prefs.avatarPercent.coerceIn(20, 70) / 100f), contentAlignment = Alignment.Center) {
                    val staticAlpha by animateFloatAsState(if (avatarLive) 0f else 1f, label = "staticAvatar")
                    // without a 3D / Live2D model the picture still "breathes" a little
                    val breath: Float = if (UiFlags.animations) {
                        val b by androidx.compose.animation.core.rememberInfiniteTransition(label = "breath").animateFloat(
                            1f, 1.025f, androidx.compose.animation.core.infiniteRepeatable(androidx.compose.animation.core.tween(3200, easing = androidx.compose.animation.core.FastOutSlowInEasing),
                                androidx.compose.animation.core.RepeatMode.Reverse), label = "breathScale")
                        b
                    } else 1f
                    if (staticAlpha > 0.01f) AvatarImage(character, Modifier.fillMaxHeight(0.8f).aspectRatio(1f).alpha(staticAlpha).scale(breath))
                    // invisible until the model reports that it is loaded: a web view that failed would otherwise cover the picture with black
                    if (localVrm) LocalAvatar(chosen, Modifier.fillMaxSize().alpha(if (avatarLive) 1f else 0f), zoom = zoom, onReady = { avatarLive = it }, onLog = { avatarLog = it })
                    else if (base.isNotEmpty() && liveHost) AvatarWebView(Modifier.fillMaxSize().alpha(if (avatarLive) 1f else 0f), onReady = { avatarLive = it })
                    if (localVrm) Row(Modifier.align(Alignment.BottomStart).padding(start = 6.dp), verticalAlignment = Alignment.CenterVertically) {
                        FilledTonalIconButton(onClick = { zoom = (zoom - 8).coerceAtLeast(40); Prefs.avatarZoom = zoom }, modifier = Modifier.size(36.dp)) { Icon(Icons.Filled.Remove, "Kleiner") }
                        Spacer(Modifier.width(6.dp))
                        FilledTonalIconButton(onClick = { zoom = (zoom + 8).coerceAtMost(140); Prefs.avatarZoom = zoom }, modifier = Modifier.size(36.dp)) { Icon(Icons.Filled.Add, "Größer") }
                    }
                    TextButton(onClick = { showPicker = true }, modifier = Modifier.align(Alignment.BottomEnd)) {
                        Text(if (localVrm) "3D-Modell ändern" else "3D-Modell wählen …", fontSize = 12.sp, color = Violet)
                    }
                    if (localVrm && !avatarLive && avatarLog.isNotEmpty()) Text("Avatar: " + avatarLog.take(120), fontSize = 10.sp, color = Color(0xFFFF8A8A), modifier = Modifier.align(Alignment.BottomStart).padding(8.dp))
                }
            }

            // ---- chat
            Box(Modifier.fillMaxWidth().weight(if (Prefs.showAvatar && avatarOpen && !imeVisible) (100 - Prefs.avatarPercent.coerceIn(20, 70)) / 100f else 1f)) {
                if (!connected && ChatRepo.msgs.isEmpty()) {
                    Column(Modifier.fillMaxSize().padding(24.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                        Text(if (link == Link.CONNECTING) "Suche deinen PC …" else "Dein PC ist gerade nicht erreichbar", fontWeight = FontWeight.Bold)
                        if (detail.isNotEmpty()) Text(detail, color = MaterialTheme.colorScheme.onSurfaceVariant, textAlign = TextAlign.Center)
                        Spacer(Modifier.height(12.dp))
                        if (Prefs.wolEnabled) BigButton("PC aufwecken (Wake-on-LAN)", onClick = { scope.launch { wolMsg = WakeOnLan.wake() } })
                        if (wolMsg.isNotEmpty()) Text(wolMsg, color = Violet)
                        OutlinedButton(onClick = onOffline, modifier = Modifier.fillMaxWidth()) { Text("Offline-Notfallmodus") }
                        TextButton(onClick = { HostLink.restart() }) { Text("Erneut versuchen") }
                    }
                } else {
                    // reversed: the list is anchored at the bottom, so the keyboard opening / closing needs no scrolling code and cannot make it jump
                    LazyColumn(state = listState, reverseLayout = true, modifier = Modifier.fillMaxSize().padding(horizontal = 10.dp), verticalArrangement = Arrangement.spacedBy(6.dp)) {
                        item { Spacer(Modifier.height(4.dp)) }
                        items(ChatRepo.msgs.size) { i ->
                            val m = ChatRepo.msgs[ChatRepo.msgs.size - 1 - i]
                            Row(Modifier.fillMaxWidth(), horizontalArrangement = if (m.mine) Arrangement.End else Arrangement.Start) {
                                Box(
                                    Modifier.widthIn(max = 320.dp)
                                        .background(if (m.mine) Pink.copy(alpha = 0.88f) else Color(0xCC1A1226), RoundedCornerShape(16.dp))
                                        .padding(horizontal = 12.dp, vertical = 8.dp),
                                ) {
                                    val textColor = if (m.mine) Color(0xFF2A0A1A) else Color(0xFFF1E8F6)
                                    Column(horizontalAlignment = Alignment.End) {
                                        Text(if (m.text.isEmpty() && m.streaming) AnnotatedString("…") else styled(m.text, textColor), color = textColor, fontSize = fs)
                                        if (!(m.text.isEmpty() && m.streaming)) Text(m.clock(), color = textColor.copy(alpha = 0.55f), fontSize = 10.sp)
                                    }
                                }
                            }
                        }
                        item { Spacer(Modifier.height(4.dp)) }
                    }
                }
            }

            ToolStatusLine()

            // ---- input
            Row(Modifier.fillMaxWidth().padding(8.dp), verticalAlignment = Alignment.CenterVertically) {
                OutlinedTextField(
                    value = input, onValueChange = { input = it },
                    placeholder = { Text("Nachricht an ${character.ifEmpty { "Yume" }} …") },
                    modifier = Modifier.weight(1f), maxLines = 4,
                    shape = RoundedCornerShape(24.dp),
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(onSend = { ChatRepo.send(input); input = "" }),
                )
                Spacer(Modifier.width(6.dp))
                if (ChatRepo.generating) {
                    FilledIconButton(onClick = { ChatRepo.stop() }, colors = IconButtonDefaults.filledIconButtonColors(containerColor = Color(0xFFE5484D))) { Icon(Icons.Filled.Stop, "Stopp") }
                } else {
                    FilledIconButton(onClick = { ChatRepo.send(input); input = "" }, enabled = input.isNotBlank(),
                        colors = IconButtonDefaults.filledIconButtonColors(containerColor = Pink, contentColor = Color(0xFF2A0A1A))) { Icon(Icons.Filled.Send, "Senden") }
                }
            }
        }
    }
}

/** "Who do you want to talk to?" – direct choice of the character, with a star for the default. */
@Composable
fun CharacterPicker(onChosen: () -> Unit, onSettings: () -> Unit = {}) {
    val scope = rememberCoroutineScope()
    val link by HostLink.state.collectAsState()
    var chars by remember { mutableStateOf(Prefs.cachedCharacters.split(',').filter { it.isNotBlank() }) }
    var def by remember { mutableStateOf(Prefs.defaultCharacter) }
    var ask by remember { mutableStateOf(Prefs.askCharacterOnStart) }
    val connected = link == Link.CONNECTED

    LaunchedEffect(connected, Host.baseUrl) {
        if (connected) {
            val list = withContext(Dispatchers.IO) { Host.characters() }
            if (list.isNotEmpty()) { chars = list; Prefs.cachedCharacters = list.joinToString(",") }
        }
    }

    fun choose(name: String) {
        Prefs.character = name
        scope.launch(Dispatchers.IO) { if (HostLink.connected) Host.switchCharacter(name) }
        onChosen()
    }

    Box(Modifier.fillMaxSize()) {
        YumeBackground()
        Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(16.dp), horizontalAlignment = Alignment.CenterHorizontally) {
            Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End) {
                TextButton(onClick = onSettings) { Icon(Icons.Filled.Settings, null); Spacer(Modifier.width(6.dp)); Text("Einstellungen") }
            }
            Text("Mit wem möchtest du sprechen?", style = MaterialTheme.typography.headlineSmall, color = Color.White, textAlign = TextAlign.Center)
            Spacer(Modifier.height(6.dp))
            Row(verticalAlignment = Alignment.CenterVertically) { LinkChip() }
            Text("Tippe einen Charakter an. Mit dem Stern legst du den Standard fest.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 13.sp, textAlign = TextAlign.Center)
            Spacer(Modifier.height(12.dp))
            if (chars.isEmpty()) {
                Text(if (link == Link.CONNECTING) "Lade Charaktere …" else "Keine Charaktere – der PC ist nicht erreichbar.", color = Color.White)
                if (Prefs.character.isNotEmpty()) BigButton("Weiter mit ${Prefs.character}", onClick = onChosen)
            }
            LazyVerticalGrid(columns = GridCells.Fixed(2), modifier = Modifier.weight(1f), horizontalArrangement = Arrangement.spacedBy(12.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                items(chars) { name ->
                    Box(Modifier.fillMaxWidth().clip18().background(Color(0xCC1A1226)).clickable { choose(name) }.padding(12.dp)) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally, modifier = Modifier.fillMaxWidth()) {
                            AvatarImage(name, Modifier.size(110.dp))
                            Spacer(Modifier.height(8.dp))
                            Text(name, fontWeight = FontWeight.Bold, maxLines = 1)
                            if (name == Prefs.character) Text("aktuell", color = Violet, fontSize = 12.sp)
                        }
                        IconButton(onClick = { def = if (def == name) "" else name; Prefs.defaultCharacter = def }, modifier = Modifier.align(Alignment.TopEnd).size(36.dp)) {
                            Icon(if (def == name) Icons.Filled.Star else Icons.Filled.StarBorder, "Als Standard festlegen", tint = if (def == name) Color(0xFFFFD166) else Color.White.copy(alpha = 0.7f))
                        }
                    }
                }
            }
            Row(Modifier.fillMaxWidth().padding(top = 8.dp), verticalAlignment = Alignment.CenterVertically) {
                Text("Beim Start immer fragen", Modifier.weight(1f), color = Color.White)
                Switch(checked = ask, onCheckedChange = { ask = it; Prefs.askCharacterOnStart = it })
            }
            if (!ask) Text(if (def.isEmpty()) "Ohne Standard-Charakter wird weiterhin gefragt." else "Beim nächsten Start öffnet direkt $def.", color = MaterialTheme.colorScheme.onSurfaceVariant, fontSize = 12.sp)
        }
    }
}

private fun Modifier.clip18() = this.then(Modifier.clip(RoundedCornerShape(18.dp)))
