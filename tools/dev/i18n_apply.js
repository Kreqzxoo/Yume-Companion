// Ersetzt deutsche Text-Literale in Kotlin-Dateien durch tr("deutsch", "english").
// Aufruf:  node tools/dev/i18n_apply.js <android-java-ordner> <tabelle.json>
// Tabelle: { "ui/Datei.kt": [ ["deutscher Text wie im Quelltext", "English text"], ... ], ... }
// Fehlende Treffer werden gemeldet; bereits ersetzte Texte werden nicht noch einmal ersetzt.
const fs = require('fs');
const path = require('path');

const root = process.argv[2];
const table = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
let missing = 0, replaced = 0;

for (const [rel, pairs] of Object.entries(table)) {
  const file = path.join(root, rel);
  let src = fs.readFileSync(file, 'utf8');
  const crlf = src.includes('\r\n');
  if (crlf) src = src.replace(/\r\n/g, '\n');
  let changed = false;
  for (const [de, en] of pairs) {
    const lit = '"' + de + '"';
    const already = 'tr(' + lit + ', ';
    // alle Vorkommen, die nicht schon in tr(...) stehen
    let out = '', i = 0, n = 0;
    while (true) {
      const j = src.indexOf(lit, i);
      if (j < 0) { out += src.slice(i); break; }
      if (src.slice(Math.max(0, j - 3), j) === 'tr(') { out += src.slice(i, j + lit.length); i = j + lit.length; continue; }
      out += src.slice(i, j) + 'tr(' + lit + ', "' + en + '")';
      i = j + lit.length; n++;
    }
    if (n === 0 && !src.includes(already)) { console.log('FEHLT  ' + rel + ' :: ' + de.slice(0, 70)); missing++; }
    else if (n > 0) { src = out; changed = true; replaced += n; }
  }
  if (changed) {
    const hasImport = /import net\.yume\.companion\.core\.(\*|tr)\b/.test(src) || /^package net\.yume\.companion\.core\s*$/m.test(src);
    if (!hasImport) src = src.replace(/^(package [^\n]+\n)/, '$1\nimport net.yume.companion.core.tr\n');
    fs.writeFileSync(file, crlf ? src.replace(/\n/g, '\r\n') : src, 'utf8');
  }
}
console.log('ersetzt: ' + replaced + ', fehlend: ' + missing);
