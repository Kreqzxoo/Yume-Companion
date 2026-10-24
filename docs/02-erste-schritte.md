# 02 Erste Schritte

In zehn Minuten vom leeren Programm zum ersten Gespräch.

## 2.1 Die Oberfläche

![Startseite mit den drei Beispiel-Charakteren](images/pc/seite_1_main_characters.png)

**Seitenleiste links** (von oben nach unten):

| Eintrag | Zweck |
| --- | --- |
| Anzeige **KEIN MODELL AKTIV / MODELL LÄDT / MODELL BEREIT / GENERIERUNG** | Zustand des lokalen Sprachmodells (llama.cpp) |
| **Startseite** | Deine Charaktere als Kacheln („Startzentrale“) |
| **Yume-Bühne** | Rollenspiel mit KI-Spielleiter ([Kapitel 07](07-yume-buehne.md)) |
| **Werkstatt** | Charakter-Editor, Lorebooks, Personas, System-Prompts, Discord-Gateway, Bildgenerierung |
| **Charakter-Galerie** | Fertige Charakterkarten aus dem Netz |
| **Modelle** | Lokale Sprachmodelle suchen, laden, starten |
| **Einstellungen** | Alles Weitere (19 Bereiche) |
| ⓘ unten | „Über Yume Companion“ mit Version, Autor und Links |

Der Klick auf ⓘ öffnet den Über-Dialog mit Version, Kurzbeschreibung der drei Bereiche, Lizenzhinweis (GPL-3.0, Basis Soul of Waifu) und dem Autorennamen:

![Über-Dialog](images/pc/dialog_ueber.png)

**Leiste oben auf der Startseite:** Begrüßung mit deinem Persona-Namen, drei Symbole (Charakter erstellen · Charakterkarte importieren · Neuer Ordner) und das Suchfeld für Charaktere. Du kannst eine `.png`- oder `.json`-Karte auch einfach **ins Fenster ziehen**, um sie zu importieren.

**Fensterknöpfe** ganz oben rechts: Minimieren, Maximieren, Schließen. Das Fenster ist an allen Rändern in der Größe veränderbar.

## 2.2 Schritt 1: ein Sprachmodell wählen

Ohne Sprachmodell kann kein Charakter antworten. Zwei Wege:

### Weg 1: Cloud-Anbieter (am schnellsten, keine starke Grafikkarte nötig)
1. **Einstellungen → Sprachmodell & APIs**.
2. Bei **Anbieter** den Dienst wählen (OpenAI, Anthropic, Google Gemini, DeepSeek, Mistral, OpenRouter, Grok, Qwen, Z.AI, Player2 oder eigener OpenAI-kompatibler Endpunkt).
3. Den **API-Schlüssel** eintragen (steht nur lokal in `api.json`) und ggf. den Modellnamen.
4. Bei **Charakter** später als *Konversationsmethode* denselben Anbieter wählen (siehe 2.3).

![Sprachmodell und Anbieter](images/pc/optionen_02_llm.png)

> **Datenschutz:** Bei Cloud-Anbietern gehen deine Nachrichten an diesen Anbieter. Das gilt auch für Werkzeug-Ergebnisse (z. B. gelesene Mails), die als Kontext mitgeschickt werden.

### Weg 2: lokales Modell (privat, offline)
1. Seitenleiste → **Modelle**.
2. Im Reiter **Empfehlungen** oder **Beliebt** ein Modell wählen. Als Faustregel: *Q4_K_M*-Dateien haben das beste Verhältnis aus Qualität und Größe; ein 8B-Modell braucht ca. 5 GB Speicher.
3. **Herunterladen** → Quantisierung wählen → warten.
4. In **Meine Modelle** das Modell mit **Modell laden** starten. Die Anzeige links oben wechselt auf *MODELL LÄDT … → MODELL BEREIT*.

![Modelle-Hub](images/pc/seite_6_modelshub.png)

Wenn du einen **zweiten PC** als Server hast: [Kapitel 12 (Yume LLM Server)](12-llm-server.md).

## 2.3 Schritt 2: einen Charakter anlegen

**Startseite → Symbol „Charakter erstellen“** oder **Werkstatt → Charaktereditor**.

![Charakter erstellen](images/pc/seite_2_create_character.png)

Mindestens nötig: **Name** und **Erste Nachricht**. Für gute Ergebnisse zusätzlich Beschreibung und Persönlichkeit. Oder lass den **KI-Assistenten** die Felder schreiben (siehe [Kapitel 03](03-chat-und-charaktere.md#ki-assistent)). Danach bei **Konversationsmethode** den Anbieter wählen (z. B. *Local LLM*, *Remote LLM* oder ein Cloud-Dienst) und **Charakter erstellen** klicken.

Alternativ:
* **Charakterkarte importieren** (`.png` mit eingebetteten Daten oder `.json`, Format „TavernAI/SillyTavern“ und Soul-of-Waifu-Karten).
* **Charakter-Galerie**: Karten durchsuchen und mit **Zur Liste hinzufügen** übernehmen.
* Beispiel-Charaktere (Yume, Mika, Kai) per `tools/demo/make_demo_content.py`.

## 2.4 Schritt 3: chatten

Klicke die Kachel des Charakters. Der Chat öffnet sich:

![Chat mit Yume](images/pc/chat_yume.png)

| Bereich | Bedeutung |
| --- | --- |
| Kopf links | Name, Titel und **Token-Zähler** („264 / 16.384 tok“: so viel vom Kontextfenster ist belegt) |
| Kopf rechts | Audio-Hintergrund, Chat-Hintergrund, Autorennotizen, Zusammenfassung, Gedächtnis, Mehr (Charaktereinstellungen) |
| Nachrichten | Jede Nachricht hat **⋯** mit Bearbeiten, Neu generieren, Löschen, Übersetzen, Bild erzeugen, Sprachnachricht abspielen |
| Eingabezeile unten | Anhang (Bild/Dokument), Werkzeuge ein/aus, Persona wechseln, Gedächtnis jetzt erzwingen, Senden |

Schreibe eine Nachricht und sende mit **Enter**. Sterne `*lächelt*` werden als Handlung kursiv dargestellt.

Weiter: [03 Charaktere und Chat](03-chat-und-charaktere.md) · [05 Stimme und Avatare](05-stimme-und-avatare.md)

## 2.5 Programmsprache ändern

**Einstellungen → System & Benutzeroberfläche → Programmsprache** (Englisch, Russisch, Deutsch). Nach der Änderung fragt das Programm nach dem Neustart.

![System und Benutzeroberfläche](images/pc/optionen_00_system.png)

Auf derselben Seite: **Nachrichtenübersetzung** (Google/Yandex, Zielsprache, Modus „beide / Nachricht des Benutzers / Charakternachricht“), **Audiogeräte** (Ein-/Ausgabe) und **Text-zu-Sprache-Regeln** (Sprachausgabemodus, z. B. „Nur Zitate vorlesen“ oder eigener regulärer Ausdruck). Unten stehen deine PC-Daten (RAM, Grafikkarte), anhand derer die App Empfehlungen gibt.
