# Soul of Waifu 2.5.1 – Jarvis-Erweiterung

Dieses Paket baut auf der erweiterten SoW-2.5.1-Quellversion auf. Es ergänzt die vorhandene Remote-LLM- und Audio-Konfiguration um Home Assistant, eine gemeinsame Werkzeug-Zentrale und die Anbindung des vorhandenen MCP-Clients an den normalen Chat.

## Installation – Overlay-Patch

1. Soul of Waifu vollständig beenden.
2. Den gesamten aktuellen Soul-of-Waifu-Ordner sichern. Am einfachsten den Ordner kopieren und die Sicherung nicht überschreiben.
3. `Soul-of-Waifu-v2.5.1-Jarvis-Update-Patch.zip` in den **bestehenden Projektordner entpacken**, in dem `main.py` liegt. Ordner zusammenführen und die enthaltenen Dateien überschreiben lassen.
4. Vorhandene `app/configuration/settings.json`, `api.json`, `characters.json` und `branding.json` nicht ersetzen. Sie sind im Patch absichtlich nicht enthalten.
5. Über `start.bat` wie gewohnt starten. Falls beim Start eine Python-Fehlermeldung erscheint, das Log sichern und die Sicherung wiederherstellen, statt weitere Dateien auf Verdacht zu überschreiben.

Das alternative Archiv `Soul-of-Waifu-v2.5.1-Jarvis-Enhanced-Source.zip` ist eine vollständige, separate Quellcodekopie. Es ist für einen Test in einem eigenen Verzeichnis gedacht – **nicht** als Overlay über die bestehende Installation.

## Neue Einstellungsbereiche

### 1. Home Assistant

- Unter `Options → Home Assistant` die Integration aktivieren.
- Als Adresse den aus Sicht des Windows-PCs erreichbaren Host und veröffentlichten Port verwenden. Für Home Assistant in einem Unraid-Docker-Container ist das meistens zum Beispiel `http://192.168.1.20:8123`, sofern `8123` am Unraid-Host veröffentlicht ist. Ein interner Docker-Bridge-IP-Bereich wie `172.17.x.x` ist von einem anderen Rechner in der Regel nicht direkt erreichbar.
- In Home Assistant ein persönliches Long-Lived Access Token erstellen und in Soul of Waifu einfügen.
- `Verbindung testen` drücken.
- Für reine Statusabfragen genügt die aktivierte Integration. Für Steuerung zusätzlich `Steuerbefehle erlauben` aktivieren und konkrete Entitäten eintragen, eine pro Zeile, z. B. `light.wohnzimmer` oder `switch.serverrack`.
- Die Integration bietet nur definierte Dienste für Licht, Schalter, Helfer, Lüfter, Szenen, Klima, Abdeckungen und Media Player. Schlösser, Alarmanlagen, allgemeine Skripte und beliebige Service-Daten sind absichtlich nicht freigegeben.

### 2. Werkzeuge & Plugins

Unter `Options → Tools & Plugins` kannst du Chat-Werkzeugnutzung und einzelne Funktionen freigeben:

- Websuche (sofern die installierte Suchabhängigkeit erreichbar ist)
- Websites im Standardbrowser öffnen (nur `http://` oder `https://`, keine lokalen Datei-URLs)
- Systeminformationen/Datum und Uhrzeit
- optional Text aus der Zwischenablage lesen
- freigegebene Windows-Programme starten

Für Programme wird eine Liste im Format `Name | absoluter Pfad` verwendet, jeweils eine pro Zeile, z. B.:

```text
Editor | C:\Windows\System32\notepad.exe
```

Jeder Programmstart verlangt eine Bestätigung. Es werden keine freien Shell-Befehle oder vom Modell gelieferten Argumente ausgeführt. Die Zwischenablage ist standardmäßig deaktiviert.

**Datenschutz:** Werkzeugergebnisse werden dem ausgewählten LLM als Kontext übergeben. Bei einem Cloud-LLM können Informationen deshalb den Cloud-Anbieter erreichen. Aktiviere Zwischenablage und sensible Werkzeuge nur bewusst; für private Home-Assistant-Zustände und Systemdaten möglichst ein lokales oder vertrauenswürdiges Modell verwenden.

### 3. Tool Calling & MCP

Der vorhandene MCP-Client ist mit dem Chat-Werkzeug-Router verbunden. Aktiviere `MCP Proxy Integration`, gib die URL eines vertrauenswürdigen MCP-Servers ein und verwende `MCP-Verbindung testen`, um die angebotenen Werkzeuge zu prüfen.

- Chat-Werkzeugnutzung muss ebenfalls aktiviert sein, damit die KI Tools im normalen Chat aufruft.
- Externe MCP-Werkzeugaufrufe verlangen standardmäßig pro Aufruf eine Bestätigung. Nur bei einem Server, dem du vollständig vertraust, sollte diese Abfrage deaktiviert werden.
- MCP-Server können mehr Rechte haben als der SoW-eigene Home-Assistant-Connector. Prüfe die Fähigkeiten und Berechtigungen des Servers vor dem Verbinden.
- Den MCP-Endpunkt nicht ohne Authentifizierung/Netzwerkschutz ins öffentliche Internet stellen.

### 4. KI-Dienste & GPU-Zuweisung

Unter `Options → AI Services` kannst du zentral konfigurieren:

- LLM-Ziel: lokaler llama.cpp-Server oder Remote-Ollama/llama.cpp
- Whisper: CPU oder eine auswählbare CUDA-GPU
- Qwen3-TTS: Standard-GPU; eine explizite GPU-Zuweisung pro Charakter hat Vorrang
- lokaler llama.cpp: eine oder mehrere CUDA-GPU-Indizes

Die Remote-URL, optionale Authentifizierung und Modell-ID bleiben zentral unter `Options → API & Providers → Remote LLM`; über die Schaltfläche auf der KI-Diensteseite gelangst du direkt dorthin.

Beispiele für OpenAI-kompatible Endpunkte:

- Ollama: `http://<LLM-PC-IP>:11434/v1`
- llama.cpp Server: `http://<LLM-PC-IP>:8080/v1`

Die konkreten Dienste müssen auf dem Remote-PC für den Zugriff aus dem vertrauenswürdigen LAN konfiguriert und per Firewall eingeschränkt sein. Insbesondere ungeschützte Ollama-/llama.cpp-Endpunkte nicht ins Internet exponieren. Whisper, Qwen-TTS und die SoW-Oberfläche bleiben lokal; nur die LLM-Textgenerierung wird ausgelagert.

CUDA-Indizes beziehen sich auf die Sicht des jeweiligen Prozesses. Nach GPU-Änderungen den lokalen LLM-Server bzw. den Sprachmodus neu starten. Live2D-/VRM-Rendering ist kein gewöhnlicher separater CUDA-Worker; die bevorzugte GPU dafür wird unter Windows in den Grafikeinstellungen festgelegt.

### 5. Gespräch & Audio

Unter `Options → Conversation & Audio` findest du Gesprächsstil, emotionale Ausdrucksstärke, Kontinuität und das Vermeiden wiederholter Floskeln. Diese Einstellungen ergänzen die Charakterpersönlichkeit; sie ersetzen keine Persona-, Szenario- oder Lorebook-Instruktionen.

Audioeinstellungen umfassen Wake-Word, Halbduplex-Echo-Schutz, Echo-Nachlauf, Whisper-Satzende/Stille, Audio-Vorlauf, maximale TTS-Textlänge pro Segment, Segmentpause und Lip-Sync-Glättung.

- Wake-Word ist in dieser Version **transkriptbasiert**: Whisper erkennt erst Sprache, anschließend wird geprüft, ob die konfigurierte Phrase enthalten war. Es ist kein dedizierter, stromsparender Wake-Word-Detektor.
- Der eingebaute Echo-Schutz ist **Halbduplex**, keine echte akustische Echounterdrückung (AEC). Während SoW spricht, ignoriert der Mikrofonpfad Audioframes samt Nachlauf. Gleichzeitiges Sprechen und Unterbrechen benötigt später eine AEC-fähige Audiopipeline.
- Die meisten Audioparameter werden beim Start des Sprachmodus geladen. Nach Änderungen den Sprachmodus beenden und wieder starten.
- In der Qwen3-TTS-Charakterkonfiguration gibt es zusätzliche Parameter wie maximale Tokens, Temperatur, Top-p und Stille am Segmentende. Bei abgeschnittenen Enden zuerst Segmentlänge und Stille am Ende moderat erhöhen, dann mit der Zwischen-Segment-Pause experimentieren.

## Tests und bekannte Grenzen

In der Entwicklungsumgebung wurden die Python-Syntax aller Module, JSON-Konfigurationen, YAML-Übersetzungen, Home-Assistant-URL-/Entitäten-Validierung, erlaubte und verbotene Home-Assistant-Dienstaufrufe sowie die HTTP(S)-URL-Validierung automatisiert geprüft.

Nicht möglich war hier ein vollständiger Windows-GUI-Lauf mit echten Audiogeräten, GPUs, Soul-of-Waifu-Modellen, einem laufenden Home-Assistant-Container und einem echten MCP-/Remote-LLM-Server. Darum bitte vor dem produktiven Einsatz einen Backup-Zweig verwenden und Integrationen einzeln testen. Es gibt weiterhin keinen automatischen Rückfall auf lokal, falls ein Remote-LLM ausfällt.

## Dateien und Privatsphäre

Der Overlay-Patch enthält keine persönliche SoW-Einstellungsdatei, API-Tokens, Charakterdatei oder Branding-Konfiguration. Home-Assistant- und andere API-Tokens werden in den bestehenden lokalen Konfigurationsdateien gespeichert. Diese Dateien nicht öffentlich teilen.

Die originale Lizenz sowie bestehende Projekt-Credits bleiben im Quellcode erhalten. Das optionale Branding-Werkzeug kann zusätzliche Logos/Angaben konfigurieren, soll aber keine ursprünglichen Copyright-Hinweise entfernen.
