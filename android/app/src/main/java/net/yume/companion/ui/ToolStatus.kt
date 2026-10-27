// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.ui

import net.yume.companion.core.tr

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import net.yume.companion.core.HostLink

/** Live status of what the AI does for you right now ("Öffne Spotify …" -> "✓ Spotify geöffnet"), sent by the PC while a tool runs. */
data class ToolState(val id: String, val tool: String, val state: String, val label: String, val detail: String)

object ToolStatusRepo {
    var current by mutableStateOf<ToolState?>(null)
        private set
    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Main.immediate)
    private var clearJob: Job? = null
    private var started = false

    fun start() {
        if (started) return
        started = true
        scope.launch {
            HostLink.events.collect { j ->
                when (j.optString("type")) {
                    "tool_status" -> {
                        val s = ToolState(j.optString("id"), j.optString("tool"), j.optString("state"), j.optString("label"), j.optString("detail"))
                        clearJob?.cancel()
                        current = s
                        if (s.state != "running") clearJob = scope.launch { delay(if (s.state == "failed") 6000 else 3500); if (current?.id == s.id) current = null }
                    }
                    "message_end" -> { clearJob?.cancel(); clearJob = scope.launch { delay(2500); current = null } }
                }
            }
        }
    }
}

/** One line with a spinner (running), a check mark (done) or a warning (failed); between tools: "denkt nach / schreibt / spricht". */
@Composable
fun ToolStatusLine(modifier: Modifier = Modifier, dark: Boolean = true) {
    val s = ToolStatusRepo.current
    val textColor = if (dark) Color.White else Color(0xFF2A0A1A)
    if (s == null) {
        var speaking by remember { mutableStateOf(false) }
        LaunchedEffect(Unit) { while (true) { speaking = net.yume.companion.voice.AudioPlayer.busy || net.yume.companion.voice.PhoneTts.speaking; delay(300) } }
        val last = net.yume.companion.core.ChatRepo.msgs.lastOrNull()
        val generic = when {
            net.yume.companion.core.ChatRepo.generating && (last == null || last.mine || last.text.isEmpty()) -> tr("denkt nach …", "thinking …")
            net.yume.companion.core.ChatRepo.generating -> tr("schreibt …", "writing …")
            speaking -> tr("spricht …", "speaking …")
            else -> return
        }
        Row(modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp).background(Color(0x991A1226), RoundedCornerShape(14.dp)).padding(horizontal = 12.dp, vertical = 8.dp),
            verticalAlignment = Alignment.CenterVertically) {
            if (generic != tr("spricht …", "speaking …")) CircularProgressIndicator(Modifier.size(14.dp), strokeWidth = 2.dp, color = Pink) else Text("♪", color = Pink, fontSize = 14.sp)
            Spacer(Modifier.width(10.dp))
            Text(generic, color = textColor.copy(alpha = 0.85f), fontSize = 13.sp)
        }
        return
    }
    Row(
        modifier.fillMaxWidth().padding(horizontal = 12.dp, vertical = 4.dp)
            .background(Color(0x991A1226), RoundedCornerShape(14.dp)).padding(horizontal = 12.dp, vertical = 8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        when (s.state) {
            "running" -> CircularProgressIndicator(Modifier.size(14.dp), strokeWidth = 2.dp, color = Pink)
            "done" -> Text("✓", color = Color(0xFF8BE9A8), fontSize = 14.sp)
            else -> Text("⚠", color = Color(0xFFF6C177), fontSize = 14.sp)
        }
        Spacer(Modifier.width(10.dp))
        Column {
            Text(s.label, color = textColor, fontSize = 13.sp)
            if (s.state != "running" && s.detail.isNotBlank()) Text(s.detail, color = textColor.copy(alpha = 0.7f), fontSize = 12.sp)
        }
    }
}
