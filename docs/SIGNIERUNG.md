# Signieren und Virenscanner (für den Herausgeber)

Dieses Kapitel ist für den, der Setups baut. Wie Nutzer Downloads prüfen, steht in [14 Backup, Updates, Sicherheit](14-backup-updates-sicherheit.md#downloads-prüfen-und-windows-warnungen).

## Was heute schon eingebaut ist
- Die Programmdateien tragen Herstellername, Beschreibung und Versionsnummer (Starter `Yume Companion.exe`, `YumeLLMServer.exe`, beide Setups). Dateien ohne diese Angaben werden von Scannern öfter beanstandet.
- Das Update-Programm der App lädt Setups nur von `github.com/<Repository>/releases/download/…`, prüft die SHA-256-Prüfsumme und startet nichts bei Abweichung ([14 Backup, Updates, Sicherheit](14-backup-updates-sicherheit.md)).
- Die Build-Werkzeuge haben einen **Signatur-Haken**: Setzt du die Umgebungsvariable `YUME_SIGN_CMD`, werden der Starter, das Setup (samt Deinstaller) und beim LLM Server die Exe und sein Setup signiert. Ohne die Variable läuft der Build wie bisher.

## Signatur einschalten (sobald ein Zertifikat da ist)
1. **Zertifikat besorgen** (Identitätsprüfung macht der Herausgeber selbst):
   - *Microsoft Artifact Signing* (früher „Trusted Signing“), laut Microsoft mit Plänen für Einzelpersonen und Firmen; ob eine Privatperson in Deutschland teilnehmen darf, bei Microsoft prüfen;
   - oder ein normales Code-Signing-Zertifikat (OV) eines Anbieters, am besten mit Cloud-Signatur (kein USB-Stick nötig).
   Als Privatperson ist die Prüfung oft schwerer; mit einem Kleingewerbe geht es meist einfacher.
2. **Signierbefehl festlegen.** Er muss `$f` enthalten (Platz für den Dateipfad) und einen **Zeitstempel** setzen, damit die Signatur nach Ablauf des Zertifikats gültig bleibt. Beispiel mit `signtool`:
   ```
   setx YUME_SIGN_CMD "signtool.exe sign /fd SHA256 /tr http://timestamp.digicert.com /td SHA256 /n \"Dein Name\" \"$f\""
   ```
   Bei Artifact Signing oder Cloud-Anbietern nimmst du den Befehl aus deren Anleitung; wichtig ist nur `$f`.
3. **Bauen wie gewohnt** (`Yume Release Tool` oder `Yume Build.ps1`). In der Ausgabe steht „Signiert: …“ und „Setup und Deinstaller werden signiert.“
4. **Prüfen:** `Get-AuthenticodeSignature "Yume-Companion-Setup-….exe"` muss `Status: Valid` und deinen Namen zeigen.

## Wichtig zu wissen
- Eine Signatur macht das Programm **nicht sofort** frei von Warnungen. Seit 2024 bekommt auch ein EV-Zertifikat keinen Sofort-Vertrauensbonus mehr: SmartScreen vertraut Datei und Herausgeber erst nach genug Downloads. Ein gleichbleibender Herausgebername und ein verlängertes Zertifikat vom selben Anbieter bauen den Ruf schneller auf.
- Windows 11 mit **Smart App Control** blockiert unsignierte oder unbekannte Programme ganz. Dafür hilft nur die Signatur.
- Signiere **jede** Veröffentlichung gleich (nicht mal mit, mal ohne), und ändere den Herausgebernamen nicht.

## Fehlalarme von Virenscannern melden
Nach jedem Release die Setup-Datei bei den Herstellern als Fehlalarm melden, die sie beanstanden:
1. Bei **Microsoft Defender**: Formular „File submission“ unter <https://www.microsoft.com/en-us/wdsi/filesubmission> (braucht ein Microsoft-Konto). „Software developer“ wählen, die Datei hochladen, die Prüfsumme und den Link zum Quelltext angeben.
2. Bei **VirusTotal** zeigt `https://www.virustotal.com/gui/file/<SHA-256>` das Ergebnis, wenn jemand die Datei schon hochgeladen hat. Die Setups sind mit 2 GB zu groß für den normalen Upload; für Tests eignet sich die kleine `YumeLLMServer.exe`.
3. Jeder andere Hersteller hat ein eigenes Formular (Suche: „<Name> false positive submission“). Gib dort den Link zum Release und zum Quelltext an.
4. Schreibe in den Release-Text, dass es sich bei Meldungen um Fehlalarme handeln kann, und nenne die Prüfsumme.
