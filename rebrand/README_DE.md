# SoW Rebrand (privates Hilfsprogramm)

Eigenständiges Programm, **nicht Teil von Soul of Waifu** und ohne Eintrag in dessen Oberfläche.
Start: `SoW-Rebrand.bat`. Der Ordner liegt bewusst außerhalb von SoW. Das Python kommt aus `python_path.txt`
(eine Zeile, Pfad zu einer python.exe mit PyQt6; aktuell das Python deiner SoW-Installation). Der SoW-Ordner wird
beim ersten Start gemerkt (`rebrand_settings.json`) oder per Dialog gewählt bzw. als Argument übergeben:
`SoW-Rebrand.bat "C:\Pfad\zu\SoW"`.

## Was es ändert
Nur `app/configuration/branding.json` und Bilder unter `assets/custom_branding/` des gewählten Ordners.
Vor jedem Speichern wird die alte Datei nach `SoW-Rebrand/backups/` gesichert.

* Name & Autor: Programmname, Kurzname, „Made by“ samt Link
* Logos: Programm-Logo (Fenster, Info-Dialog), optional breites Seitenleisten-Logo
* Links: Website, Docs, Support/Spenden, Discord, GitHub, YouTube, Update-Repository
* Texte: Info-Text (HTML) und zusätzliche Credits

Pro Feld: „Standard verwenden“ = Originalwert, eigener Wert = dein Text, **leer lassen = Element ausblenden**.
Profile speichern/laden wechselt komplette Marken (Texte + Bilder) mit einem Klick.
Nach dem Speichern Soul of Waifu neu starten.

## Startfenster (start.bat / installer.bat)
Der große Banner oben im Startfenster, der Programmname und der Untertitel kommen aus den Feldern
„Programmname“, „Untertitel im Startfenster“ und „Großer Banner-Text“ (leer = Programmname).
Tab „Startfenster“ zeigt eine Live-Vorschau im gleichen Block-Schriftstil (A–Z, 0–9, - . _ ! ?).
Beim Speichern entstehen `app/configuration/branding_start.cmd` und `branding_banner.txt`, die `start.bat`
einliest. Beim Zurücksetzen auf Original werden sie wieder gelöscht. Nur wirksam, wenn die `start.bat`
der Ziel-Version den Branding-Hook enthält (ab 2.5.3 in diesem Projekt); sonst zeigt der Tab einen Hinweis.

## Aufwärtskompatibel
* Die Feldliste wird aus `app/utils/branding.py` (`BRANDING_FIELDS`) der Ziel-Version gelesen (nur gelesen, nie ausgeführt).
  Neue Felder späterer Versionen erscheinen automatisch.
* Unbekannte Schlüssel in `branding.json` bleiben erhalten (Tab „Weitere Schlüssel“).
* Ohne Registry (ältere Version) gilt eine eingebaute Mindestliste.

## Beim Erweitern von SoW
Neues Branding-Feld = ein Eintrag in `BRANDING_FIELDS` plus die Stelle im Code, die `get_text`/`get_url` aus
`app/utils/branding.py` nutzt. Das Programm hier braucht dafür keine Änderung.
