# Änderungen

Format: neueste Version oben. Versionsnummern: `Haupt.Neben.Fehler`.

## 3.0.0 Beta 12 (Setup)

**Behoben**
- Start nach Neuinstallation: `ImportError: numpy.core.multiarray failed to import` (faiss / rvc_python). pip konnte beim Setup NumPy 1.26 durch NumPy 2 ersetzen. Der Installer begrenzt jetzt die Paketversionen (`constraints.txt`), setzt NumPy 1.26.4 bei Bedarf zurück und testet `import faiss`.

## Unreleased

**Lizenz**
- Yume LLM Server (`llm-server/`): ab jetzt proprietär, alle Rechte vorbehalten (Copyright (c) 2026 Kreqzxoo), siehe `llm-server/LICENSE`. Der Installer zeigt die Lizenz an (wirksam ab dem nächsten gebauten Setup). Bereits veröffentlichte Versionen (bis v3.0.0-beta11) bleiben für deren Empfänger unter der damaligen Lizenz.
- Android-App (`android/`): ebenfalls proprietär, alle Rechte vorbehalten, siehe `android/LICENSE`. Dafür wurde die 3D-Avatar-Seite der App von Grund auf neu geschrieben (Mimik, Blinzeln, Blick, Idle-Gesten, Lippenbewegung, Körper-Animationen), die frühere Seite enthielt Code aus Soul of Waifu.

## 3.0.0 Beta 11 (Android-App 1.1.0)

**Neu**
- Android-App auf Deutsch und Englisch (Einstellung *App-Sprache*, automatisch nach Handy-Sprache), inklusive englischer Sprachbefehle und Dolmetscher
- Android-App wird mit eigenem Signaturschlüssel gebaut (GitHub-Action `android-release.yml`)
- CI prüft jetzt auch die Android-App (Tests, Debug-APK) und die Doku
- `updater/Make Clean Build Source.ps1`: sauberer Quellordner für Releases mit Leck-Prüfung

**Hinweis**
- Die APK ist jetzt mit einem neuen Schlüssel signiert: die alte Beta-APK vorher deinstallieren (Einstellungen der App gehen dabei verloren, danach neu koppeln).

## 3.0.0 Beta (in Arbeit)

**Neu**
- Android-App „Yume Companion“ (QR-Kopplung, Chat, Anrufe, Wake Word, 3D-Avatar, Handy-Steuerung, Wecker, Auto-/Wandmodus, Offline-Notfallmodus)
- Yume LLM Server: zweiter PC als KI-Server (Sprache, Vision, Bilder, Werkzeuge)
- Organizer: Kalender, Mail (lesen), Erinnerungen, Listen, Routinen, Pendeln, Personen, Wissensdatenbank, Dokumente, Skills, Eingang
- „Hey Yume“ am PC, WebRTC-AEC3-Echoentfernung, Stimmungs- und Stimm-Gespür
- Leistungs-Dashboard, Werkzeugprotokoll, Selbsttest, automatische Profil-Backups (`.yumepack`)
- Neues Design („Yume Look“), deutsche Übersetzung, Darstellung mit Themen
- Doku mit Bildern, GitHub-Anleitung, Demo-Inhalte und Werkzeuge zum Neu-Erzeugen der Bilder

**Geändert**
- Erststart aus Quelltext: `settings.json` entsteht aus `settings.template.json`
- Vorlagen-Generator (`make_templates.py`) übernimmt keine Dashboard-Tokens und Geräte-IDs mehr
- Build-Skripte und Tests arbeiten relativ zum Repository (keine festen Pfade)

**Basis**
- Aufbauend auf Soul of Waifu 2.5.x von jofizcd (GPL-3.0), siehe `NOTICE.md`.
