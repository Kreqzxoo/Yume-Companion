# Soul of Waifu v2.5.3 – Release- und Upgradehinweise (DE)

## Enthaltene Integrationen

- Remote LLM über OpenAI-kompatible API (z. B. Ollama oder llama.cpp auf einem anderen Rechner).
- Home Assistant REST-Integration mit optionaler Entitäten-Freigabeliste und Bestätigung für Steueraktionen.
- Tool Calling/MCP mit optionaler Bestätigung externer Tool-Aufrufe.
- AI-Service-/Geräte-Zuweisung für die vorhandenen LLM-/Whisper-/TTS-/Qwen-Komponenten, soweit der jeweilige Backend-Pfad dies unterstützt.
- Konfigurierbare Audio-Parameter, segmentierte TTS-Ausgabe, Wakeword-Prüfung über Whisper-Transkript und Halbduplex-Echo-Schutz. Der AEC-Reparatur-Nachtrag fuer diese 2.5.3-Neuausgabe integriert WebRTC AEC3; fehlende Laufzeitdateien koennen beim Start nachinstalliert werden. Der Halbduplex-Modus bleibt als Fallback verfügbar.
- Android Connector: lokale WLAN-URL, externe HTTPS-Domain, token-geschützte Bootstrap-Route, WebSocket/Weboberfläche mit Chat und Charakteransichten sowie Server-Steuerung direkt im Android-Connector-Tab.
- Android-Quellprojekt unter `android/SoulOfWaifuAndroid`, einschließlich Assistenten-Rollen-Integration und experimentellem Wakeword-Dienst.
- SOW Studio/Branding-Dateien aus dem bisherigen erweiterten Quellstand.
- Avatar-Bildquellen werden normalisiert statt ein Dictionary direkt an `QPixmap` zu geben; Chat-Generierungsfehler werden sichtbarer protokolliert.
- Einmalige Settings-Migration erhöht Kontextgrößen unter 8192 auf 8192, damit ältere Installationen nicht mit zu kleinem Kontext am Systemprompt scheitern. Alte AEC-Einstellungen bleiben erhalten; der Starttest prueft die AEC3-Laufzeit und aktiviert bei Fehlern den Halbduplex-Fallback, ohne andere persoenliche Einstellungen zu ersetzen.

## Android-Webserver starten

Nach Installation: Soul of Waifu starten → Einstellungen → Android Connector → **Webserver starten**. Standard-Port ist 8000. Auf demselben PC `http://127.0.0.1:8000` testen; vom Handy im selben WLAN `http://PC-IP:8000`. Für Zugriff über `https://yume.example.com` muss der Cloudflare Tunnel tatsächlich auf diesen Rechner und Port zeigen und der Ursprungsdienst erreichbar sein. Ein Cloudflare-Fehler 523 bedeutet, dass Cloudflare den Origin nicht erreicht, nicht dass das LLM-Modell fehlt.

In Android Connector SSID exakt eintragen, lokale URL und HTTPS-Domain setzen, Token nur auf eigenen Geräten nutzen. `settings.json`, `api.json` und `characters.json` werden beim inkrementellen Update nicht ersetzt.

## Update von Original 2.5.1

1. Soul of Waifu schließen.
2. Den Ordner des bestehenden Projekts sichern.
3. `Soul-of-Waifu-v2.5.3-Update-from-2.5.1.zip` entpacken.
4. `install_update.bat` ausführen und den Ordner auswählen, in dem `main.py` liegt. Das Skript legt eine Sicherung aller überschriebenen Dateien im Projektordner an.
5. Danach mit `start.bat` starten. Das Update kopiert keine persönlichen API-/Charakter-/Einstellungsdateien.

## Wichtige Grenzen / Prüfstatus

- Der Android-Teil ist Quellcode, keine beigefügte installierbare APK. Aus dem Projekt lässt sich unter Windows mit Android SDK/Gradle eine APK bauen. Ein vollständiger Geräte-/APK-Test wurde in der Erstellungsumgebung nicht durchgeführt.
- Android Assistant Role ist vorbereitet. Das Wakeword nutzt die Android-Spracherkennung als experimentellen Prototyp und ist kein systemprivilegiertes, energieeffizientes „Hey Google“-Äquivalent; HyperOS kann den Hintergrunddienst beschränken.
- WebRTC AEC3 wird in diesem Reparaturpaket ueber pywebrtc-audio eingebunden; die Echoqualitaet muss auf dem Zielsystem getestet werden. Wakeword in der Desktop-App ist transkriptbasiert und kein dedizierter Low-Power-Hotword-Detektor.
- Kein automatischer Fallback vom ausgefallenen Remote-LLM auf Local LLM.
- Integrationen, GPU-Zuweisungen, Home Assistant, externe MCP-Server, Audio-Hardware und Tunnel müssen nach dem Update in der eigenen Umgebung getestet werden.


## AEC-Reparaturpaket fuer v2.5.3 (gleiche Versionsnummer)

- Stellt `Install-AEC-Dependency.bat` im Hauptordner wieder her.
- Prueft WebRTC AEC3 beim Start und bietet Installation/Reparatur in exakt der von `start.bat` genutzten Python-Umgebung an.
- Fuegt in Einstellungen -> Conversation & Audio Status, Installation/Pruefung und aktive AEC3-Einstellungen hinzu.
- Integriert `pywebrtc-audio==0.2.0` in Mikrofonverarbeitung und referenzbewusste Lautsprecherwiedergabe.
- Bei nicht verfuegbarer Bibliothek oder Laufzeitfehler bleibt Halbduplex als sicherer Fallback aktiv.
- Audiolatenz und Rauschunterdrueckung sind konfigurierbar; Aenderungen gelten beim Neustart des Sprachmodus.

AEC-Status wird per Import-, Initialisierungs- und Pufferverarbeitungstest ermittelt. Die tatsaechliche Echoqualitaet muss nach Installation mit den verwendeten Lautsprechern, dem Mikrofon und der Raumakustik getestet werden.

## AEC-Reparaturupdate – gleiche Versionsnummer 2.5.3

- Stellt `Install-AEC-Dependency.bat` als Datei im SoW-Hauptordner wieder her.
- Prüft Installation, native Initialisierung und Pufferverarbeitung bei jedem App-Start; wenn nötig, fragt SoW nach, ob es die Abhängigkeit in der tatsächlich laufenden Python-Umgebung installieren soll. Eine zuvor in einem älteren 2.5.3-Paket gespeicherte Ablehnung wird für diese Reparatur einmalig erneut abgefragt.
- Unter **Einstellungen → Conversation & Audio** stehen Status, erneuter Installations-/Prüfknopf, AEC-Verzögerung und Rauschunterdrückung zur Verfügung.
- Verwendet `pywebrtc-audio==0.2.0` für den Mikrofonpfad und referenzierte Lautsprecherwiedergabe. Bei fehlender Bibliothek oder Laufzeitfehler schaltet SoW sicher auf Halbduplex um.
- Die Version bleibt **2.5.3**. Das Update kann über die Originalversion 2.5.1 oder über das frühere 2.5.3-Update installiert werden.
- Echoqualität wurde nicht auf dem Zielrechner getestet und hängt von Audiogeräten, Treibern, Latenz und Raumakustik ab.


## Backup & Wiederherstellung (Reparaturstand 2.5.3)

- Wiederhergestellter Einstellungsbereich **Einstellungen → Backup & Wiederherstellung**.
- ZIP-Backup der Einstellungen, API-Konfiguration, Charaktere/Chats, SoW-Daten und gecachten Avatare.
- Optionale Sicherung großer Modell-, Stimmen- und Asset-Ordner.
- Import von ZIP-Backups ohne Manifest aus v2.5.1 sowie von älteren Backup-Ordnern mit `app/configuration`.
- Vor jeder Wiederherstellung automatische Sicherung des aktuellen Zustands; Importvalidierung und Schutz gegen unsichere ZIP-Pfade.
- Migration alter Einstellungsdateien auf das 2.5.3-Schema unter Beibehaltung vorhandener Benutzerfelder.
