# Lizenzen und Upload-Checkliste (Yume Companion)

Stand: 18.10.2026. Das ist eine technische Zusammenstellung aus den Lizenzangaben der Projekte, **keine Rechtsberatung**.
Bei kommerzieller Nutzung oder Unsicherheit bitte selbst gegenprüfen oder fachlich beraten lassen.

## 1. Die Lizenz deines Projekts: GPL-3.0

Das Original **Soul of Waifu** (jofizcd/Soul-of-Waifu) steht unter der **GNU General Public License v3.0**.
Yume Companion ist eine veränderte Fassung davon. Die GPL ist eine Copyleft-Lizenz, deshalb gilt:

| Pflicht | Was das für dich heißt |
|---|---|
| Gleiche Lizenz | Dein Projekt (der PC-Teil, abgeleitet vom Original) muss ebenfalls **GPL-3.0** sein. Eine andere Lizenz (MIT, Apache, "alle Rechte vorbehalten", Nur-nicht-kommerziell) ist **nicht erlaubt**. |
| Lizenztext | `LICENSE` (GPL-3.0) liegt im Hauptordner. |
| Urheber nennen | Die Hinweise auf den Original-Autor (jofizcd) müssen bleiben: `NOTICE.md`, Über-Dialog / "Made by". Im Rebrander darfst du Namen und Logo ändern, aber den Urheber nicht entfernen, wenn du hochlädst. |
| Änderungen kennzeichnen | `NOTICE.md` nennt, dass und wann das Projekt verändert wurde (GPL §5a). Am besten zusätzlich eine saubere Git-Historie. |
| Quelltext bereitstellen | Wer die App (oder die APK / Installer) von dir bekommt, muss den passenden Quelltext bekommen. GitHub-Repo mit gleichem Stand wie die Release-Dateien genügt. |
| Keine Zusatzbeschränkungen | Du darfst keine Bedingungen draufsetzen, die die GPL einschränken (z. B. "nur privat"). |
| Name / Marke | Die GPL gibt dir keine Namens- oder Markenrechte am Original. "Yume Companion" ist ein eigener Name, das ist in Ordnung. Nicht den Eindruck erwecken, es sei das offizielle Soul of Waifu. |

**Garantien:** Keine. Der übliche GPL-Hinweis "ohne jede Gewährleistung" steht in `NOTICE.md` / `LICENSE`.

## 2. Deine eigenen Teile

| Teil | Empfehlung |
|---|---|
| PC-App (Yume Companion, abgeleitet) | **GPL-3.0** (Pflicht, siehe oben) |
| Android-App (`Yume Android`) | Eigener Code, **proprietär: Copyright (c) 2026 Kreqzxoo, alle Rechte vorbehalten** (`android/LICENSE`, Drittkomponenten in `android/THIRD_PARTY.md` und in der App). Die 3D-Avatar-Seite wurde von Grund auf neu geschrieben (die frühere Seite enthielt Code aus Soul of Waifu und musste dafür ersetzt werden). Die App ist ein eigenständiges Programm und spricht nur über das Netzwerk mit der GPL-PC-App. Die MIT-Bibliotheken (three.js, three-vrm) erlauben die proprietäre Nutzung, solange ihre Hinweise mitgeliefert werden (`assets/THIRD_PARTY_NOTICES.txt`). |
| Yume LLM Server (C#) | Eigener Code, **proprietär: Copyright (c) 2026 Kreqzxoo, alle Rechte vorbehalten** (`llm-server/LICENSE`, Drittkomponenten in `llm-server/THIRD_PARTY.md`). Er lädt llama.cpp / stable-diffusion.cpp (MIT) zur Laufzeit nach. Er ist ein eigenständiges Programm ohne Code von Soul of Waifu und kommuniziert nur über das Netzwerk mit der GPL-PC-App. |
| Yume Updater / SoW-Rebrand | Eigene Hilfsprogramme. Der Rebrander liest `branding.py` des GPL-Projekts nur (führt es nicht aus). Freie Wahl, GPL-3.0 passt zum Rest. |

Wichtig: Der Code der Android-App wurde mit KI-Unterstützung geschrieben. Das ist erlaubt. Die Rechte daran
liegen bei dir als Nutzer, die Lizenz legst du fest.

## 3. Software von Dritten

### Im Projekt / vom Projekt verwendet

| Komponente | Lizenz | Hinweis |
|---|---|---|
| PyQt6 / Qt WebEngine | **GPL-3.0** (oder kommerziell) | Passt zu einem GPL-3.0-Projekt. Wer das Projekt später **nicht** unter GPL veröffentlichen wollte, bräuchte eine kommerzielle Qt-Lizenz. Bei GPL-3.0 kein Problem. |
| coqui-tts (Fork) | MPL-2.0 | OK. **XTTS-v2 Modell: Coqui Public Model License (nur nicht-kommerziell)**. Das Modell wird nicht mitgeliefert, nur vom Nutzer geladen. |
| Qwen3-TTS (Code + Modelle) | Apache-2.0 | OK |
| Kokoro | Apache-2.0 | espeak-ng (über espeakng-loader) ist GPL-3.0, passt. |
| Silero TTS Modelle | in der Repo-Lizenz nicht eindeutig ("Other") | Modelle nicht mitliefern, nur vom Nutzer laden lassen. **Vor Nutzung die Bedingungen von Silero prüfen.** |
| Silero VAD | MIT | OK (Lizenzdatei liegt im Ordner) |
| edge-tts | LGPL-3.0 (laut Projektseite) | OK, wird als Bibliothek genutzt. Der Dienst gehört Microsoft; nicht für Dauerbetrieb Dritter missbrauchen. |
| ElevenLabs Python SDK | MIT | Der Dienst selbst hat eigene Nutzungsbedingungen (API-Key des Nutzers). |
| faster-whisper | MIT | Whisper-Modelle: MIT |
| rvc-python / RVC | MIT | Die RVC-**Stimmmodelle** (`.pth`) sind eigene Daten, siehe Abschnitt 4. |
| fairseq | MIT | |
| discord.py | MIT | Discord-Nutzungsbedingungen beachten (Bot-Token des Nutzers). |
| live2d-py | MIT, **enthält Live2D Cubism Core (proprietär)** | Die Cubism-Komponenten stehen unter der **Live2D-Lizenz** (Software License / Cubism SDK Release License). Wird es (wie das Original) nur als pip-Paket installiert und nicht von dir ins Repo gelegt, entsteht für dich keine eigene Weitergabe. Nicht in das Repo legen. |
| three.js / three-vrm (Webmodule) | MIT | Lizenzkommentar in den Dateien lassen. |
| ffmpeg (`app/ffmpeg`) | GPL-3.0 / LGPL, je nach Build | Binärdateien **nicht** ins Repo (wie beim Original), nur Link / Download beim Installieren. |
| llama.cpp, stable-diffusion.cpp | MIT | Werden vom LLM Server / App nachgeladen |
| Schriften Comfortaa, Inter Tight | SIL OFL 1.1 | Dürfen weitergegeben werden; Lizenztext mitliefern. Das Original liefert sie nicht im Repo, `app/font` kann ignoriert werden. |

### Android-App

| Komponente | Lizenz |
|---|---|
| Jetpack Compose, AndroidX, CameraX | Apache-2.0 |
| OkHttp | Apache-2.0 |
| Vosk (Android) + Sprachmodelle + Sprecher-Modell | Apache-2.0 (Modelle von Alpha Cephei) |
| MediaPipe Tasks GenAI | Apache-2.0 |
| ML Kit Barcode Scanning | Google ML Kit Nutzungsbedingungen (Bibliothek frei nutzbar, kein Open-Source-Code) |
| three.js / three-vrm im Avatar-Fenster | MIT |
| JNA | Apache-2.0 / LGPL-2.1 |
| Offline-KI-Modelle (Gemma o. ä.) | Eigene Modell-Lizenz (Gemma Terms of Use). Werden nicht mitgeliefert. |

Apache-2.0-Software darf in GPL-3.0-Projekten verwendet werden.

## 4. Was **nicht** ins öffentliche Repo darf

### Geheimnisse und persönliche Daten (immer ausschließen)
- `app/configuration/api.json` (API-Schlüssel, Bot-Token), `settings.json` (u. a. `web_auth_token`), `characters.json`, `characters/`
- `android_devices.json` (Geräte-Tokens), `logs/`, `Backups/` (`*.sowpack`), `app/data/.soul` (Gedächtnis), `app/cache`
- Sicherungskopien von Charakterdateien wie `characters_*_backup.json` (private Chats)
- die Pfade in Logs und Konfiguration verraten Benutzername und Netzwerk (z. B. IP-Adressen)

### Fremde Inhalte, deren Weitergabe du nicht erlauben kannst
| Datei / Ordner | Grund |
|---|---|
| `assets/emotions/vrm/1648710486258542243.vrm` (Zero Two) | Modell von **Sayurii** (VRoid Hub), Lizenz laut Datei: "Other", **kommerzielle Nutzung nicht erlaubt**, Namensnennung nötig, Veränderung nicht erlaubt (die Weitergabe ist nach dem VRoid-Hub-Link erlaubt, aber nur mit Bedingungen). Charakter ist urheberrechtlich geschützt (Darling in the FranXX). **Nicht hochladen.** |
| `Anime Girl.vrm`, `Anime Man.vrm` | VRoid-Studio-Beispielavatare „AvatarSample_Y/Z“ des **pixiv VRoid Project** (VRM Public License 1.0): Weitergabe und Veränderung erlaubt, Namensnennung nicht nötig. Liegen im Repo und sind in `NOTICE.md` genannt (Lizenz steht in den Metadaten der Dateien). |
| `assets/emotions/live2d/Hiyori` | Live2D-**Beispielmodell** (Free Material License von Live2D): Weitergabe nur nach deren Bedingungen. Das Original liefert es nicht im Repo. Nicht hochladen. |
| `assets/rvc_models/zerotwo/*` und `assets/voice_refs/*` | Eine nachgebaute **Stimme einer realen Synchronsprecherin** (und Ausschnitte aus Serien-Audio). Urheber- und Persönlichkeitsrechte. **Nicht hochladen, nicht weitergeben.** |
| `RVC Zero Two/Mp4` (Serienfolgen) | Urheberrechtlich geschützt. Niemals hochladen. |
| `Zero Two.json` (Lorebook, Charakterkarte) und die Zero-Two-Charakterdaten | Figur und Inhalte stammen aus einer geschützten Serie. Dein eigener Text darin gehört dir, die Figur nicht. Besser nicht im öffentlichen Repo. |
| `assets/ambient/*` (78 MB), `assets/backgrounds/*` (16 MB) | Herkunft nicht bekannt, im Original-Repo nur `.gitkeep`. Nur mit eigener Quelle / freier Lizenz (z. B. CC0). |
| `app/utils/emotions/vrm/expressions/*.fbx` (28 Animationen) | Vermutlich **Mixamo**-Animationen: für eigene Projekte nutzbar, aber **nicht als Dateien weitergeben**. Im Original-Repo nicht enthalten, daher auch hier **nicht im Quelltext** (`.gitignore`). Im fertigen Setup sind sie als Teil der Anwendung enthalten (nötig für die Körperbewegungen); Herkunft und Bedingungen vor einer Veröffentlichung klären oder die Dateien beim Setup-Bau ausschließen. |
| `app/voices/*.wav` | Herkunft unklar, im Original nur `.gitkeep` |
| `assets/vision_models` (2,6 GB), `assets/local_llm`, `app/models/hf_cache` | Sehr groß (GitHub-Limit 100 MB pro Datei) und eigene Modell-Lizenzen (z. B. Qwen2.5-VL 3B unter "Qwen Research License"). Nutzer laden sie selbst. |
| `app/data/` (Python-Umgebung, ~11 GB) | Wird vom Installer erzeugt |
| `tools/android/*.apk`, `tools/server/*.exe` | Gebaute Dateien. Besser als **Release-Datei** (GitHub Releases) statt im Quelltext. |

Die vorbereitete `.gitignore` schließt das alles aus. Sie ist nur eine Hilfe: vor dem ersten Push die Dateiliste
mit `git status` / `git ls-files` durchsehen.

## 5. Kurze Checkliste für den Upload

1. Neues, **sauberes** Git-Repo anlegen (nicht den ganzen Ordner mit Verlauf kopieren).
2. `LICENSE` (GPL-3.0) und `NOTICE.md` im Hauptordner lassen; Lizenz bei GitHub auf "GPL-3.0" stellen.
3. `.gitignore` aktivieren, `git status` prüfen: keine `api.json`, keine Chats, keine `.vrm` / `.pth` / `.wav` von Zero Two.
4. Im README die Herkunft nennen: "Basierend auf Soul of Waifu von jofizcd (GPL-3.0)" mit Link.
5. APK und Installer als Release anhängen, mit dem Hinweis auf den passenden Quelltext-Stand.
6. Für Stimmen / Charaktere nur eigene oder frei lizenzierte Inhalte als Beispiel mitgeben.
7. Optional: Das Original-Projekt kurz informieren (höflich, nicht Pflicht).

## 6. Ergänzungen (Stand dieser Veröffentlichungs-Fassung)

| Thema | Hinweis |
| --- | --- |
| **Logo und Charakterbild der Marke** (`assets/custom_branding/*.png`, Android-Platzhalterbild unter `android/app/src/main/res/drawable-nodpi`) | Diese Bilder sind in der App und auf den Screenshots sichtbar. **Du musst die Rechte daran haben** (selbst gezeichnet, selbst mit einer KI erzeugt unter Bedingungen, die Weitergabe erlauben, oder frei lizenziert). Ist die Herkunft unklar, ersetze sie vor dem Upload mit dem Rebrand-Programm durch eigene Bilder und mache die Screenshots neu |
| **Beispiel-Charaktere** (Yume, Mika, Kai) | erfunden, Bilder in `tools/demo/make_demo_content.py` selbst gezeichnet: frei verwendbar |
| **Schriften** `app/font` (Comfortaa, Inter Tight) | SIL OFL 1.1, liegen im Repo mit Hinweisdatei |
| **Einbettungsmodell** `d0rj/e5-small-en-ru` und **Gefühlserkennung** `joeddav/distilbert-base-uncased-go-emotions-student` | beide MIT-lizenziert; nicht im Repo (zu groß), `tools/fetch_models.py` lädt sie von Hugging Face |
| **FFmpeg** | wird beim Einrichten aus dem Quelltext von gyan.dev geladen (GPL-Build), nicht im Repo |
| **XTTS-Referenzstimmen** `app/voices/*.wav` | Herkunft unklar, nicht im Repo; lege eigene Aufnahmen ab |
| **Skripte, Tests, Doku** | eigener Code, GPL-3.0 (siehe Abschnitt 2) |
| **Android-App** (`android/`) | eigener Code, proprietär, alle Rechte vorbehalten (`android/LICENSE`); Ausnahme von der GPL des übrigen Repositorys |
| **LLM-Server** (`llm-server/`) | eigener Code, proprietär, alle Rechte vorbehalten (`llm-server/LICENSE`); Ausnahme von der GPL des übrigen Repositorys |
| **Screenshots** `docs/images` | aus der App mit Demo-Daten erzeugt; Benutzernamen und Pfade werden ersetzt. Vor dem Upload trotzdem ansehen |
| **Release-Vorlagen** (`updater/installer_build/templates`) | enthalten **keine** Tokens mehr (`dashboard_token` wurde geleert); Vorlagen-Generator ergänzt |
