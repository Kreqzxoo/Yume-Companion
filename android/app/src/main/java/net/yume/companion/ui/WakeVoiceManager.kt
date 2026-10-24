package net.yume.companion.ui

import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import androidx.compose.ui.window.DialogProperties
import kotlinx.coroutines.launch
import net.yume.companion.voice.WakeVoice
import java.io.File

/**
 * The answers to the wake word: per sentence several recordings made by the PC (best quality, checked by speech recognition) - listen,
 * choose, delete, export, import your own audio files, ask for more takes.
 */
@Composable
fun WakeVoiceManager(onDismiss: () -> Unit) {
    val ctx = LocalContext.current
    val scope = rememberCoroutineScope()
    @Suppress("UNUSED_VARIABLE") val v = WakeVoice.version            // re-read the lists whenever something changed
    val phrases = remember(v) { WakeVoice.phrases() }
    var message by remember { mutableStateOf("") }
    var importFor by remember { mutableStateOf("") }
    var exportFile by remember { mutableStateOf<File?>(null) }
    var confirmClear by remember { mutableStateOf(false) }

    val importer = rememberLauncherForActivityResult(ActivityResultContracts.OpenMultipleDocuments()) { uris ->
        val n = uris.count { WakeVoice.importFrom(importFor, it) }
        message = if (n > 0) "$n Datei${if (n == 1) "" else "en"} importiert." else if (uris.isNotEmpty()) "Die Datei konnte nicht gelesen werden (nur Audio, bis 8 MB)." else ""
    }
    val exporter = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/wav")) { uri ->
        val f = exportFile
        if (uri != null && f != null) message = if (WakeVoice.exportTo(f, uri)) "Gespeichert." else "Speichern fehlgeschlagen."
    }
    val exportAll = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { tree ->
        if (tree != null) message = "${WakeVoice.exportAllTo(tree)} Aufnahmen exportiert."
    }

    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text("Antworten auf das Wake Word", fontSize = 20.sp, modifier = Modifier.weight(1f))
                    IconButton(onClick = onDismiss) { Icon(Icons.Filled.Close, "Schließen") }
                }
                Text("Die Sätze entstehen am PC mit der Stimme des Charakters (in bester Qualität, jede aufgenommene Fassung wird per Spracherkennung geprüft). Beim Wake Word spielt Yume zufällig einen Satz in der Aufnahme, die du hier wählst.",
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(8.dp))
                if (WakeVoice.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                val line = if (message.isNotEmpty()) message else WakeVoice.status
                if (line.isNotEmpty()) Text(line, fontSize = 12.sp, color = Violet, modifier = Modifier.padding(vertical = 4.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { exportAll.launch(null) }) { Icon(Icons.Filled.SaveAlt, null); Spacer(Modifier.width(6.dp)); Text("Alle exportieren") }
                    TextButton(onClick = { confirmClear = true }) { Text("Alle löschen", color = MaterialTheme.colorScheme.error) }
                }
                Spacer(Modifier.height(6.dp))
                LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(phrases) { text ->
                        val takes = remember(v, text) { WakeVoice.takes(text) }
                        val chosen = remember(v, text) { WakeVoice.selected(text) }
                        Card(colors = CardDefaults.cardColors(containerColor = Panel), shape = RoundedCornerShape(16.dp)) {
                            Column(Modifier.padding(12.dp)) {
                                Text("„$text“", fontSize = 16.sp, color = Pink)
                                if (takes.isEmpty()) Text("Noch keine Aufnahme – es spricht die Handy-Stimme.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                takes.forEachIndexed { i, f ->
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        RadioButton(selected = f == chosen, onClick = { WakeVoice.select(text, f) })
                                        Column(Modifier.weight(1f)) {
                                            Text("Aufnahme ${i + 1}", fontSize = 14.sp)
                                            Text(WakeVoice.describe(f), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                        IconButton(onClick = { WakeVoice.preview(f) }) { Icon(Icons.Filled.PlayArrow, "Anhören", tint = Violet) }
                                        IconButton(onClick = { exportFile = f; exporter.launch("yume_${i + 1}.${f.extension}") }) { Icon(Icons.Filled.SaveAlt, "Speichern") }
                                        IconButton(onClick = { WakeVoice.delete(text, f) }) { Icon(Icons.Filled.Delete, "Löschen") }
                                    }
                                }
                                Spacer(Modifier.height(4.dp))
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    OutlinedButton(enabled = !WakeVoice.busy, onClick = { scope.launch { message = ""; WakeVoice.generate(text, 5) } }, contentPadding = PaddingValues(horizontal = 10.dp)) { Text("5 neue", fontSize = 12.sp) }
                                    OutlinedButton(enabled = !WakeVoice.busy, onClick = { scope.launch { message = ""; WakeVoice.generate(text, 10) } }, contentPadding = PaddingValues(horizontal = 10.dp)) { Text("10 neue", fontSize = 12.sp) }
                                    OutlinedButton(onClick = { importFor = text; importer.launch(arrayOf("audio/*")) }, contentPadding = PaddingValues(horizontal = 10.dp)) { Icon(Icons.Filled.FileUpload, null, Modifier.size(16.dp)); Spacer(Modifier.width(4.dp)); Text("Importieren", fontSize = 12.sp) }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    if (confirmClear) AlertDialog(
        onDismissRequest = { confirmClear = false },
        title = { Text("Alle Aufnahmen löschen?") },
        text = { Text("Die Aufnahmen aller Sätze für diesen Charakter werden vom Handy gelöscht. Danach holt die App für jeden Satz wieder eine neue vom PC.") },
        confirmButton = { TextButton(onClick = { confirmClear = false; WakeVoice.deleteAll(); WakeVoice.sync() }) { Text("Löschen", color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirmClear = false }) { Text("Abbrechen") } },
    )
}
