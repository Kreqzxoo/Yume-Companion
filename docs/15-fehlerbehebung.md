# 15 Fehlerbehebung

Zuerst immer: **Protokoll ansehen.** Das Konsolenfenster beim Start zeigt es live; zusätzlich liegt jede Sitzung in `logs\sow_<Datum>_<Zeit>.log`, die Installation in `logs\installer.log`. Das **Dashboard** ([Kapitel 13](13-web-und-dashboard.md)) hat einen **Selbsttest**, der in Klartext sagt, was fehlt.

> Protokolle können Pfade und Computernamen enthalten. Vor dem Teilen (z. B. in einem GitHub-Issue) lesen und Namen schwärzen.

## Installation und Start

| Problem | Ursache und Lösung |
| --- | --- |
| **„Data folder was not found“** beim `installer.bat` | Der Ordner `app\data` (Miniconda) fehlt. Bei Quelltext-Installation zuerst `tools\setup_from_source.bat` ausführen, nicht direkt `installer.bat` |
| Installation bricht mit Fehlern bei einzelnen Paketen ab | Die fehlgeschlagenen Teile stehen am Ende und in `logs\installer.log`. Meist hilft ein erneuter Lauf (Netzwerk). FlashAttention-2 ist optional |
| PyTorch-Download bricht ab | Der Installer wiederholt automatisch und wartet länger; bei sehr langsamen Leitungen später erneut starten |
| **Installer als Administrator gestartet** | nicht tun; ändert Arbeitsverzeichnis und Pfade. Normal starten |
| Absturz beim Start mit `ModuleNotFoundError` | Pakete fehlen: `installer.bat` erneut ausführen |
| Absturz beim Start, Meldung zu `settings.json` / `NoneType` | `settings.json` ist beschädigt oder zu alt. Datei umbenennen, die App erzeugt sie neu aus `settings.template.json` (Backup vorher!) |
| „FFmpeg …“ Fehler in `start.bat` | `app\ffmpeg\bin\ffmpeg.exe` fehlt (bei Quelltext-Installation `tools\setup_from_source.bat`) |
| Fehlermeldung zu Einbettungsmodell / Gefühlserkennung | `app\utils\e5-small-en-ru` bzw. `app\utils\emotions\detector` fehlen: `app\data\envs\sow\python.exe tools\fetch_models.py` |
| OneDrive/Pfad mit Leerzeichen oder Sonderzeichen | Programm in einen kurzen, einfachen Pfad (z. B. `C:\Yume`) installieren |
| Fenster bleibt leer / sehr langsam | Grafiktreiber aktualisieren; *Windows-Einstellungen → System → Anzeige → Grafik*: der App die schnelle GPU geben |

## Sprachmodell

| Problem | Lösung |
| --- | --- |
| **Keine Antwort / Fehler 400, „Kontext zu klein“** | *Kontextgröße* in *Sprachmodell & APIs* auf mindestens 8192 stellen (der System-Prompt braucht Platz) |
| Lokales Modell lädt nicht („Modell fehlt VRAM“) | kleineres Modell oder Quantisierung (Q4_K_M), weniger **GPU-Layer**, kleinerer Kontext, KV-Cache `q8_0`; sonst CPU |
| Sehr langsame Antworten | Modell passt nicht in den VRAM (teils im RAM). Kleineres Modell, Flash Attention an, Reasoning-Modus aus, kürzere Maximallänge |
| Seltsame Sonderzeichen-Ausgaben (z. B. „im_end“) | falsche **Chat-Vorlage**: statt *Auto* z. B. ChatML oder Llama-3 erzwingen |
| Charakter schreibt für dich mit | **Stopp-Zeichenfolgen** setzen (`\nUser:`) |
| **Remote-Server nicht erreichbar** | läuft `llama-server` dort mit `--host 0.0.0.0`? Firewall-Regel? Gleiche Netz? IP richtig? Port stimmt? Beim Yume LLM Server: Status grün, *Firewall prüfen* |
| Remote-Server antwortet, aber „Modell nicht aufgeführt“ | exakte Modell-ID aus `/v1/models` verwenden (Ollama: Name und Tag) |
| Cloud: „401 / ungültiger Schlüssel“ | Schlüssel neu kopieren (ohne Leerzeichen), richtiger Anbieter gewählt? |
| Nach Wechsel auf entfernten PC antworten Charaktere nicht | *KI-Dienste → LLM-Ausführungsziel* und Verbindungstest prüfen; es gibt keinen automatischen Rückfall auf lokal |

## Stimme und Ohren

| Problem | Lösung |
| --- | --- |
| Keine Stimme | dem Charakter eine **Stimme zuweisen**; beim ersten Start einer lokalen Engine werden Modelle geladen (Konsole beobachten) |
| Stimme bricht am Satzende ab (Qwen3-TTS) | *Maximale Zeichen pro Segment* 220–280, *Stille am Ende* 100–250 ms, *maximale neue Tokens* ≥ 1500 |
| Der Charakter hört sich selbst | **Echo-Schutz**: *Halbduplex* oder **WebRTC AEC3**; Status prüfen („AEC3 erneut prüfen“), Referenzverzögerung testen |
| Mikrofon wird nicht erkannt / falsches Gerät | *System & Benutzeroberfläche → Audiogeräte* |
| Wake-Word reagiert zu oft/zu selten | andere Phrasen (kurze, eindeutige Namen), Whisper-Gerät, Stille-Einstellungen; ist transkriptbasiert und kein Spezial-Detektor |
| Live2D/VRM lädt „ewig“ | kurz warten und nicht schließen; *Yume-System* muss aktiv sein; Live2D nur **.moc3** |
| Kein Ausdrucksbild für ein Gefühl | Dateiname muss exakt dem Gefühl entsprechen (`joy.png`); es fehlt sonst `neutral.png` |

## Handy und Netzwerk

| Problem | Lösung |
| --- | --- |
| Handy koppelt nicht (kein Kontakt) | Webserver am PC **gestartet**? Windows-Firewall freigegeben (*Android Connector*)? Gleiches WLAN? **Gast-WLAN/WLAN-Isolation** und **VPN am Handy** blockieren |
| QR-Code abgelaufen | er gilt nur wenige Minuten und einmal; **Neuen QR-Code erzeugen** |
| Verbindung nur im Heimnetz | externe HTTPS-Domain (z. B. Cloudflare Tunnel) einrichten und am Handy eintragen |
| Cloudflare **Fehler 523** | der Tunnel erreicht deinen PC nicht (Dienst/Port/Tunnel prüfen), nicht ein Modellproblem |
| Handy findet PC nicht (Mobilfunk) | *Lokal bevorzugen* aus, externe Domain eintragen, ggf. Wake-on-LAN |
| Wake Word am Handy reagiert nicht im Hintergrund | Batterie-Optimierung für die App ausnehmen; manche Hersteller (z. B. HyperOS) beschränken Hintergrunddienste; Mikrofon-Dienst nur aus sichtbarer App startbar |
| Handy-Steuerung funktioniert nicht | *Bedienungshilfen*-Dienst und *Benachrichtigungszugriff* der App einschalten; Hauptschalter *Steuerung erlauben* |
| Offline-Modell stürzt ab | Die App markiert es als „abgestürzt“; kleineres Modell wählen (Qwen 0,5 B) |

## Integrationen

| Problem | Lösung |
| --- | --- |
| Spotify steuert nichts | **Premium** nötig; Redirect-URI exakt wie angezeigt eingetragen; neu anmelden |
| Home Assistant antwortet nicht | URL vom PC aus erreichbar (Host-Adresse, nicht Docker-Bridge), Token gültig, bei Steuerbefehlen Entität in der Liste |
| Mail-Anmeldung abgelehnt | **App-Passwort** statt Hauptpasswort (Gmail: IMAP aktivieren) |
| Kalender zeigt nichts | iCal-Link (geheime Adresse) prüfen; ICS ist schreibgeschützt |
| Bildgenerierung schlägt fehl | Dienst (A1111/Forge mit `--api --listen`, ComfyUI `--listen`) erreichbar? Genügend VRAM (LLM + Bild gleichzeitig)? |
| Discord-Bot antwortet nicht | Token richtig, Bot auf dem Server, Intents im Entwicklerportal an |

## Zurücksetzen und Hilfe holen

* **Einstellungen zurücksetzen:** `app\configuration\settings.json` umbenennen. Beim nächsten Start entsteht sie aus der sauberen Vorlage.
* **Alles neu, Charaktere behalten:** `settings.json` löschen, `characters.json` und `.soul` behalten.
* **Fehler melden:** als Issue auf GitHub mit Version (`VERSION.txt`), Windows-Version, Grafikkarte, Beschreibung, Schritten und gekürztem Protokoll (ohne Namen/Schlüssel).
