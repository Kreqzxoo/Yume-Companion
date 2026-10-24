package net.yume.companion.ui

import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.background
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp

/** Tests switch the endless animations off (an endless animation never lets a headless test become idle). */
object UiFlags { var animations = true }

val Pink = Color(0xFFFF8FC7)
val Violet = Color(0xFFB69CFF)
val Night = Color(0xFF0E0916)
val Panel = Color(0xFF1A1226)
val Ok = Color(0xFF6EE7A0)

@Composable
fun YumeTheme(content: @Composable () -> Unit) {
    MaterialTheme(
        colorScheme = darkColorScheme(
            primary = Pink, onPrimary = Color(0xFF2A0A1A), secondary = Violet, background = Night, surface = Panel,
            onBackground = Color(0xFFF1E8F6), onSurface = Color(0xFFF1E8F6), surfaceVariant = Color(0xFF241A33), onSurfaceVariant = Color(0xFFB9A9C9),
            primaryContainer = Color(0xFF3A1F33), onPrimaryContainer = Color(0xFFFFD9EC),
        ),
        content = content,
    )
}

@Composable
fun Section(title: String, content: @Composable ColumnScope.() -> Unit) {
    Column(Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp)) {
        Text(title.uppercase(), color = Violet, fontWeight = FontWeight.Bold, fontSize = 12.sp, letterSpacing = 1.sp)
        Spacer(Modifier.height(6.dp))
        Card(colors = CardDefaults.cardColors(containerColor = Panel), shape = RoundedCornerShape(16.dp)) {
            Column(Modifier.padding(horizontal = 14.dp, vertical = 10.dp), verticalArrangement = Arrangement.spacedBy(4.dp), content = content)
        }
    }
}

@Composable
fun SwitchRow(title: String, sub: String = "", get: () -> Boolean, set: (Boolean) -> Unit) {
    var v by remember { mutableStateOf(get()) }
    Row(Modifier.fillMaxWidth().padding(vertical = 4.dp), verticalAlignment = Alignment.CenterVertically) {
        Column(Modifier.weight(1f)) {
            Text(title)
            if (sub.isNotEmpty()) Text(sub, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        }
        Switch(checked = v, onCheckedChange = { v = it; set(it) })
    }
}

@Composable
fun SliderRow(title: String, range: ClosedFloatingPointRange<Float>, get: () -> Int, set: (Int) -> Unit, unit: String = "", sub: String = "") {
    var v by remember { mutableStateOf(get().toFloat()) }
    Column(Modifier.fillMaxWidth().padding(vertical = 2.dp)) {
        Row { Text(title, Modifier.weight(1f)); Text("${v.toInt()}$unit", color = Pink) }
        if (sub.isNotEmpty()) Text(sub, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Slider(value = v, onValueChange = { v = it }, onValueChangeFinished = { set(v.toInt()) }, valueRange = range)
    }
}

@Composable
fun TextRow(label: String, get: () -> String, set: (String) -> Unit, hint: String = "", single: Boolean = true) {
    var v by remember { mutableStateOf(get()) }
    OutlinedTextField(
        value = v, onValueChange = { v = it; set(it) }, label = { Text(label) }, singleLine = single,
        placeholder = { if (hint.isNotEmpty()) Text(hint) }, modifier = Modifier.fillMaxWidth().padding(vertical = 4.dp),
    )
}

@Composable
fun ChoiceRow(title: String, options: List<Pair<String, String>>, get: () -> String, set: (String) -> Unit, sub: String = "") {
    var v by remember { mutableStateOf(get()) }
    var open by remember { mutableStateOf(false) }
    Column(Modifier.fillMaxWidth().padding(vertical = 4.dp)) {
        Text(title)
        if (sub.isNotEmpty()) Text(sub, fontSize = 12.sp, color = MaterialTheme.colorScheme.onSurfaceVariant)
        Box {
            OutlinedButton(onClick = { open = true }) { Text(options.firstOrNull { it.first == v }?.second ?: v) }
            DropdownMenu(expanded = open, onDismissRequest = { open = false }) {
                options.forEach { (key, label) -> DropdownMenuItem(text = { Text(label) }, onClick = { v = key; set(key); open = false }) }
            }
        }
    }
}

@Composable
fun Chip(text: String, color: Color) {
    Box(Modifier.background(color.copy(alpha = 0.18f), RoundedCornerShape(50)).padding(horizontal = 10.dp, vertical = 4.dp)) {
        Text(text, color = color, fontSize = 12.sp, fontWeight = FontWeight.SemiBold, maxLines = 1, softWrap = false)
    }
}

@Composable
fun BigButton(text: String, onClick: () -> Unit, modifier: Modifier = Modifier, danger: Boolean = false) {
    Button(
        onClick = onClick, modifier = modifier.fillMaxWidth().heightIn(min = 52.dp),
        colors = ButtonDefaults.buttonColors(containerColor = if (danger) Color(0xFFE5484D) else Pink, contentColor = if (danger) Color.White else Color(0xFF2A0A1A)),
        shape = RoundedCornerShape(14.dp),
    ) { Text(text, fontWeight = FontWeight.Bold) }
}
