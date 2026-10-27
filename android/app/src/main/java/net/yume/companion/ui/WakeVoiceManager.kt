// Copyright (c) 2026 Kreqzxoo. All rights reserved. Proprietary software - see LICENSE in the android folder.
package net.yume.companion.ui

import net.yume.companion.core.tr

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
        message = if (n > 0) tr("$n Datei${if (n == 1) "" else "en"} importiert.", "$n file${if (n == 1) "" else "s"} imported.") else if (uris.isNotEmpty()) tr("Die Datei konnte nicht gelesen werden (nur Audio, bis 8 MB).", "The file could not be read (audio only, up to 8 MB).") else ""
    }
    val exporter = rememberLauncherForActivityResult(ActivityResultContracts.CreateDocument("audio/wav")) { uri ->
        val f = exportFile
        if (uri != null && f != null) message = if (WakeVoice.exportTo(f, uri)) tr("Gespeichert.", "Saved.") else tr("Speichern fehlgeschlagen.", "Saving failed.")
    }
    val exportAll = rememberLauncherForActivityResult(ActivityResultContracts.OpenDocumentTree()) { tree ->
        if (tree != null) message = tr("${WakeVoice.exportAllTo(tree)} Aufnahmen exportiert.", "${WakeVoice.exportAllTo(tree)} recordings exported.")
    }

    Dialog(onDismissRequest = onDismiss, properties = DialogProperties(usePlatformDefaultWidth = false)) {
        Surface(Modifier.fillMaxSize(), color = MaterialTheme.colorScheme.background) {
            Column(Modifier.fillMaxSize().statusBarsPadding().navigationBarsPadding().padding(16.dp)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(tr("Antworten auf das Wake Word", "Answers to the wake word"), fontSize = 20.sp, modifier = Modifier.weight(1f))
                    IconButton(onClick = onDismiss) { Icon(Icons.Filled.Close, tr("Schließen", "Close")) }
                }
                Text(tr("Die Sätze entstehen am PC mit der Stimme des Charakters (in bester Qualität, jede aufgenommene Fassung wird per Spracherkennung geprüft). Beim Wake Word spielt Yume zufällig einen Satz in der Aufnahme, die du hier wählst.", "The phrases are created on the PC with the character's voice (in the best quality, every recorded version is checked by speech recognition). On the wake word Yume plays a random phrase in the recording you choose here."),
                    fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(8.dp))
                if (WakeVoice.busy) LinearProgressIndicator(Modifier.fillMaxWidth())
                val line = if (message.isNotEmpty()) message else WakeVoice.status
                if (line.isNotEmpty()) Text(line, fontSize = 12.sp, color = Violet, modifier = Modifier.padding(vertical = 4.dp))
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(onClick = { exportAll.launch(null) }) { Icon(Icons.Filled.SaveAlt, null); Spacer(Modifier.width(6.dp)); Text(tr("Alle exportieren", "Export all")) }
                    TextButton(onClick = { confirmClear = true }) { Text(tr("Alle löschen", "Delete all"), color = MaterialTheme.colorScheme.error) }
                }
                Spacer(Modifier.height(6.dp))
                LazyColumn(Modifier.weight(1f), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    items(phrases) { text ->
                        val takes = remember(v, text) { WakeVoice.takes(text) }
                        val chosen = remember(v, text) { WakeVoice.selected(text) }
                        Card(colors = CardDefaults.cardColors(containerColor = Panel), shape = RoundedCornerShape(16.dp)) {
                            Column(Modifier.padding(12.dp)) {
                                Text("„$text“", fontSize = 16.sp, color = Pink)
                                if (takes.isEmpty()) Text(tr("Noch keine Aufnahme – es spricht die Handy-Stimme.", "No recording yet – the phone voice speaks."), fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                takes.forEachIndexed { i, f ->
                                    Row(verticalAlignment = Alignment.CenterVertically) {
                                        RadioButton(selected = f == chosen, onClick = { WakeVoice.select(text, f) })
                                        Column(Modifier.weight(1f)) {
                                            Text(tr("Aufnahme ${i + 1}", "Recording ${i + 1}"), fontSize = 14.sp)
                                            Text(WakeVoice.describe(f), fontSize = 11.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                                        }
                                        IconButton(onClick = { WakeVoice.preview(f) }) { Icon(Icons.Filled.PlayArrow, tr("Anhören", "Listen"), tint = Violet) }
                                        IconButton(onClick = { exportFile = f; exporter.launch("yume_${i + 1}.${f.extension}") }) { Icon(Icons.Filled.SaveAlt, "Speichern") }
                                        IconButton(onClick = { WakeVoice.delete(text, f) }) { Icon(Icons.Filled.Delete, tr("Löschen", "Delete")) }
                                    }
                                }
                                Spacer(Modifier.height(4.dp))
                                Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                                    OutlinedButton(enabled = !WakeVoice.busy, onClick = { scope.launch { message = ""; WakeVoice.generate(text, 5) } }, contentPadding = PaddingValues(horizontal = 10.dp)) { Text(tr("5 neue", "5 new"), fontSize = 12.sp) }
                                    OutlinedButton(enabled = !WakeVoice.busy, onClick = { scope.launch { message = ""; WakeVoice.generate(text, 10) } }, contentPadding = PaddingValues(horizontal = 10.dp)) { Text(tr("10 neue", "10 new"), fontSize = 12.sp) }
                                    OutlinedButton(onClick = { importFor = text; importer.launch(arrayOf("audio/*")) }, contentPadding = PaddingValues(horizontal = 10.dp)) { Icon(Icons.Filled.FileUpload, null, Modifier.size(16.dp)); Spacer(Modifier.width(4.dp)); Text(tr("Importieren", "Import"), fontSize = 12.sp) }
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
        title = { Text(tr("Alle Aufnahmen löschen?", "Delete all recordings?")) },
        text = { Text(tr("Die Aufnahmen aller Sätze für diesen Charakter werden vom Handy gelöscht. Danach holt die App für jeden Satz wieder eine neue vom PC.", "The recordings of all phrases for this character are deleted from the phone. Afterwards the app fetches a new one from the PC for every phrase.")) },
        confirmButton = { TextButton(onClick = { confirmClear = false; WakeVoice.deleteAll(); WakeVoice.sync() }) { Text(tr("Löschen", "Delete"), color = MaterialTheme.colorScheme.error) } },
        dismissButton = { TextButton(onClick = { confirmClear = false }) { Text(tr("Abbrechen", "Cancel")) } },
    )
}
