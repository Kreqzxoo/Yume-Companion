# Backup & Wiederherstellung – Soul of Waifu 2.5.3

## Wo finde ich die Funktion?

In SoW: **Einstellungen → Backup & Wiederherstellung**.

### Backup erstellen

1. Auf **Backup-ZIP erstellen** klicken.
2. Speicherort und Dateinamen auswählen.
3. Optional **Eigene Stimmen, Modelle und Asset-Ordner einschließen** aktivieren. Das kann mehrere Gigabyte beanspruchen.
4. Das ZIP enthält `settings.json`, `api.json`, `characters.json`, eine vorhandene `branding.json`, `app/data` sowie gecachte Charakter-Avatare. Mit aktivierter Asset-Option kommen ausgewählte Modell-, Stimmen- und Asset-Ordner dazu.

**Datenschutz:** `api.json` kann API-Tokens enthalten; `characters.json` kann private Chats enthalten. Backup-Dateien vertraulich speichern und nicht öffentlich hochladen.

### Backup importieren

- **Backup importieren / wiederherstellen** nimmt das aktuelle SoW-ZIP-Format sowie ZIP-Backups ohne Manifest aus älteren Versionen an.
- **Alten Backup-Ordner importieren** kann einen Ordner auswählen, der die alte Struktur `app/configuration/` enthält.
- Vor dem Import zeigt SoW die Anzahl der unterstützten Dateien und fragt zur Bestätigung.
- Vor dem Überschreiben erstellt SoW automatisch eine Sicherheitssicherung des aktuellen Zustands unter `backups/`.
- Entsprechende Konfigurationsdateien werden ersetzt; andere, im Backup fehlende Dateien werden nicht gelöscht. Datenordner werden dateiweise zusammengeführt.
- Nach dem Import SoW vollständig neu starten.

## 2.5.1-Kompatibilität

Der Importer erkennt alte ZIP-Strukturen wie `Soul-of-Waifu-2.5.1/app/configuration/settings.json`, `api.json` und `characters.json`, auch wenn kein Manifest vorhanden ist. Beim Laden werden fehlende optionale 2.5.3-Standardwerte ergänzt. Ein zu kleines Kontextfenster unter 8192 Tokens wird für 2.5.3 auf 8192 angehoben. Vorhandene Personas, Presets und sonstige unbekannte Einstellungsfelder bleiben erhalten.

## Sicherheit / Grenzen

- Das Importieren führt keinen Python-Code aus dem Backup aus und überschreibt keine SoW-Programmdateien.
- Es werden nur bekannte Konfigurationsdateien, Speicher-/Avatar-Ordner und ausgewählte Benutzer-Assets importiert.
- ZIP-Pfade mit `..` oder absoluten Pfaden werden abgelehnt bzw. übersprungen.
- Sehr große optionale Modell-Dateien werden beim Lesen/Restore gestreamt, nicht vollständig in den Arbeitsspeicher geladen.
- Die Sicherung ist keine vollständige Kopie einer Python-Umgebung. Installierte Pakete und virtuelle Umgebungen werden nicht gesichert.
