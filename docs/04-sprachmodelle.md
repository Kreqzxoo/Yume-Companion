# 04 Sprachmodelle

Das Sprachmodell („LLM“) schreibt die Antworten deiner Charaktere. Yume Companion kann es **auf diesem PC**, **auf einem zweiten PC im Heimnetz** oder **bei einem Cloud-Anbieter** laufen lassen. Du wählst den Weg pro Charakter ([Konversationsmethode](03-chat-und-charaktere.md#konversationsmethode-anbieter-pro-charakter)) und kannst ihn global umschalten.

## 4.1 Überblick der drei Wege

| Weg | Vorteil | Nachteil |
| --- | --- | --- |
| **Lokal** (llama.cpp in der App) | privat, offline, kostenlos | braucht Grafikkarte/RAM; große Modelle sind langsam |
| **Anderer PC** (Remote LLM, z. B. [Yume LLM Server](12-llm-server.md), Ollama, llama.cpp) | starke Hardware ausgelagert, PC bleibt frei | zweiter Rechner im selben Netz nötig |
| **Cloud** (OpenAI, Anthropic, Gemini, DeepSeek, Grok, Qwen, Z.AI, Mistral, OpenRouter, Player2, eigener Endpunkt) | sehr gute Modelle, keine Hardware | Kosten, Nachrichten gehen zum Anbieter |

## 4.2 Einstellungen → Sprachmodell & APIs

Die Seite ist in Karten gegliedert (von oben nach unten):

![Sprachmodell & APIs, ganze Seite](images/pc/optionen_02_llm_voll.png)

### Anbieter (lokal oder Cloud-API)
Wähle den **Anbieter** und trage Zugangsdaten ein: API-Schlüssel (bei Mistral/OpenAI/OpenRouter/Anthropic/Gemini/DeepSeek/Grok/Qwen/Z.AI), optional eine **eigene Endpunkt-URL** (für OpenAI-kompatible Dienste) und das **Modell**. Die Schlüssel stehen nur in `app/configuration/api.json` auf deinem PC. Bei **Player2** brauchst du keinen Schlüssel, nur die geöffnete Player2-App.

### Wo läuft das Sprachmodell?
Zwei große Schaltflächen:

* **Auf diesem PC**: Yume startet llama.cpp selbst.
* **Auf einem anderen PC im Netzwerk**: llama.cpp oder Ollama läuft dort. Du trägst die **IP-Adresse** ein (oder klickst **Netzwerk automatisch durchsuchen**), testest die Verbindung, wählst das **Modell auf dem Server** (wird nach dem Test erkannt) und gibst bei Bedarf den **Zugangsschlüssel** ein.
* **Server-Installer speichern …** legt den Installer des [Yume LLM Servers](12-llm-server.md) auf einen USB-Stick oder Netzwerkordner, um den zweiten PC einzurichten.
* Optional sucht die App **alle 5 Minuten (oder beim Start)** im Netz nach LLM-Servern und meldet gefundene.

Beim Umschalten auf den entfernten PC werden alle Charaktere mit „Lokales LLM“ automatisch umgestellt und ein laufender lokaler Server beendet (gibt VRAM frei). Der Status zeigt *Remote-Modell geladen und bereit* oder *Remote-Server nicht erreichbar – läuft llama-server dort mit `--host 0.0.0.0`?*. Es gibt **keinen automatischen Rückfall** auf lokal, wenn der entfernte Server ausfällt.

> **Sicherheit:** Ollama- und llama.cpp-Server haben oft keinen Login. Gib sie nie ins offene Internet frei, sondern nur im vertrauenswürdigen LAN (Firewall).

Beispiele für die Adresse: Ollama `http://HOST:11434/v1`, llama.cpp `http://HOST:8080/v1`. Die Schnittstelle muss OpenAI-kompatibel sein (`/v1/chat/completions`, `/v1/models`).

### Vorlage (Presets)
Speichert und wechselt komplette Schnappschüsse deiner Generierungs- und Sampling-Einstellungen (z. B. „Dense 8B RP“, „MoE 30B schnell“): *Speichern*, *Neues Preset*, *Umbenennen*, *Löschen*, *Zurücksetzen* (stellt Temperatur, Top-P, Kontext, Max-Tokens und Strafen auf Standard).

### Schnellvorlagen
Ein Klick stellt Kontext, Antwortlänge, Denktiefe, Sprach-Blöcke und Bildgröße passend zu deiner Hardware ein. Die App erkennt deine Grafikkarte:

| Vorlage | Kontext | Antwortlänge | Zweck |
| --- | --- | --- | --- |
| Schnell | 8.192 | 1.024 Tokens | schwache Hardware, kurze Antworten |
| Ausgewogen (★ empfohlen) | 16.384 | 2.048 Tokens | Alltag, guter Mix |
| Beste Qualität | 16.384 | 4.096 Tokens | starke Grafikkarte, lange Antworten |

### Allgemeine Generierungsparameter

| Parameter | Bedeutung |
| --- | --- |
| Maximale Tokenanzahl | wie lang eine Antwort höchstens wird (empfohlen 300–500 für Chat) |
| Reasoning-Aufwand | Denktiefe bei Cloud-Reasoning-Modellen (Aus, Niedrig, Mittel, Hoch) |
| Temperatur | Kreativität; 0,8–1,0 ist ein guter Bereich fürs Rollenspiel |
| Top-P | alter Filter; auf 1,0 stellen, wenn du Min-P nutzt |
| Häufigkeits- und Präsenzstrafe | gegen Wortwiederholungen bzw. für Themenwechsel (0,0–0,5) |

### Hardware und Backend (lokal)

| Einstellung | Bedeutung |
| --- | --- |
| Server-Endpunkt | Adresse des internen llama.cpp-Servers (z. B. `http://localhost:48596/v1`) |
| Rechenkonfiguration | **CPU** oder **GPU**, Backend **CUDA (NVIDIA)**, **Vulkan**, **HIP (AMD)** oder **SYCL (Intel)**. Mit **Aktualisieren** lädst du neue llama.cpp-Binärdateien (siehe 4.5) |
| KV-Cache-Typ | quantisiert den Kontext-Cache und spart bei langem Kontext viel VRAM |
| MLock / No-MMAP | Modell fest im RAM halten bzw. komplett vorab laden |
| Flash Attention | schneller und sparsamer bei langen Gesprächen |
| Denk-/Reasoning-Modus | `<think>`-Ausgaben von Reasoning-Modellen verarbeiten |
| GPU-Layer | wie viele Schichten auf der Grafikkarte laufen (99 = alle) |
| CPU-MoE-Schichten | wie viele Mixture-of-Experts-Schichten im RAM bleiben (für riesige MoE-Modelle) |
| Kontextgröße | Arbeitsgedächtnis in Tokens; mehr = mehr VRAM |
| Prompt-Batchgröße / CPU-Threads | Tempo beim Verarbeiten des Prompts bzw. auf der CPU (0 = automatisch) |
| Eigene Argumente | Kommandozeilen-Flags direkt an llama.cpp (z. B. `--rope-freq-base 10000`) |

### Prompting und Formatierung
* **Chat-Vorlage:** *Auto* liest die Vorlage aus der GGUF-Datei; bei seltsamen Ausgaben wie `<|im_end|>` erzwingst du z. B. ChatML oder Llama-3.
* **Stopp-Zeichenfolgen:** Abbruchwörter (z. B. `\nUser:`, `</s>`).
* **Nur normalen, gesprochenen Text generieren:** Die KI antwortet ohne *Handlungen* und Beschreibungen. Das macht Antworten kürzer und schneller (gilt für alle Charaktere; praktisch für Sprache).

### Erweitertes Sampling (lokal)
Aktivierbar mit **Erweitertes Sampling aktivieren**; sonst gelten die normalen Parameter.

| Sampler | Wirkung |
| --- | --- |
| **Min-P** | schneidet unsinnige Wörter dynamisch ab (empfohlen 0,05–0,10 bei Top-P = 1,0) |
| **Dynamische Temperatur** (Min/Max) | Temperatur schwankt je nach Sicherheit des Modells |
| **XTC** (Wahrscheinlichkeit, Schwelle) | entfernt gezielt Klischee-Wörter („Schauer liefen mir über den Rücken“) |
| **DRY** (Multiplikator, Basis, erlaubte Länge) | bestraft ganze wiederholte Satzfolgen |

## 4.3 Modelle (lokal)

Seitenleiste → **Modelle**:

![Modelle-Hub](images/pc/seite_6_modelshub.png)

* **Empfehlungen:** kuratierte Liste mit Kompatibilitätsangabe für deine Hardware (bezogen auf Q4).
* **Beliebt:** aktuell beliebte GGUF-Modelle von Hugging Face.
* **Meine Modelle:** Modelle im lokalen Ordner (`assets/local_llm`), mit **Modell laden / entladen**, **Als Standard festlegen**, **Löschen**. **Ordner öffnen** und **Verzeichnis ändern** wechseln den Speicherort.
* **Herunterladen:** Quantisierung wählen (empfohlen Q4_K_M oder Q5_K_M), Fortschritt und **Stopp**. Abgebrochene Downloads werden aufgeräumt.
* Beim Laden zeigt die App die Schritte *Engine initialisieren → GGUF prüfen → Tensoren laden → Kontext zuweisen → Modell bereit*.

## 4.4 Vision

**Einstellungen → Vision-KI.** Ein kleines, separates Vision-Modell beschreibt Bilder (Chat-Anhänge, Discord-Bilder). So können auch reine Text-Modelle mit Bildern arbeiten.

![Vision-KI](images/pc/optionen_03_vision.png)

* **Plugin aktivieren**; Modus *Nur wenn das Chat-Modell keine Bilder versteht* (Standard) oder *Immer*.
* **Vision-Modell** wählen und **Herunterladen und installieren** (z. B. Qwen2.5-VL 3B) oder ein eigenes GGUF samt *mmproj*-Datei angeben.
* **Automatisch beenden nach** N Minuten Leerlauf (gibt GPU-Speicher frei), **Bildgröße** (längste Seite).
* Gerät/GPU über *KI-Dienste*; **Anweisung** an das Vision-Modell anpassen; **Mit einem Bild testen**; Modell jetzt laden/beenden.
* **Auf einem anderen PC** (Remote-Vision): Adresse des Vision-Servers eintragen, z. B. vom Yume LLM Server (Port + 1).
* Das Werkzeug *Screenshot analysieren* (Bildschirm „sehen“, siehe [Kapitel 09](09-werkzeuge-und-integrationen.md)) braucht ein bildfähiges Modell; der Anbieter des Charakters muss Bilder verstehen oder das Vision-Plugin muss aktiv sein.

## 4.5 KI-Dienste und GPU-Zuweisung

**Einstellungen → KI-Dienste** verteilt die Rechenarbeit zentral:

![KI-Dienste](images/pc/optionen_07_ai_services.png)

* **LLM-Ausführungsziel:** *Dieser PC – lokales llama.cpp* oder *Entfernter PC – Ollama / llama.cpp*; **Entfernten PC einrichten** springt zur Netzwerk-Karte.
* **Whisper-Gerät** (CPU oder CUDA-GPU) und **-GPU**: Spracherkennung.
* **Standardgerät/-GPU für lokale TTS**: Sprachsynthese (Qwen3-TTS u. a.). Pro Charakter lässt sich das überschreiben.
* **Vision-Gerät/-GPU**, **Sprachmodell (lokal): GPUs** (mehrere möglich, Indizes aus deiner Liste).
* **Werkzeug-Modelle:** Qwen3 4B (schnell), Qwen3 8B (empfohlen, Browser-Agent), Qwen3 14B (Planung), Qwen2.5-Coder 7B (Code) – GPU je Modell wählbar.
* **GPU-Liste aktualisieren**. Live2D/VRM-Rendering nutzt die Windows-Grafikzuweisung (*Windows-Einstellungen → System → Anzeige → Grafik*), nicht diese Seite.

> GPU-Nummern gelten pro Prozess. Nach Änderungen den lokalen LLM-Server bzw. den Sprachmodus neu starten.

### llama.cpp-Updater
In der Karte *Hardware und Backend* zeigt **Aktuelle Version** den Stand der Engine. **Jetzt aktualisieren** lädt die neuesten llama.cpp-Binärdateien für das gewählte Backend (GitHub), **Zurücksetzen** stellt die vorherige Version wieder her, **Neu installieren** repariert eine kaputte Engine.

## 4.6 Werkzeug-Modell extern

Ein zweites, kleines Modell kann **entscheiden, welches Werkzeug mit welchen Argumenten** gebraucht wird, während das Chat-Modell die Antwort schreibt. Das macht Werkzeugaufrufe zuverlässiger und schneller. Einstellen unter **Werkzeugaufrufe & MCP → Werkzeug-Modell extern** (Adresse z. B. vom Yume LLM Server, Port + 3). Ist der Server aus, übernimmt das Chat-Modell zwei Minuten lang selbst.

## 4.7 Gespräch & Emotionen

**Einstellungen → Gespräch & Audio** (obere Karte) ergänzt die Charakter-Persönlichkeit, ersetzt sie aber nicht:

* **Natürlichere Gesprächsführung**, **Emotionen über mehrere Antworten konsistent halten**, **Wiederholte Begrüßungen und Floskeln vermeiden**.
* **Gesprächsstil:** Natürlich/ausgewogen, Warm und persönlich, Kurz und direkt, Locker und spontan.
* **Emotionale Ausdrucksstärke:** 0–100 %.

![Gespräch und Audio](images/pc/optionen_08_conversation_audio.png)

## 4.8 Fehlermeldungen in Klartext

Technische LLM- und Netzwerkfehler werden in kurze deutsche Sätze übersetzt, z. B. wenn der Kontext zu klein ist („aktuell 8192 Tokens“) oder der Server nicht erreichbar ist, mit einem Hinweis, was zu tun ist.
