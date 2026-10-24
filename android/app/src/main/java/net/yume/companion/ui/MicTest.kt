package net.yume.companion.ui

import android.media.AudioFormat
import android.media.AudioRecord
import android.media.MediaRecorder
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.withContext
import net.yume.companion.core.Prefs
import net.yume.companion.voice.WakeState
import kotlin.math.sqrt

/**
 * Microphone test: shows live what the speech detection of calls sees. The bar is your voice, the line is the threshold the current
 * sensitivity sets - when the bar crosses the line, a sentence would be recognised. Move the slider and watch.
 */
@Composable
fun MicTestDialog(onDismiss: () -> Unit) {
    var level by remember { mutableFloatStateOf(0f) }
    var threshold by remember { mutableFloatStateOf(0f) }
    var speech by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf("") }
    var sens by remember { mutableFloatStateOf(Prefs.vadSensitivity.toFloat()) }
    val sensNow = remember { floatArrayOf(sens) }
    sensNow[0] = sens

    DisposableEffect(Unit) {
        WakeState.micBusy = true                      // the wake word listener lets go of the microphone meanwhile
        onDispose { WakeState.micBusy = false }
    }

    LaunchedEffect(Unit) {
        delay(800)
        withContext(Dispatchers.IO) {
            val rate = 16000
            val frame = 320
            val minBuf = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            val rec = try {
                AudioRecord(MediaRecorder.AudioSource.VOICE_COMMUNICATION, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, frame * 2 * 16))
            } catch (e: SecurityException) { error = "Mikrofon-Berechtigung fehlt"; return@withContext }
            if (rec.state != AudioRecord.STATE_INITIALIZED) { error = "Mikrofon ist gerade belegt – kurz warten und nochmal öffnen"; rec.release(); return@withContext }
            val buf = ShortArray(frame)
            var noise = 150.0
            rec.startRecording()
            try {
                while (isActive) {
                    var got = 0
                    while (got < frame) { val n = rec.read(buf, got, frame - got); if (n <= 0) break; got += n }
                    if (got < frame) { delay(10); continue }
                    var sum = 0.0
                    for (s in buf) sum += s.toDouble() * s
                    val rms = sqrt(sum / frame)
                    val sensitivity = sensNow[0]
                    val k = 6.0 - sensitivity / 100.0 * 4.0                // the same formula the call uses
                    val minAbs = 250.0 + (100 - sensitivity) * 6.0
                    val thr = maxOf(noise * k, minAbs)
                    val isSpeech = rms > thr
                    if (!isSpeech) noise = (noise * 0.97 + rms * 0.03).coerceIn(30.0, 1500.0)
                    level = (rms / 6000.0).coerceIn(0.0, 1.0).toFloat()
                    threshold = (thr / 6000.0).coerceIn(0.0, 1.0).toFloat()
                    speech = isSpeech
                }
            } finally { try { rec.stop() } catch (_: Exception) {}; rec.release() }
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Mikrofon testen") },
        text = {
            Column {
                Text("Sprich einen normalen Satz. Der Balken muss die Linie überschreiten, in Ruhe nicht.", fontSize = 13.sp)
                Spacer(Modifier.height(14.dp))
                BoxWithConstraints(Modifier.fillMaxWidth().height(26.dp).clip(RoundedCornerShape(8.dp)).background(Color(0x33FFFFFF))) {
                    val w = maxWidth
                    Box(Modifier.fillMaxHeight().width(w * level).background(if (speech) Ok else Violet))
                    Box(Modifier.fillMaxHeight().width(3.dp).offset(x = w * threshold).background(Pink))
                }
                Spacer(Modifier.height(8.dp))
                Text(if (error.isNotEmpty()) error else if (speech) "✓ Sprache erkannt" else "Ruhe", color = if (error.isNotEmpty()) MaterialTheme.colorScheme.error else if (speech) Ok else MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(14.dp))
                Row { Text("Empfindlichkeit", Modifier.weight(1f)); Text("${sens.toInt()}", color = Pink) }
                Slider(value = sens, onValueChange = { sens = it }, onValueChangeFinished = { Prefs.vadSensitivity = sens.toInt() }, valueRange = 0f..100f)
                Text("Höher = erkennt auch leise Sprache, reagiert aber leichter auf Geräusche.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        },
        confirmButton = { TextButton(onClick = { Prefs.vadSensitivity = sens.toInt(); onDismiss() }) { Text("Fertig") } },
    )
}

/** Wake word test: shows what the speech recogniser hears and whether that would wake her - to find out how the name is understood. */
@Composable
fun WakeTestDialog(onDismiss: () -> Unit) {
    val lines = remember { mutableStateListOf<String>() }
    var live by remember { mutableStateOf("") }
    var matched by remember { mutableStateOf("") }
    var saved by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var sens by remember { mutableFloatStateOf(Prefs.wakeSensitivity.toFloat()) }
    val sensNow = remember { floatArrayOf(sens) }
    sensNow[0] = sens

    DisposableEffect(Unit) { WakeState.micBusy = true; onDispose { WakeState.micBusy = false } }

    LaunchedEffect(Unit) {
        delay(800)
        withContext(Dispatchers.IO) {
            val rate = 16000
            val rec = net.yume.companion.voice.SpeakerLock.newRecognizer(Prefs.wakeLanguage())
            if (rec == null) { error = "Das Sprachmodell (${Prefs.wakeLanguage()}) fehlt – erst unter „Sprache & Wake Word“ laden."; return@withContext }
            val minBuf = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            val ar = try {
                AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, 16384))
            } catch (e: SecurityException) { error = "Mikrofon-Berechtigung fehlt"; rec.close(); return@withContext }
            if (ar.state != AudioRecord.STATE_INITIALIZED) { error = "Mikrofon ist gerade belegt – kurz warten und nochmal öffnen"; ar.release(); rec.close(); return@withContext }
            val buf = ShortArray(1600)
            ar.startRecording()
            try {
                while (isActive) {
                    val n = ar.read(buf, 0, buf.size)
                    if (n <= 0) { delay(20); continue }
                    val done = rec.acceptWaveForm(buf, n)
                    val json = if (done) rec.result else rec.partialResult
                    val heard = net.yume.companion.voice.VoskStore.text(json)
                    if (heard.isNotBlank()) {
                        live = heard
                        val hit = net.yume.companion.voice.WakeMatch.explain(heard, Prefs.wakeWordList(), sensNow[0].toInt())
                        if (hit != null) matched = hit
                        if (done) {
                            // with a trained voice the distance to it is shown, too (lower = more like you)
                            val mine = net.yume.companion.voice.SpeakerLock.enrolled()
                            val print = net.yume.companion.voice.SpeakerLock.vectorOf(json)
                            val voice = if (mine != null && print != null) {
                                val d = net.yume.companion.voice.SpeakerLock.score(print)
                                "  ·  Stimme %.2f %s".format(java.util.Locale.US, d, if (d <= net.yume.companion.voice.SpeakerLock.threshold()) "✓ du" else "✗ andere")
                            } else ""
                            lines.add(0, (if (hit != null) "✓ " else "– ") + heard + voice); while (lines.size > 6) lines.removeAt(lines.lastIndex); live = ""
                        }
                    }
                }
            } finally { try { ar.stop() } catch (_: Exception) {}; ar.release(); rec.close() }
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text("Wake Word testen") },
        text = {
            Column {
                Text("Sag dein Wake Word („${Prefs.wakeWordList().firstOrNull() ?: ""}“). Unten siehst du, was die Spracherkennung versteht – ✓ bedeutet: das würde sie wecken.", fontSize = 13.sp)
                Spacer(Modifier.height(10.dp))
                if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
                Text(if (live.isNotEmpty()) "… $live" else "Ich höre zu …", color = Pink, fontSize = 15.sp)
                if (matched.isNotEmpty()) Text("✓ erkannt als „$matched“", color = Ok, fontSize = 13.sp)
                Spacer(Modifier.height(6.dp))
                lines.forEach { line ->
                    val text = line.drop(2).substringBefore("  ·  Stimme")
                    Text(line, fontSize = 13.sp, color = if (line.startsWith("✓")) Ok else MaterialTheme.colorScheme.onSurfaceVariant,
                        modifier = Modifier.fillMaxWidth().clickable {
                            // tap = "that is how I sound": the sentence becomes one more wake word
                            if (text.isNotBlank() && text.lowercase() !in Prefs.wakeWordList()) { Prefs.wakeWords = Prefs.wakeWords.trimEnd().trimEnd(',') + ", " + text.lowercase(); saved = text }
                        }.padding(vertical = 3.dp))
                }
                if (saved.isNotEmpty()) Text("„$saved“ wurde als Wake Word gespeichert.", fontSize = 12.sp, color = Ok)
                else if (lines.isNotEmpty()) Text("Tipp: Tippe auf eine Zeile, die so klingt wie du – sie wird als zusätzliches Wake Word gespeichert.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                Spacer(Modifier.height(10.dp))
                Row { Text("Empfindlichkeit", Modifier.weight(1f)); Text("${sens.toInt()}", color = Pink) }
                Slider(value = sens, onValueChange = { sens = it }, onValueChangeFinished = { Prefs.wakeSensitivity = sens.toInt() }, valueRange = 0f..100f)
                Text("Wird dein Name oft falsch verstanden: trag die Varianten, die oben stehen, zusätzlich unter „Wake Words“ ein.", fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
            }
        },
        confirmButton = { TextButton(onClick = { Prefs.wakeSensitivity = sens.toInt(); onDismiss() }) { Text("Fertig") } },
    )
}

/** Teaches the phone your voice: you say your wake word five times, the average voice print is stored (on the phone only). */
@Composable
fun SpeakerEnrollDialog(onDismiss: () -> Unit, guestName: String? = null) {
    val needed = if (guestName != null) 6 else 10
    val prints = remember { mutableStateListOf<FloatArray>() }
    var live by remember { mutableStateOf("") }
    var hint by remember { mutableStateOf("") }
    var error by remember { mutableStateOf("") }
    var finished by remember { mutableStateOf("") }

    DisposableEffect(Unit) { WakeState.micBusy = true; onDispose { WakeState.micBusy = false } }

    LaunchedEffect(Unit) {
        delay(800)
        withContext(Dispatchers.IO) {
            val rate = 16000
            val rec = net.yume.companion.voice.SpeakerLock.newRecognizer(Prefs.wakeLanguage())
            if (rec == null || net.yume.companion.voice.SpeakerLock.model() == null) { error = "Das Stimm-Modell oder das Sprachmodell fehlt – bitte erst laden."; return@withContext }
            val minBuf = AudioRecord.getMinBufferSize(rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT)
            val ar = try {
                AudioRecord(MediaRecorder.AudioSource.VOICE_RECOGNITION, rate, AudioFormat.CHANNEL_IN_MONO, AudioFormat.ENCODING_PCM_16BIT, maxOf(minBuf, 16384))
            } catch (e: SecurityException) { error = "Mikrofon-Berechtigung fehlt"; rec.close(); return@withContext }
            if (ar.state != AudioRecord.STATE_INITIALIZED) { error = "Mikrofon ist gerade belegt – kurz warten und nochmal öffnen"; ar.release(); rec.close(); return@withContext }
            val buf = ShortArray(1600)
            ar.startRecording()
            try {
                while (isActive && finished.isEmpty()) {
                    val n = ar.read(buf, 0, buf.size)
                    if (n <= 0) { delay(20); continue }
                    val done = rec.acceptWaveForm(buf, n)
                    val json = if (done) rec.result else rec.partialResult
                    val heard = net.yume.companion.voice.VoskStore.text(json)
                    if (!done) { if (heard.isNotBlank()) live = heard; continue }
                    live = ""
                    if (heard.isBlank()) continue
                    val print = net.yume.companion.voice.SpeakerLock.vectorOf(json)
                    if (print == null) { hint = "Zu kurz – sag das Wake Word etwas deutlicher und in einem Zug."; continue }
                    // the sentence has to be the wake word, otherwise the voice print would be built from random talk
                    if (net.yume.companion.voice.WakeMatch.explain(heard, Prefs.wakeWordList(), 80) == null) { hint = "„$heard“ – das war nicht dein Wake Word, nochmal bitte."; continue }
                    prints.add(print); hint = "„$heard“ ✓"
                    if (prints.size >= needed) {
                        val all = prints.toList()
                        if (guestName != null) {
                            net.yume.companion.voice.SpeakerLock.saveGuest(guestName, all)
                            finished = "Fertig. Die Stimme von $guestName ist angelernt."
                            continue
                        }
                        net.yume.companion.voice.SpeakerLock.saveAll(all)
                        // tolerance from your own spread: each sample against the mean of the others (mean + 3 x deviation), never absurdly open
                        val loo = all.indices.map { i -> net.yume.companion.voice.SpeakerLock.distance(all[i], net.yume.companion.voice.SpeakerLock.average(all.filterIndexed { j, _ -> j != i })) }
                        val avg = loo.average(); val sd = kotlin.math.sqrt(loo.map { (it - avg) * (it - avg) }.average())
                        val suggested = (((avg + 3 * sd) * 1.2).coerceIn(0.35, 0.65) * 100).toInt()
                        Prefs.speakerStrict = suggested
                        Prefs.speakerLock = true
                        finished = "Fertig. Deine Stimme ist angelernt (Toleranz $suggested). Im Wake-Word-Test siehst du, wie nah du dran bist."
                    }
                }
            } finally { try { ar.stop() } catch (_: Exception) {}; ar.release(); rec.close() }
        }
    }

    AlertDialog(
        onDismissRequest = onDismiss,
        title = { Text(if (guestName != null) "Stimme von $guestName anlernen" else "Stimme anlernen") },
        text = {
            Column {
                Text((if (guestName != null) "$guestName sagt das Wake Word („${Prefs.wakeWordList().firstOrNull() ?: ""}“) sechs Mal, jeweils mit kurzer Pause. Dabei nicht reinreden." else "Sag dein Wake Word („${Prefs.wakeWordList().firstOrNull() ?: ""}“) zehn Mal, jeweils mit kurzer Pause. Variiere ein bisschen: mal näher, mal weiter weg vom Handy, mal leiser, mal lauter – so, wie du es später auch sagst.") , fontSize = 13.sp)
                Spacer(Modifier.height(12.dp))
                LinearProgressIndicator(progress = { (prints.size.toFloat() / needed).coerceAtMost(1f) }, Modifier.fillMaxWidth())
                Text("${prints.size} von $needed", Modifier.padding(top = 4.dp), color = Pink)
                if (live.isNotEmpty()) Text("… $live", fontSize = 14.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
                if (hint.isNotEmpty()) Text(hint, fontSize = 13.sp, color = Violet)
                if (error.isNotEmpty()) Text(error, color = MaterialTheme.colorScheme.error)
                if (finished.isNotEmpty()) Text(finished, color = Ok)
            }
        },
        confirmButton = { TextButton(onClick = onDismiss) { Text(if (finished.isNotEmpty()) "Fertig" else "Abbrechen") } },
    )
}
