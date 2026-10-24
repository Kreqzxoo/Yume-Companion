# Soul of Waifu 2.5.1 – Erweiterter Patch (Deutsch)

Dieses Paket erweitert den Quellcode von Soul of Waifu 2.5.1. Es ist ein Community-/Nutzer-Patch und keine offizielle Veröffentlichung des ursprünglichen Projektautors.

## Enthaltene Verbesserungen

- **Remote-LLM im Hauptprogramm:** In `Options → API & Providers` lassen sich Remote-Endpunkt, Modell-ID und optionaler API-Token speichern und testen. Unter `Local LLM execution target` kann man bestehende Charaktere mit der Gesprächsmethode `Local LLM` zwischen lokalem llama.cpp und einem Remote-Server umschalten. Der explizite Provider `Remote LLM` kann außerdem pro Charakter gewählt werden.
- **Ollama / llama.cpp:** Der Remote-Server muss eine OpenAI-kompatible `/v1`-API anbieten. Beispiele: `http://<LLM-PC-IP>:11434/v1` für Ollama oder `http://<LLM-PC-IP>:8080/v1` für llama.cpp. Die tatsächliche IP und Modell-ID sind deine Werte.
- **Halbduplex-Anti-Echo:** Während der TTS-Wiedergabe und einer konfigurierbaren Nachlaufzeit werden Mikrofonsegmente verworfen. Dadurch sollte Whisper die eigene Ausgabe nicht an den Assistenten zurückmelden. Der Nachteil: Man kann die KI nicht gleichzeitig während ihrer Ausgabe unterbrechen.
- **Konfigurierbares Wake-Word:** Beliebige durch Komma oder Semikolon getrennte Phrasen, etwa `Alexa, Hey Jarvis, Yume`. Erkennung erfolgt nach der Whisper-Transkription. Dies ist kein eigenständiger, extrem schneller Hotword-Detektor.
- **GPU-Zuweisung:** Whisper kann eine CUDA-GPU oder CPU nutzen; für den lokalen llama.cpp-Unterprozess kann man `CUDA_VISIBLE_DEVICES` einschränken; Qwen3-TTS kann pro Charakter einer GPU zugewiesen werden. Das Remote-LLM nutzt die GPU-Einstellung auf dem Remote-PC.
- **Flüssigere Sprache:** Kürzeres Standard-VAD-Stillefenster (760 ms), Audio-Vorlauf zur Vermeidung abgeschnittener Anfangslaute, konfigurierbare TTS-Segmentlänge und Pausen, Wortgrenzen beim Aufteilen langer Texte, weiche Lippensynchronisation und ein Streaming-Lebenszyklus, der den Gesprächszustand nicht zwischen TTS-Segmenten voreilig auf „fertig“ setzt.
- **Qwen3-TTS-Einstellungen:** GPU, Tokenlimit, Temperatur, Top-p, maximale Zeichen pro Segment, Pause zwischen Segmenten und zusätzliche Stille am Ende eines Segments sind per Charakter einstellbar.
- **Soul of Waifu Studio:** Eigenständiges kleines Zusatzwerkzeug für Anti-Echo/Wake-Word, Audio-/GPU-Werte, Logo, Titel, zusätzliche Credits und deutsche Übersetzungen.
- **Deutsch:** Die neue `de.yaml` enthält alle 1.657 Schlüssel aus der englischen Vorlage. 1.342 Werte unterscheiden sich vom englischen Ausgangstext. Das bedeutet **nicht**, dass jeder Text fachlich geprüft übersetzt ist: Unverändert bleiben unter anderem Eigennamen, Modellnamen und einige noch nicht lokalisierte Texte. In SOW Studio kann man identische englische Einträge filtern, durchsuchen und korrigieren.

## Sichere Installation als Overlay-Patch

1. Soul of Waifu beenden.
2. Den kompletten Installationsordner sichern. Mindestens sichern: `app/configuration`, `app/translations`, `app/characters` bzw. die Ordner, in denen du eigene Figuren/Daten hältst.
3. `Soul-of-Waifu-v2.5.1-Enhanced-Patch.zip` **in den bestehenden Soul-of-Waifu-Ordner** entpacken und Dateistruktur zusammenführen lassen.
4. Die vorhandenen Dateien überschreiben. Das Patch enthält absichtlich **keine** `app/configuration/settings.json`, `app/configuration/api.json` oder `app/configuration/branding.json`, um deine persönlichen Einstellungen, API-Schlüssel und Branding-Daten zu erhalten.
5. Mit dem gewohnten `start.bat` starten.
6. In `Options → API & Providers` URL und Modell für `Remote LLM` eintragen und den Verbindungstest verwenden. Anschließend den gewünschten lokalen Ausführungsweg wählen.
7. `tools\SOW-Studio.bat` starten, um Wake-Word, Halbduplex-Schutz, GPU-Zuweisung, Logo/Credits und Übersetzungen zu bearbeiten. Die Anwendung vor dem Speichern schließen und danach neu starten.

## GPU-Zuweisung richtig verstehen

- **Whisper:** `cuda` plus GPU-Index oder `cpu`. CUDA-Indizes hängen von der Geräte-Reihenfolge ab, die PyTorch/CUDA meldet. Erst mit `nvidia-smi` und einem Test verifizieren.
- **Qwen3-TTS:** Die GPU wird pro Charakter gewählt; beim Wechsel des TTS-Geräts/-Modells kann ein Neustart erforderlich sein. Ein Modell, das zu groß für die ausgewählte Karte ist, kann weiterhin fehlschlagen oder auf CPU zurückfallen.
- **Lokales llama.cpp:** SOW Studio setzt die Variable `CUDA_VISIBLE_DEVICES` nur beim lokalen CUDA-Backend-Prozess. Welche Layer tatsächlich ausgelagert werden und wie mehrere Karten aufgeteilt werden, hängt weiterhin von der verwendeten llama.cpp-Version und deren Backend-/Split-Parametern ab.
- **Remote-LLM:** Wähle die GPU auf dem zweiten PC aus, zum Beispiel über Ollama oder die Startparameter von llama.cpp. Ein Client auf dem ersten PC kann die GPU des Remote-PCs nicht direkt zuweisen.
- **Animationen / Live2D / VRM:** Das sind Renderprozesse der Grafik-Engine, nicht automatisch CUDA-Workloads. Du kannst sie unter Windows über `Einstellungen → System → Bildschirm → Grafik` der bevorzugten GPU zuweisen; es gibt keine verlässliche gemeinsame CUDA-Index-Steuerung mit Whisper/TTS.

## Anti-Echo und Wake-Word – wichtige Grenzen

Der Schutz blockiert während der eigenen TTS-Ausgabe die erfassten Mikrofonsegmente und hält diese Sperre für die eingestellte Nachlaufzeit aufrecht. Das ist ein pragmatischer **Halbduplex-Schutz**, keine akustische Echounterdrückung (AEC). Der Mikrofonpfad wird weiterhin geöffnet, das Audio wird aber nicht verarbeitet. Für gleichzeitiges Sprechen/Unterbrechen braucht es eine Audio-Engine mit AEC und ein geeignetes Wiedergabe-Referenzsignal.

Das Wake-Word wird anhand des von Whisper erkannten Textes geprüft. Die Erkennung ist dadurch flexibel und benötigt kein zusätzliches Wake-Word-Modell, verursacht aber weiter Transkriptionsaufwand und kann sich in lauten Umgebungen oder bei ähnlich klingenden Wörtern irren.

## Qwen3-TTS: sinnvolle Startwerte bei abgeschnittenen Sätzen

- Max. Zeichen pro Segment: zunächst **220–280**.
- Pause zwischen Segmenten: **120–200 ms**.
- Stille am Segmentende: **100–250 ms**.
- Maximale neue Tokens: zunächst **1500**; bei abgebrochenen Enden kann ein höherer Wert helfen, kostet aber Speicher und Laufzeit.
- VAD-Stillefenster: etwa **650–900 ms**; zu niedrige Werte schneiden natürliche Sprechpausen ab, zu hohe Werte erhöhen die Latenz.

Die optimalen Werte hängen von Qwen-Modellgröße, Sprache, GPU-Speicher, Stimmkonfiguration und Satzlänge ab.

## Noch nicht umgesetzt / zu beachten

- Kein automatischer Wechsel zurück auf das lokale Modell, wenn Remote-Ollama/llama.cpp ausfällt.
- Kein echtes Vollduplex-AEC und keine interruption-fähige Duplex-Sprachpipeline.
- Wake-Word ist transcriptbasiert, kein separater Hotword-Detektor.
- Kein garantiertes dediziertes GPU-Routing für Live2D/VRM-Animationen innerhalb der App.
- Keine vollständige Laufzeitprüfung auf Windows mit echter GPU, Audiointerface und Remote-Server in dieser Umgebung. Python-Syntax, JSON/YAML und Kernlogik-Smoke-Tests wurden geprüft; die GUI und Audio-Generierung müssen auf deinem PC validiert werden.
- Die deutsche Übersetzung ist deutlich erweitert, aber nicht professionell lektoriert oder zu 100 % inhaltlich angepasst. Das Studio erleichtert den restlichen Korrekturdurchlauf.

## Datenschutz und Lizenz

Keine API-Schlüssel oder individuellen Konfigurationen sind im Overlay-Patch enthalten. Bewahre die Original-Lizenz- und Copyright-Angaben des Projekts auf. Die Branding-Funktion fügt zusätzliche Credits hinzu; sie ersetzt oder entfernt nicht die ursprünglichen Credits.
