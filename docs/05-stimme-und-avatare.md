# 05 Stimme und Avatare

Dieses Kapitel erklärt, wie dein Charakter **spricht**, wie er dich **hört** und wie er **aussieht**.

## 5.1 Das Yume-System einschalten

Avatare, Anrufe und Zusatzmodule laufen im **Yume-System** (der erweiterte Modus). Einschalten unter **Einstellungen → Visualisierung → Yume-System aktivieren**. Fehlt später im Charaktermenü der Knopf für Gesichtsausdrücke, ist dieses Modul ausgeschaltet.

![Visualisierung](images/pc/optionen_15_visualization.png)

Auf dieser Seite findest du außerdem:

| Einstellung | Bedeutung |
| --- | --- |
| **Modus** | *Yume-System* (Anruf als Vollbild-Fenster mit Avatar) oder *Yume-Desktop-Begleiter* (schwebende Figur auf dem Desktop, [Kapitel 08](08-desktop-begleiter.md)) |
| **Bildrate** | 30, 60 oder 120 FPS für Live2D/VRM |
| **Modellhintergrund** | *Farbe* (Schwarz, Tiefblau, Bordeaux, Dunkelgrün, Zartviolett, Warmes Kohlegrau) oder *Bild* |
| **Natürliche Bewegung (VRM)** | Atmen und Kopfbewegung, Blinzelhäufigkeit, Gefühle weich mischen, **Augenkontakt** (der Avatar schaut in die Kamera), **Ganzkörper-Animationen zu Gefühlen**, kleine **Idle-Gesten** (Kopf anfassen, Haare richten, strecken), *Stärke der Gefühle*, *Gefühl halten, dann entspannen*. Pro Charakter einstellbar unter Charaktereinstellungen → Visualisierung |

## 5.2 Sprachausgabe (TTS)

Pro Charakter wählst du die Stimme: Kachel → **Spracheinstellungen** (Mikrofon-Symbol).

![Charakterstimme](images/pc/dialog_stimme.png)

| Engine | Art | Hinweise |
| --- | --- | --- |
| **ElevenLabs** | Cloud | eigener API-Schlüssel und Voice-ID |
| **XTTSv2** | lokal | Sprechermodell *Männlich*, *Weiblich*, *Weiblich, ruhig*. Die Referenzstimmen sind kurze Aufnahmen `male.wav`, `female.wav`, `calm_female.wav` in `app/voices` (im Repository nicht enthalten: eigene, frei nutzbare Aufnahmen dort ablegen) |
| **Edge TTS** | Cloud (Microsoft, ohne Schlüssel) | Sprache und Stimme wählen |
| **Kokoro** (82M) | lokal | leicht, viele Stimmen |
| **Silero (RU)** | lokal | russische Stimmen |
| **Qwen-3 TTS** | lokal | beste Qualität, Details unten |

Beim **ersten Start** einer lokalen Engine lädt das Programm die Modelle automatisch (Fortschritt in der Konsole). Danach funktioniert die Sprache offline.

Die Seiten der einzelnen Engines:

| ElevenLabs | XTTSv2 | Edge TTS |
| --- | --- | --- |
| ![ElevenLabs](images/pc/dialog_stimme_elevenlabs.png) | ![XTTSv2](images/pc/dialog_stimme_xtts.png) | ![Edge TTS](images/pc/dialog_stimme_edge.png) |

| Kokoro | Silero (RU) |
| --- | --- |
| ![Kokoro](images/pc/dialog_stimme_kokoro.png) | ![Silero](images/pc/dialog_stimme_silero.png) |

![Qwen3-TTS-Konfiguration](images/pc/dialog_stimme_qwen3.png)

### Qwen3-TTS im Detail
* **Modellgröße**, **Sprache**, **Rechengerät** (*Standard* folgt den KI-Diensten; eigene CPU-/GPU-Wahl gilt nur für diesen Charakter).
* **Generierungsmodus:** *Preset Voices* (fertige Stimmen; sprechen Deutsch mit leichtem Akzent), *Voice Design* (Stimme auf Englisch beschreiben, auch fertige deutsche Beschreibungen) und *Voice Cloning* (Referenz-WAV und Wortlaut der Aufnahme).
* **Stilhinweis** (optional, z. B. „speak sadly and slowly“).
* **Erweiterte Generierung und Segmentierung:** TTS-GPU, maximale neue Tokens (Start 1500), Temperatur, Top-p, **maximale Zeichen pro Segment** (220–280), **Pause zwischen Segmenten** (120–200 ms), **Stille am Ende** (100–250 ms), *auffällig kurze Ausgabe automatisch einmal wiederholen*, *maximale Generierungsdauer pro Segment*.
* Bricht die Stimme am Satzende ab: kürzere Segmente, etwas höheres Token-Limit und Stille am Segmentende moderat erhöhen.

### RVC (Stimmumwandlung)
In der Engine-Seite **RVC aktivieren** und einen Ordner mit einer `.pth`-Stimme wählen (Ordner in `assets/rvc_models`). Gibt es keine `.pth`-Datei im Ordner, meldet die App das. **Nutze nur eigene, synthetische oder lizenzierte Stimmen. Stimmen echter Personen ohne deren Einwilligung zu klonen ist nicht erlaubt.**

### Weitere Regeln für die Sprachausgabe
* **Sprachausgabemodus** (Einstellungen → System → Text-zu-Sprache-Regeln): z. B. *Nur Zitate vorlesen* oder ein eigener **regulärer Ausdruck** (z. B. `\*(.*?)\*` liest nur Text zwischen Sternchen).
* Die Ausgabe erfolgt **Satz für Satz** (Streaming), damit die Stimme schon beginnt, während die KI noch schreibt. Ein gemeinsamer Text-Reiniger entfernt Handlungen, Emojis und Markdown.
* Die Lippenbewegung wird glatt gefahren (**Lippensynchronisation glätten**).

## 5.3 Spracheingabe

* **Spracherkennung:** Faster-Whisper mit Silero-VAD (erkennt Sprechpausen). Gerät (CPU/GPU) unter *KI-Dienste*.
* **Einstellungen → Gespräch & Audio** (Karte *Spracheingabe, Wake-Word & Echo-Schutz*):

![Spracheingabe, Wake-Word und Echo-Schutz](images/pc/optionen_08_conversation_audio_voll.png)

| Einstellung | Bedeutung |
| --- | --- |
| **Wake-Word aktivieren** | das Programm reagiert erst, wenn eine der Phrasen gesagt wird (mehrere mit Komma, z. B. `Yume, Hey Yume`). Erkennung im Whisper-Text, kein Spezial-Detektor |
| **Aktiv bleiben nach Wake-Word** | Sekunden, die nach dem letzten Satz zugehört wird |
| **Echo-Schutz-Modus** | *Aus*, *Halbduplex* (Mikrofon pausiert, solange der Charakter spricht, plus Nachlaufzeit) oder **WebRTC AEC3** (echte Echoentfernung, du kannst dazwischenreden) |
| **Sprache der Spracherkennung** | *Automatisch erkennen* oder fest |
| **AEC-Referenzverzögerung** | Abgleich zwischen Lautsprecher und Mikrofon (Standard 60 ms) |
| **Echo-Nachlauf** | nur für den Halbduplex-Fallback (700 ms) |
| **Stille bis zum Satzende** | wie lange Pause als Satzende gilt (760 ms; zu niedrig schneidet Pausen ab) |
| **Audio-Vorlauf** | verhindert abgeschnittene Anfangslaute (192 ms) |
| **Maximale Textlänge pro TTS-Segment**, **Pause zwischen Segmenten** | Feinabstimmung der Ausgabe |
| **AEC3 erneut prüfen / installieren** | prüft die Bibliothek `pywebrtc-audio`; bei Fehlern wird automatisch Halbduplex genutzt |

Die meisten Audio-Werte gelten erst nach Neustart des Sprachmodus. Ob AEC3 gut klingt, hängt von Lautsprechern, Mikrofon und Raum ab; teste es.

### Echo-Schutz (Anti-Echo) im Detail

Damit sich die KI nicht selbst hört, gibt es drei Verfahren. Die Namen entsprechen den Einträgen in der App (*Einstellungen → Gespräch & Audio → Echo-Schutz-Modus*):

| Eintrag in der App | Fachbegriff | Wirkung |
| --- | --- | --- |
| **Aus** | kein Echo-Schutz | Mikrofon bleibt immer offen. Nur mit Kopfhörer sinnvoll, sonst hört sich die KI selbst |
| **Halbduplex: während Wiedergabe nicht zuhören** | *Half-Duplex* (Anti-Echo mit Stummschaltung) | Das Mikrofon wird stummgeschaltet, solange der Charakter spricht, plus **Echo-Nachlauf** (700 ms). Zuverlässig und ohne Zusatzpaket, aber du kannst nicht dazwischenreden |
| **WebRTC AEC3 (Vollduplex-Echoentfernung)** | *Full-Duplex* mit *Acoustic Echo Cancellation* (WebRTC **AEC3**, Bibliothek `pywebrtc-audio`) | Das tatsächlich abgespielte Audio dient als Referenz und wird aus dem Mikrofonsignal herausgerechnet. Das Mikrofon bleibt offen, du kannst der KI **ins Wort fallen**. Feineinstellung mit **AEC-Referenzverzögerung** (60 ms) |

Beim Start prüft die App, ob AEC3 funktioniert (*„WebRTC AEC3 ist bereit. Vollduplex-Echoentfernung ist verfügbar.“*). Fehlt das Paket oder besteht der Test nicht, fällt sie automatisch auf **Halbduplex** zurück; **WebRTC AEC3 prüfen / installieren** repariert das in der Python-Umgebung der App.

**Auf dem Handy** heißt der Schalter **Echo-Unterdrückung** (*Einstellungen → Gespräch*): Die App schaltet im Anruf auf den Telefon-Audiopfad von Android (`USAGE_VOICE_COMMUNICATION`) und aktiviert den Echo-Unterdrücker des Handys (`AcousticEchoCanceler`, falls das Gerät ihn hat). Das ist ebenfalls eine Vollduplex-Lösung. Über **Unterbrechen** (*Durch Sprechen*, *Nur mit Stopp-Wort*, *Aus*) legst du fest, wie du die KI mitten im Satz stoppst. Am besten funktioniert alles mit Kopfhörern. Siehe [Android-App](11-android-app.md#117-einstellungen-am-handy).

* **Hey Yume am PC** (immer lauschend, auch bei geschlossenem Chat) steht im [Organizer](10-organizer.md#1017-hey-yume-am-pc).
* **Stimmungs-Gespür** aus der Stimme (experimentell, es werden nur Zahlen ausgewertet, keine Aufnahmen): [Organizer](10-organizer.md#108-gespräche-und-stimmung).

## 5.4 Anrufen

Auf der Kachel eines Charakters das **Telefon-Symbol** („Anrufen“) wählen. Du entscheidest den **Anrufmodus**:

* **Yume-System**: Vollbild-Anruffenster mit interaktivem Avatar und Sprachchat.
* **Yume-Desktop-Begleiter**: rahmenlose Figur, die über anderen Fenstern bleibt.

Der Charakter braucht vorher eine **Stimme**. Ohne Stimme meldet die App „Weise dem Charakter eine Stimme zu, bevor du den Anruf startest“. Ein lokales LLM muss geladen sein, sonst erscheint der Hinweis „Wähle im Modell-Hub *Local LLM*“. Die Schaltfläche *Unterhaltung starten* beginnt das Zuhören; während der Ausgabe zeigt sie „Spricht …“.

## 5.5 Avatare

Der Charakter wird im Chat rechts neben den Nachrichten animiert und reagiert auf jede Antwort.

### Das Gefühls-System
Ein Klassifikator liest jede Antwort und ordnet sie **28 Gefühlen** zu: neutral, Freude, Liebe, Trauer, Wut, Bewunderung, Belustigung, Verärgerung, Zustimmung, Fürsorge, Verwirrung, Neugier, Verlangen, Enttäuschung, Missbilligung, Ekel, Verlegenheit, Begeisterung, Angst, Dankbarkeit, Kummer, Nervosität, Optimismus, Stolz, Erkenntnis, Erleichterung, Reue, Überraschung. Für jedes Gefühl kannst du eine eigene Reaktion hinterlegen.

### Vier Darstellungsarten
Kachel → **Gesichtsausdrücke** (*Ausdrucksauswahl*). Links *Visualisierungs-Engine* wählen, Ordner oder Datei bestimmen, **Auswahl speichern**.

![Ausdrucksauswahl](images/pc/dialog_ausdruecke.png)

| Ausdrucksbilder | Live2D-Modell | VRM-3D-Modell |
| --- | --- | --- |
| ![Ausdrucksbilder](images/pc/dialog_ausdruecke_bilder.png) | ![Live2D](images/pc/dialog_ausdruecke_live2d.png) | ![VRM](images/pc/dialog_ausdruecke_vrm.png) |

| Art | Wo die Dateien liegen | Hinweise |
| --- | --- | --- |
| **Keine Visualisierung** | – | nur die statische Charakterkarte |
| **Ausdrucksbilder** | `assets/emotions/images/<Ordnername>/` | Eine Datei pro Gefühl, Name = Gefühl: `neutral.png`, `joy.gif`, `anger.png` … (PNG, JPG oder GIF). Fehlt ein Gefühl, wird `neutral` genutzt. Leichteste Variante, keine Last für CPU/GPU |
| **Live2D-Modell** | `assets/emotions/live2d/<Modellordner>/` | nur Format **.moc3** (altes .moc wird nicht unterstützt). Motions (Blinzeln, Arme, Posen) und Lippensynchronisation. Mit **Gefühle Bewegungen zuordnen** weist du jedem der 28 Gefühle eine Animationsgruppe zu |
| **VRM-3D-Modell** | `assets/emotions/vrm/` | freie 3D-Modelle (`.vrm`), z. B. mit der kostenlosen Software VRoid Studio gebaut oder von VRoid Hub. Haare und Kleidung bewegen sich, Mimik, Augenkontakt, Körper-Animationen |

Tipp: Reagiert die App beim Laden eines Live2D- oder VRM-Modells nicht sofort, kurz warten und das Fenster nicht schließen.

### Live2D-Bewegungszuordnung
Weist jedem der 28 Gefühle eine Körperanimationsgruppe zu; **Standard wiederherstellen** und **Zuordnung speichern**.

### Eigene Inhalte und Rechte
Dieses Repository enthält nur frei weitergebbare Avatare: selbst gezeichnete Ausdrucksbilder der Demo-Charaktere und zwei **VRoid-Beispielmodelle** (`Anime Girl.vrm`, `Anime Man.vrm` vom pixiv VRoid Project, VRM Public License 1.0, siehe [NOTICE](../NOTICE.md)). Die Demo-Charaktere Mika und Kai nutzen sie:

![Chat mit VRM-Avatar](images/pc/chat_vrm_mika.png)

Die 28 Körperanimationen zu den Gefühlen (`app/utils/emotions/vrm/expressions/*.fbx`) sind **nicht** im Repository (vermutlich Mixamo-Material, das man nicht weitergeben darf). Ohne sie steht das Modell in der T-Pose; eigene Animationen mit den Gefühlsnamen als Dateinamen (`neutral.fbx`, `joy.fbx` …) legst du in diesen Ordner. Live2D-Modelle liegen hier nicht bei. Wenn du Modelle von anderen nutzt, beachte deren Lizenz (Angabe von Quelle, kommerzielle Nutzung, Veränderung). Die Cubism-Komponenten von Live2D stehen unter einer eigenen Lizenz.

## 5.6 Umgebungsgeräusche und Hintergründe

* **Umgebungsgeräusche** (Einstellungen → Yume-Module): spielt beim Öffnen des Chats passende Atmosphäre ab (Wald, Regen, Taverne, Lagerfeuer …). Eigene Dateien in `assets/ambient` ablegen (Knopf *Ambient-Ordner öffnen*), *Audioliste aktualisieren*. Standard-Titel und -Lautstärke einstellbar; im Chat steuert das Audio-HUD oben rechts Klangkulisse und Lautstärke.
* **Chat-Hintergrund:** Bilder aus `assets/backgrounds` (für Querformat „Horizontal …“, für Hochformat „Vertical …“), pro Chat wählbar.
