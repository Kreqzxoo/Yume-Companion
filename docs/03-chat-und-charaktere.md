# 03 Charaktere und Chat

Dieses Kapitel erklärt alles rund um Charaktere: anlegen, importieren, einstellen, mit Lorebooks, Personas und System-Prompts steuern – und alle Funktionen des Chats.

## 3.1 Die Werkstatt

**Werkstatt** in der Seitenleiste sammelt die Werkzeuge zum Gestalten:

![Werkstatt](images/pc/seite_7_rp_editors.png)

| Karte | Wofür |
| --- | --- |
| Charaktereditor | Eigene Charaktere mit Persönlichkeit, Hintergrund und Dialogbeispielen |
| Personas | Dein eigenes Profil (Name, Beschreibung, Bild) |
| System-Prompts | Anweisungen und Format, in dem die KI die Charakterdaten erhält |
| Lorebooks | Weltwissen: Orte, Regeln, Ereignisse |
| Yume-Bühne | Rollenspiel-Szenen (siehe [Kapitel 07](07-yume-buehne.md)) |
| Bildgenerierung | Einstellungen für KI-Bilder (siehe [Kapitel 09](09-werkzeuge-und-integrationen.md)) |
| Discord-Gateway | Charakter als Discord-Bot (siehe [Kapitel 09](09-werkzeuge-und-integrationen.md)) |

## 3.2 Charakter erstellen

**Startseite → „Charakter erstellen“** öffnet den Editor. Links ist die Navigation, rechts die Felder:

| Abschnitt | Felder |
| --- | --- |
| Allgemeine Informationen | Charakterbild, **Name**, Titel, Version der Karte |
| Persönlichkeit und Szenario | **Beschreibung** („Fakten, die die KI wissen soll“), **Persönlichkeit** (Kurzfassung), **Szenario** |
| Dialoge und Begrüßungen | **Erste Nachricht** (legt Ton und Stil fest), **Beispieldialoge** (jeder Dialog beginnt mit `<START>`), **Alternative Begrüßungen** (jede beginnt mit `<GREETING>`) |
| Erweiterte Einstellungen und Lore | **Benutzerpersona**, **System-Prompt-Vorlage**, **Weltwissen** (Lorebooks, mehrere möglich), **Konversationsmethode** |
| Variablen und Status | eigene Statusvariablen mit HUD (siehe 3.7) |
| Export und Werkzeuge | Karte exportieren, Felder leeren, **Rohtext anzeigen** (Vorschau des Prompts), Token-Zähler |

Platzhalter in Texten: `{{user}}` (dein Persona-Name) und `{{char}}` (der Charaktername).

![Charaktereditor](images/pc/seite_2_create_character.png)

### Konversationsmethode (Anbieter pro Charakter)
Jeder Charakter hat seinen eigenen Anbieter: *Local LLM*, *Remote LLM*, *OpenAI*, *Anthropic*, *Google Gemini*, *DeepSeek*, *Grok*, *Qwen*, *Z.AI*, *Mistral AI*, *OpenRouter* oder *Player2*. So kann Yume lokal laufen, Kai über eine Cloud-API. Details und Zugangsdaten: [Kapitel 04](04-sprachmodelle.md).

### KI-Assistent
Im Editor öffnet **KI-Charakterassistent** einen Fragebogen in sechs Schritten: *Grundidee → Charakter und Stimme → Aussehen und Hintergrund → Beziehungen → Details und Grenzen → Generator*. Du wählst Genre (Fantasy, Sci-Fi, Anime, Cyberpunk, Alltag …), Rolle (Begleiter, Mentor, Rivale, Assistent …), Eigenschaften (freundlich, tsundere, schüchtern, loyal …), Sprechstil, Beziehung zu dir und die Stimmung der Geschichte. Danach bestimmst du, **welche Felder** die KI schreiben soll, und ob vorhandene Inhalte überschrieben oder nur leere Felder gefüllt werden. Nach dem Erzeugen prüfst und bearbeitest du den Text, kannst einzelne Felder **neu generieren** und mit **In den Editor übernehmen** abschließen. Der Assistent nutzt den Anbieter, der im Programm eingerichtet ist (ohne Zugang erscheint ein Hinweis).

![KI-Charakterassistent](images/pc/dialog_ki_assistent.png)

## 3.3 Charakterkarten importieren und exportieren

* **Importieren:** Symbol auf der Startseite oder Datei ins Fenster ziehen. Unterstützt werden `.png`-Karten mit eingebetteten Daten und `.json`. Enthält die Karte ein Lorebook, fragt die App, ob es der Bibliothek hinzugefügt werden soll.
* **Exportieren:** im Charakter (Mehr → Charakterkarte) oder im Editor unter *Export und Werkzeuge*.
* **Charakter duplizieren:** im Charaktermenü *Duplizieren* (bei gleichem Namen wird eine Nummer angehängt).

## 3.4 Die Charakter-Galerie

**Charakter-Galerie** durchsucht öffentliche Inhalte in vier Reitern: **Yume Gateway** (Charakterkarten der Community), **Chub AI Hub** (Karten von chub.ai), **Welt-Wissenssammlungen** (Lorebooks) und **Bühnen-Szenarien** (Szenen für die [Yume-Bühne](07-yume-buehne.md)). Oben stehen die Suche und „Im Trend“; jede Karte hat eine Vorschau; **In das System importieren** bzw. **Zur Liste / Bibliothek / Stages hinzufügen** übernimmt sie. Der **NSFW-Schalter** oben rechts bestimmt, ob Inhalte für Erwachsene angezeigt werden. Prüfe seinen Zustand vor dem ersten Öffnen.

![Charakter-Galerie](images/pc/seite_galerie.png)

> Die Galerie braucht Internet. Inhalte stammen von Dritten; prüfe Karten, bevor du sie benutzt.

## 3.5 Ordnung auf der Startseite

* **Ordner:** Symbol *Neuer Ordner* → Name, Charaktere auswählen. Ordner lassen sich bearbeiten (Charaktere hinzufügen/entfernen, per Ziehen neu ordnen) und löschen (die Charaktere kehren in die Hauptliste zurück).
* **Suche:** Das Suchfeld filtert Charaktere nach Namen.
* **Kachelaktionen:** Klick auf die Kachel öffnet den Chat. Fährst du mit der Maus darüber, erscheinen Symbole: **Ordner** (in einen Ordner verschieben), **⋯** (Charakterinformationen), **Telefon** (Anrufen), **Mikrofon** (Spracheinstellungen), **Papierkorb** (löschen). Das **Bildschirm-Symbol** unten rechts öffnet die *Gesichtsausdrücke* (Avatar-Auswahl).

![Kachel mit Mauszeiger](images/pc/kachel_aktionen.png)

## 3.6 Personas, System-Prompts, Lorebooks, Autorennotizen

### Personas (Werkstatt → Personas)
Eine Persona beschreibt **dich**: Name, Beschreibung, Bild (empfohlen 256×256). Du kannst mehrere anlegen, eine als **Standard** festlegen und im Chat über das Persona-Symbol unten schnell **wechseln**.

![Persona-Editor](images/pc/dialog_personas.png)

### System-Prompts (Werkstatt → System-Prompts)
Der System-Prompt sagt dem Modell, wie es sich verhalten soll. Der Editor hat drei Teile: den **Prompt-Text**, die **Reihenfolge der Bausteine** (zum Sortieren ziehen: Das Modell beachtet meist Inhalte am Ende stärker; wichtige Persönlichkeit nach hinten) und die **Vorlagen-Steuerung** (neue Vorlage, speichern, löschen, *Standard*). Pro Charakter wählst du die Vorlage aus.

![System-Prompt-Editor](images/pc/dialog_systemprompt.png)

### Lorebooks (Werkstatt → Lorebooks)
Ein Lorebook ist ein Nachschlagewerk: Erwähnst du ein Stichwort, fügt die App den passenden Eintrag automatisch in den Prompt ein. Die **Lorebook-Engine** hat:

* **Bibliothek** (mehrere Lorebooks), Einträge filtern, **Such-Tiefe** (wie viele letzte Nachrichten geprüft werden), Token-Zähler, JSON importieren/exportieren, umbenennen, löschen.
* **Auslösertypen:** *Schlüsselwörter* (mit Ausschlussbegriffen), *Semantisch* (die KI erkennt die beschriebene Situation), *Immer aktiv*, *Zufällig* (Wahrscheinlichkeit), *Kette* (Eintrag wird nach einem Elterneintrag freigeschaltet, mit Verzögerung), *Szenario* (nur in einem Nachrichtenbereich).
* **Einfügung:** *Passiv* oder *Aktiv*.
* **Zeitgesteuerte Effekte:** *Haftend* (bleibt N Nachrichten aktiv), *Abklingzeit*, *Verzögerung*, *Wahrscheinlichkeit*.

![Lorebook-Engine mit dem Beispiel „Yume-Welt“](images/pc/dialog_lorebook.png)

### Autorennotizen
Globale Erzählvorgaben, die dynamisch in den Kontext eingefügt werden (z. B. Schreibstil oder Regeln). Im Chat über das Notizen-Symbol oben rechts.

![Autorennotizen](images/pc/chat_autorennotizen.png)

## 3.7 Variablen und HUD

Mit **Eigene Variable hinzufügen** definierst du Werte, die der Charakter im Gespräch verfolgt (ID, Anzeigename, Datentyp, HUD-Symbol, Minimum, Maximum, Standardwert, Prompt-Vorlage wie `[Vertrauen: {value}/100]`). Fertige Vorlagen sparen Arbeit: Romantik (Zuneigung/Vertrauen), RPG (HP, Mana, Gold, Inventar), Tamagotchi, Horror-Survival, Detektiv, sowie Anime-Typen (Yandere, Shonen, Maid, Chuunibyou, Tsundere, Kuudere, Dandere, Himedere). **Vorlage speichern/löschen** für eigene Sätze.

## 3.8 Der Chat im Detail

![Chat mit Yume](images/pc/chat_yume.png)

### Kopfleiste
* **Name, Titel und Token-Zähler**: Belegung des Kontextfensters.
* **Audio-Hintergrund** (Symbol „Muted“): Umgebungsgeräusche und Lautstärke wählen (nur wenn das Modul aktiv ist, siehe [Kapitel 09](09-werkzeuge-und-integrationen.md#910-umgebungsgeräusche)).
* **Chat-Hintergrund:** ein Bild für den Chat wählen.
* **Autorennotizen · Zusammenfassung · Gedächtnis · Mehr** (siehe unten).

![Chat-Hintergrund wählen](images/pc/chat_hintergrund.png)

### Nachrichten
Das **⋯**-Menü jeder Nachricht:

| Aktion | Beschreibung |
| --- | --- |
| Bearbeiten | Text ändern (z. B. Fehler korrigieren) |
| Neu generieren | neue Antwortvariante; mit **◀ ▶** blätterst du durch die Varianten |
| Ab dieser Nachricht fortsetzen | alles danach wird verworfen |
| Löschen | einzelne oder mehrere Nachrichten |
| Übersetzen | in die Zielsprache |
| Bild generieren | erzeugt ein Bild zur Szene (wenn Bildgenerierung aktiv) |
| Sprachnachricht abspielen | gespeicherte Sprachausgabe erneut hören |

Welche Einträge erscheinen, hängt von der Nachricht ab (z. B. „Neu generieren“ nur bei Antworten des Charakters, „Bild generieren“ nur bei aktiver Bildgenerierung).

Bei Werkzeugnutzung zeigt der Chat „verwendet *Werkzeug* …“ und, bei Reasoning-Modellen, einen einklappbaren **DENKPROZESS**.

### Eingabezeile
* **Anhang** (Büroklammer): Bild oder Dokument, bis zu einer Höchstzahl pro Nachricht; zu große Dateien werden übersprungen. Bilder beschreibt das Vision-Modell, wenn dein Chat-Modell keine Bilder versteht ([Kapitel 04](04-sprachmodelle.md#44-vision)).
* **Werkzeuge** (Schraubenschlüssel): schaltet für diesen Chat Werkzeuge wie Rechner, Datum/Uhrzeit und Websuche ein oder aus.
* **Persona wechseln** (rundes Symbol mit „YOU“).
* **Gedächtnis jetzt erzwingen:** stößt die Gedächtnis-Aktualisierung sofort an.
* **Senden** mit der Enter-Taste; **Umschalt+Enter** macht einen Zeilenumbruch. Während der Generierung gibt es **Stopp**.

### Mehr: Charaktereinstellungen
Das **⋯**-Symbol öffnet die Charaktereinstellungen mit den Abschnitten *Identität, Szenario, Beispiele, Notizen des Erstellers* sowie **Neuen Chat starten**, **Änderungen speichern** und die Chat-Verwaltung.

![Charaktereinstellungen](images/pc/chat_mehr.png)

### Chatverwaltung
Pro Charakter gibt es mehrere **Chats**: neu anlegen, umbenennen, löschen, **exportieren** und **importieren** (Dateiformat `.sowchat`). Beim Import eines Chats von einem anderen Charakter fragt die App nach; bei gleicher Chat-ID wählst du *überschreiben* oder *neu anlegen*.

### Zusammenfassung (Story-Gedächtnis)
Lange Chats werden automatisch verdichtet, damit das Kontextfenster nicht überläuft. Im **Story-Gedächtnis-Editor** siehst du den aktuellen Gedächtnistext, ob er bis Nachricht N reicht, bearbeitest die **Anweisung** für die Zusammenfassung und kannst **sofort zusammenfassen** oder das Gedächtnis **leeren**. Mehr dazu in [Kapitel 06](06-gedaechtnis.md).

![Story-Gedächtnis](images/pc/chat_zusammenfassung.png)

### Persona-Schnellwechsel und Tastenkürzel
Das Menü *Persona wechseln* zeigt alle Personas. Mit dem Pfeil unten rechts springst du zur neuesten Nachricht.
