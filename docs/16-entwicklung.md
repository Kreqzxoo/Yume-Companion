# 16 Entwicklung

Für alle, die den Code ändern, Installer bauen oder zum Projekt beitragen wollen.

## 16.1 Projektstruktur

```text
Yume-Companion/
├─ main.py                  Einstieg der PC-App (PyQt6, qasync)
├─ installer.bat / start.bat Pakete installieren / Programm starten
├─ app/
│  ├─ configuration/        Einstellungen, Charaktere, Vorlage settings.template.json, Branding
│  ├─ gui/                  Oberfläche: sowInterface.py (Layout), interface_signals.py (Logik),
│  │                        custom_widgets.py, Organizer-, Dashboard-, Spotify-, Backup-, Vision-Seiten …
│  ├─ translations/         de.yaml, en.yaml, ru.yaml
│  ├─ utils/
│  │  ├─ ai_clients/        Anbieter (OpenAI, Anthropic, Gemini, …), llama.cpp-Verwaltung, Werkzeuge (tools.py),
│  │  │                     Prompt-Aufbau, Yume-Bühne-Engine, MCP-Client
│  │  ├─ soul_companion/    Desktop-Begleiter (Hormon-Modell, Plugins)
│  │  ├─ integrations/      Home Assistant
│  │  ├─ speech-to-text/    Whisper, Silero-VAD
│  │  └─ *.py               Gedächtnis, Organizer, Routinen, Skills, Wissensbasis, Dokumente, Webserver,
│  │                        Dashboard, Spotify, Mobilgeräte, Backups, TTS, Vision, Bildgenerierung, Discord …
│  ├─ web_client/           Browser-Oberfläche (Port 8000)
│  └─ models/, voices/, font/, cache/   Laufzeitdaten (nicht im Repository, außer font)
├─ assets/                  Hintergründe, Ambient, Avatare (Demo-Bilder), Branding
├─ android/                 Handy-App (Kotlin, Jetpack Compose), Gradle-Projekt
├─ llm-server/              Yume LLM Server (C#), Build- und Installer-Skripte
├─ updater/                 Release-Werkzeuge (Setup/Update bauen, Verifizieren, Fehleranalyse)
├─ rebrand/                 Name, Logo, Links ändern (Branding)
├─ tests/                   Entwickler-Tests (Python)
├─ tools/                   SOW-Studio, Demo-Inhalte, Screenshot-Werkzeuge, Prüfungen
└─ docs/                    diese Dokumentation
```

## 16.2 Aus dem Quelltext arbeiten

1. Einrichten: [Kapitel 01](01-installation.md#13-weg-b-aus-dem-quelltext) (`tools\setup_from_source.bat`).
2. Starten: `start.bat`, oder in der aktivierten Umgebung `python main.py`.
3. Einstellungen und Charaktere entstehen beim ersten Start aus `app\configuration\settings.template.json`. Eigene Testdaten: `app\data\envs\sow\python.exe tools\demo\make_demo_content.py`.

**Wichtige Konventionen**
* Oberflächentexte stehen in `app/translations/*.yaml`. Neue Texte als Schlüssel in **allen** drei Dateien ergänzen; neue Seiten benutzen `tr("schlüssel", "Standardtext")`.
* Neue Werkzeuge der KI: Klasse in `app/utils/ai_clients/tools.py` (von `BaseTool`) und im `ToolRegistry` eintragen; Berechtigungen in den Einstellungen verknüpfen.
* Pfade immer **relativ zum Projektordner** und ohne feste Benutzernamen. Persönliche Daten gehören nach `%LOCALAPPDATA%\YumeCompanion`, nicht ins Projekt.
* Geheimnisse nie ins Repository: siehe `.gitignore` und `tools/dev/check_upload.ps1`.

## 16.3 Tests

```powershell
powershell -ExecutionPolicy Bypass -File tests\run_tests.ps1          # offline, sicher
powershell -ExecutionPolicy Bypass -File tests\run_tests.ps1 -Live    # zusätzlich: echte Verbindungen (LLM-Server, Spotify, Routen)
```

Die Tests laufen mit der Python-Umgebung der App (`app\data\envs\sow`) im „offscreen“-Modus und decken u. a. Schnellbefehle, Organizer, Routinen, Listen, Rückgängig, Tagebuch, Szenen, Eingang, Wissensdatenbank, Regenalarm, Werkzeug-Modell, Anwesenheit, Dokumente und Skills ab (siehe `tests/Testliste.md` für die manuelle Testliste und `tests/README.txt`). **Achtung:** Starte die Tests mit einem Testprofil (`LOCALAPPDATA` auf einen leeren Ordner setzen), wenn du echte Organizer-Daten hast:

```powershell
$env:LOCALAPPDATA = "$env:TEMP\yume-test"; powershell -File tests\run_tests.ps1
```

Android: `android\run-unit-tests.ps1` (siehe 16.5). Zusätzlich gibt es in `.github/workflows` eine einfache Prüfung (Syntax aller Python-Dateien).

## 16.4 Setup und Updates bauen (Windows)

Das **Yume Release Tool** (`updater\Yume Release Tool.bat`) baut aus deinem **Arbeitsordner** ein sauberes Setup:

* arbeitet nur in einer **temporären Kopie**, dein Original bleibt unverändert;
* entfernt alles, was `installer.bat` nachinstalliert, sowie Cache, Logs und persönliche Daten;
* setzt Einstellungen auf die **Vorlagen** zurück (`updater\installer_build\templates`);
* **Voll-Installer** (ca. 2 GB, mit Komponenten-Auswahl) oder **Nur Update** (klein: nur Programmcode und neue Pakete aus `requirements_extra.txt`);
* prüft auf Wunsch das Ergebnis (`Yume Verify.ps1`: Reset-Zustand, Syntax, Importe, Oberfläche startet headless, KI-Smoke-Test mit einem Mini-Modell);
* bei Fehlern erklärt `Yume Doctor.ps1` mit Regeln (und, wenn ein starkes lokales Modell installiert ist, mit KI), was schiefging, und bietet **sichere** Korrekturen an.

Voraussetzungen: **Inno Setup 6** (das Tool bietet die Installation per `winget` an) und ein Arbeitsordner **mit** installierter Umgebung `app\data\envs\sow` (also ein normal installiertes Programm, nicht das nackte Repository). Das Tool setzt keine Pfade voraus: Quelle und Ausgabeordner wählst du im Fenster.

Tipp: Der Arbeitsordner sollte **sauber** bleiben (nicht starten, bevor du baust), sonst landen Chats und Logs im Setup. Die Vorlagen und die Prüfung fangen das ab, ersetzen aber keinen Blick auf `check_upload.ps1`.

> **Hinweis zu den Vorlagen:** `templates\make_templates.py` erzeugt die Vorlagen aus deinem Arbeitsordner. Es setzt persönliche Werte, Geräte, **Tokens und Geräte-IDs** zurück. (In dieser Fassung wurden `dashboard_token` und `android_host_id` ergänzt; frühere Setups trugen sonst dasselbe Dashboard-Token in jeder Installation.)

Der **Yume Updater** (`updater\YumeUpdaterLauncher.cs`, `yume_updater_setup.iss`) ist nur der **Starter** des Release Tools (öffnet die PowerShell-Oberfläche ohne Konsolenfenster). `Build Updater Installer.ps1` baut daraus den Installer des Release Tools.

## 16.5 Android-App bauen und testen

```powershell
android\build-apk.bat                  # APK bauen (richtet JDK, Android SDK, Gradle bei Bedarf ein, mehrere GB)
android\run-unit-tests.ps1             # Tests; schreibt auch Bilder der Bildschirme (YUME_SHOTS=…)
```

* Ergebnis: `%LOCALAPPDATA%\YumeAndroidBuild\Yume-Companion.apk` (Debug-signiert, für den eigenen Gebrauch). Lege sie in `tools\android\`, damit die PC-App sie zum Speichern anbietet. Für eine Veröffentlichung im Play Store brauchst du einen eigenen Signierschlüssel (nie ins Repository).
* `app/src/test/…` enthält JVM-Tests ohne Handy: `LayoutTest` und `DocShotsTest` rendern echte Compose-Bildschirme (Robolectric) und speichern PNGs; `WakeMatchTest`, `QuickCommandsTest`, `CallRulesTest` prüfen die Logik.
* Struktur: `core/` (Verbindung, Chat, Einstellungen), `voice/` (Anruf, Wake Word, Sprecher-Erkennung, Assistenten-Fenster), `device/` (Handy-Steuerung, Wecker, Spotify, Anrufschutz, Kamera, Automationen), `ui/` (Compose-Bildschirme, 3D-Avatar), `offline/` (Notfall-Modell).
* Im Projekt liegt `android/local.properties` **nicht** (enthält deinen SDK-Pfad); sie entsteht beim Bauen.

## 16.6 LLM-Server bauen

Siehe [Kapitel 12.7](12-llm-server.md#127-selbst-bauen): `llm-server\Build Yume LLM Server.ps1` (Compiler `csc.exe` aus Windows, Inno Setup für den Installer).

## 16.7 Branding (Name, Logo, Links)

`rebrand\SoW-Rebrand.bat` ändert **nur** `app/configuration/branding.json` und die Bilder unter `assets/custom_branding/` (mit Sicherung der alten Datei in `rebrand\backups`): Programmname, Kurzname, Autor („Made by“ samt Link), Logos, **Links** (Webseite, Doku, Support, Discord, GitHub, YouTube) und **Update-Repository**, Info-Text und zusätzliche Credits, Startfenster (Banner-Text). *Standard verwenden* = Originalwert, eigener Wert = dein Text, *leer lassen* = Element ausblenden. Profile speichern/laden wechselt komplette Marken.

* Python: `rebrand\python_path.txt` (eine Zeile, Pfad zu einer `python.exe` mit PyQt6) oder die Umgebung des Projekts (`..\app\data\envs\sow`).
* **Wichtig für GPL:** Du darfst Namen und Logo ändern, **den Hinweis auf den Original-Autor (jofizcd) aber nicht entfernen** (`NOTICE.md`, Über-Dialog, `LICENSE`).
* Nach dem Speichern die App neu starten.
* Ergänze vor dem Release das **Update-Repository** (`Kreqzxoo/Yume-Companion`), damit die Prüfung beim Programmstart dein Repository fragt.

## 16.8 SOW Studio und weitere Hilfsprogramme

| Programm | Zweck |
| --- | --- |
| `tools\SOW-Studio.bat` (`sow_studio.py`) | kleines Zusatzwerkzeug für Wake-Word/Echo-Schutz, Audio-/GPU-Werte, Logo, Titel, Credits und die deutschen Übersetzungen (Einträge, die noch dem Englischen gleichen, lassen sich filtern). **App vorher schließen** |
| `tools\demo\make_demo_content.py` | Beispiel-Charaktere, Bilder, Persona, Lorebook, Szene (erfunden, frei) |
| `tools\dev\take_screenshots.py` | Bilder der PC-App für die Doku (siehe 16.9) |
| `tools\dev\take_web_screenshots.py` | Bilder von Webclient und Dashboard (Playwright) |
| `tools\dev\capture_window.ps1` | Fenster eines Windows-Programms fotografieren (z. B. LLM-Server) |
| `tools\dev\check_upload.ps1` | Upload-Prüfung auf Geheimnisse, große/verbotene Dateien |
| `tools\dev\make_yume_icons.py` | Symbole der Oberfläche erzeugen |
| `tools\fetch_models.py` | die zwei kleinen Modelle laden |
| `tools\setup_from_source.bat` | Installation aus dem Quelltext |

## 16.9 Dokumentation und Bilder neu erzeugen

Alle Bilder in `docs/images` stammen aus der echten Software mit Demo-Daten und lassen sich neu erzeugen:

```powershell
# 1) Demo-Inhalte (Charaktere Yume, Mika, Kai, Persona, Lorebook, Szene)
app\data\envs\sow\python.exe tools\demo\make_demo_content.py

# 2) PC-App: Seiten, Einstellungen, Dialoge, Chat (nutzt ein leeres LOCALAPPDATA, damit keine privaten Daten sichtbar sind)
$env:YUME_ROOT = (Get-Location).Path
$env:LOCALAPPDATA = "$env:TEMP\yume-shots"
app\data\envs\sow\python.exe tools\dev\take_screenshots.py docs\images\pc alle

# 3) Webclient und Dashboard: erst  take_screenshots.py <Ordner> web  starten (gibt den Token aus), dann
app\data\envs\sow\python.exe tools\dev\take_web_screenshots.py <Token> docs\images\web

# 4) Handy-App (ohne Handy)
$env:YUME_SHOTS = "$PWD\docs\images\android"; android\run-unit-tests.ps1
```

Das Skript `take_screenshots.py` ersetzt Benutzernamen und Pfade in Beschriftungen sowie Felder mit Token/Schlüssel/Adresse durch Platzhalter. Prüfe die Bilder dennoch, bevor du sie veröffentlichst.

## 16.10 Beitragen

* Issues und Pull Requests sind willkommen (siehe `CONTRIBUTING.md`).
* Halte Änderungen klein, teste sie (16.3) und beschreibe sie kurz.
* Jede Datei, die du hinzufügst, muss unter **GPL-3.0-kompatiblen** Bedingungen stehen. Keine Modelle, Stimmen, Bilder oder Charaktere ohne klare Lizenz.
