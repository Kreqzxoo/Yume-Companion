# Yume Companion

**Deine KI-Begleiterin für Windows und Android.** Chatten, telefonieren, Avatare, Gedächtnis, Rollenspiel-Bühne, Organizer und Smart-Home-Steuerung – lokal auf deinem PC, mit eigenen oder Cloud-Sprachmodellen.

[English summary below](#english-summary)

![Yume Companion – Chat](docs/images/pc/chat_yume.png)

> **Status:** 3.0.0 **Beta**. Vieles funktioniert, manches ist noch rau. Fehler bitte als [Issue](../../issues) melden.
> **Herkunft:** Yume Companion ist eine stark erweiterte, veränderte Fassung von [**Soul of Waifu**](https://github.com/jofizcd/Soul-of-Waifu) von *jofizcd* (GPL-3.0). Der Original-Autor bleibt genannt, siehe [NOTICE.md](NOTICE.md). Dieses Projekt ist **nicht** das offizielle Soul of Waifu.

---

## Inhalt

* [Was ist Yume Companion?](#was-ist-yume-companion)
* [Die Bausteine](#die-bausteine)
* [Schnellstart](#schnellstart)
* [Funktionen im Überblick](#funktionen-im-überblick)
* [Die Dokumentation](#die-dokumentation)
* [Systemvoraussetzungen](#systemvoraussetzungen)
* [Datenschutz](#datenschutz)
* [Lizenz und Danksagung](#lizenz-und-danksagung)
* [English summary](#english-summary)

---

## Was ist Yume Companion?

Yume Companion ist eine Windows-Anwendung, in der KI-Charaktere sich an dich erinnern und über mehrere Wege erreichbar sind:

* 💬 **Text- und Sprachchat** mit Charakteren: Avatare als Bilder, Live2D oder 3D (VRM), Stimme per Sprachsynthese, Spracheingabe, Lorebooks, Werkzeuge.
* 🧠 **Gedächtnis** („Yume-Gedächtnis“): Der Charakter merkt sich Fakten, Gefühle und führt ein Tagebuch.
* 🎲 **Yume-Bühne**: Textabenteuer mit KI-Spielleiter, Würfelproben, Inventar, Nebenfiguren und mehreren Charakteren.
* 🖥️ **Desktop-Begleiter**: Eine Figur auf deinem Desktop mit Stimmungsmodell, Bildschirm-Sicht und Werkzeugen.
* 📅 **Organizer**: Kalender, Mails (nur lesen), Erinnerungen, Listen, Morgen-Briefing, Pendelzeit, Geburtstage, Wissensdatenbank, Briefe und Rechnungen.
* 📱 **Android-App**: Chat, Anrufe mit Wake Word, 3D-Avatar, Handy-Steuerung durch die KI, Wecker, Auto- und Wandmodus, Offline-Notfallmodus.
* 🖧 **Yume LLM Server**: macht einen zweiten PC zum KI-Server für Sprache, Bilder, Vision und Werkzeuge.

## Die Bausteine

![Die Bausteine](docs/images/diagramme/architektur.svg)

| Baustein | Ordner | Beschreibung |
| --- | --- | --- |
| PC-App | `app/`, `main.py` | Python, PyQt6. Die eigentliche Anwendung. |
| Android-App | `android/` | Kotlin, Jetpack Compose. Verbindet sich mit dem PC. |
| Yume LLM Server | `llm-server/` | Kleines Windows-Programm (C#), startet llama.cpp auf einem zweiten PC. |
| Release-Werkzeuge | `updater/`, `rebrand/` | Setup bauen, Name und Logo ändern. |
| Tests | `tests/` | Tests für den Organizer, Sprache, Werkzeuge u. a. |
| Dokumentation | `docs/` | Diese Anleitung mit Bildern. |

## Schnellstart

1. Lade unter [**Releases**](../../releases) das neueste `Yume-Companion-Setup-….exe` herunter und führe es aus. Es richtet Python, PyTorch und alle Pakete ein (ca. 10 GB nach der Installation).
2. Starte **Yume Companion**. Auf der Startseite erscheinen drei Schritte: **Modell wählen → Charakter erstellen → Chatten**.
3. Für das erste Gespräch brauchst du ein Sprachmodell. Am einfachsten:
   * **Cloud:** *Einstellungen → Sprachmodell & APIs* → Anbieter wählen → API-Schlüssel eintragen.
   * **Lokal:** *Modelle* → ein Modell (z. B. Qwen3 8B, Quantisierung Q4_K_M) herunterladen → **Modell laden**.
4. Beispiel-Charaktere erzeugst du mit `tools/demo/make_demo_content.py` oder legst eigene unter *Charakter erstellen* an.

Ausführlich: [Installation](docs/01-installation.md) · [Erste Schritte](docs/02-erste-schritte.md)

## Funktionen im Überblick

| Bereich | Was du bekommst | Anleitung |
| --- | --- | --- |
| **Charaktere** | Editor, KI-Assistent, Karten importieren/exportieren, Ordner, Galerie, Personas, System-Prompts, Lorebooks, Variablen | [Charaktere und Chat](docs/03-chat-und-charaktere.md) |
| **Sprachmodelle** | Lokal (llama.cpp), Remote-PC, 10+ Cloud-Anbieter, Modell-Hub, Presets, Sampling | [Sprachmodelle](docs/04-sprachmodelle.md) |
| **Stimme und Avatare** | 6 Sprach-Engines, RVC, Spracheingabe, Wake Word, Echo-Entfernung, Bilder/Live2D/VRM | [Stimme und Avatare](docs/05-stimme-und-avatare.md) |
| **Gedächtnis** | 4 Modi, Archiv, Tagebuch, automatische Zusammenfassungen | [Gedächtnis](docs/06-gedaechtnis.md) |
| **Yume-Bühne** | KI-Spielleiter, Würfel, Inventar, Kampagnen, Nebenfiguren | [Yume-Bühne](docs/07-yume-buehne.md) |
| **Desktop-Begleiter** | Schwebende Figur, Hormon-Modell, Schnellaktionen | [Desktop-Begleiter](docs/08-desktop-begleiter.md) |
| **Werkzeuge** | Websuche, Browser-Agent, PC-Steuerung, Code, Dateien, MCP, Home Assistant, Spotify, Discord, Bildgenerierung | [Werkzeuge und Integrationen](docs/09-werkzeuge-und-integrationen.md) |
| **Organizer** | Kalender, Mail, Listen, Routinen, Pendeln, Personen, Wissensbasis, Dokumente, Skills | [Organizer](docs/10-organizer.md) |
| **Android** | Chat, Anruf, Wake Word, 3D-Avatar, Handy-Steuerung, Wecker, Modi | [Android-App](docs/11-android-app.md) |
| **LLM-Server** | Zweiter PC als KI-Server | [Yume LLM Server](docs/12-llm-server.md) |
| **Web** | Webclient, Dashboard, Schnittstellen | [Web und Dashboard](docs/13-web-und-dashboard.md) |
| **Sicherheit** | Backups, Updates, Berechtigungen, Datenschutz | [Backup, Updates, Sicherheit](docs/14-backup-updates-sicherheit.md) |

## Die Dokumentation

Alles liegt in [`docs/`](docs/INDEX.md): Installation, alle Funktionen mit Bildern, Fehlerbehebung, Entwicklung und die [**Anleitung zum Veröffentlichen auf GitHub**](docs/GITHUB_ANLEITUNG.md).

## Systemvoraussetzungen

| | Minimum | Empfohlen |
| --- | --- | --- |
| System | Windows 10/11 (64 Bit) | Windows 11 |
| RAM | 8 GB | 16 GB oder mehr |
| Grafikkarte | beliebig (nur Cloud-Modelle) | NVIDIA oder AMD mit 8 GB+ VRAM für lokale Modelle |
| Speicher | 15 GB frei | schnelle NVMe-SSD, 40 GB+ für Modelle |
| Handy | Android 9+ (API 28) | Android 12+ (Kamera, Mikrofon, WLAN) |

## Datenschutz

* Charaktere, Chats, Gedächtnis, Einstellungen und Organizer-Daten bleiben auf deinem PC. Passwörter (Mail, Spotify) werden mit der Windows-Datenschutz-Funktion verschlüsselt gespeichert.
* Lokale Modelle senden nichts ins Internet. Mit Cloud-Anbietern (OpenAI, Anthropic, Gemini …) gehen die Chat-Texte an diesen Anbieter.
* Die App holt aus dem Netz nur, was du nutzt: Modelle von Hugging Face, Charakterkarten aus der Galerie, Wetter (Open-Meteo), Orte und Routen (OpenStreetMap), Spotify, und Update-Infos von GitHub.
* Weitere Hinweise: [Backup, Updates, Sicherheit](docs/14-backup-updates-sicherheit.md).

## Lizenz und Danksagung

* Lizenz: **GNU General Public License v3.0** (siehe [LICENSE](LICENSE)). Der Quelltext darf unter diesen Bedingungen genutzt, verändert und weitergegeben werden.
* Original: **Soul of Waifu** von jofizcd – <https://github.com/jofizcd/Soul-of-Waifu>, Dokumentation: <https://jofizcd.github.io/soul-of-waifu-site/docs/>.
* Verwendete Komponenten und ihre Lizenzen: [docs/LIZENZEN_UND_UPLOAD.md](docs/LIZENZEN_UND_UPLOAD.md).
* Die Beispiel-Charaktere und ihre Bilder in diesem Repository sind selbst erstellt und frei verwendbar.

---

## English summary

**Yume Companion** is a Windows desktop app (Python/PyQt6) for AI characters with memory, voice, avatars (images, Live2D, VRM), a role-play stage with an AI game master, a desktop companion, an organizer (calendar, mail, lists, routines), and an Android companion app (Kotlin) that can chat, call, and control the phone. The separate **Yume LLM Server** turns a second PC into a llama.cpp server for language, vision, image and tool models.

It is a heavily modified fork of [Soul of Waifu](https://github.com/jofizcd/Soul-of-Waifu) by jofizcd (GPL-3.0) and is licensed under **GPL-3.0** as well. The documentation in `docs/` is written in German, with screenshots of every screen.

**Quick start:** download the latest setup from [Releases](../../releases), run it, start the app, pick a model (cloud API key or a local GGUF model from the *Modelle* page), create a character and chat. Build from source: see [docs/16-entwicklung.md](docs/16-entwicklung.md).
