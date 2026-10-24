# 07 Yume-Bühne

Die **Yume-Bühne** ist eine Textabenteuer-Engine: eine KI führt als **Spielleiter** (Erzähler) mehrere Charaktere durch eine Geschichte, mit Würfelproben, Inventar, Ereigniskarten und Nebenfiguren. Sie funktioniert wie ein Pen-and-Paper-Rollenspiel am PC.

![Übersicht der Szenen](images/pc/buehne_uebersicht.png)

## 7.1 Szenen verwalten

Seitenleiste → **Yume-Bühne**. Oben: **Neuer Ordner**, **Importieren**, **Neue Szene** und eine Suche. Jede Szene ist eine Karte mit Titel, Kurzbeschreibung, den Bildern der Gruppenmitglieder und den Knöpfen:

| Symbol / Knopf | Funktion |
| --- | --- |
| **Abspielen** | Szene öffnen. Hat sie einen gespeicherten Verlauf, wählst du *fortsetzen* (N gespeicherte Nachrichten laden) oder *neu beginnen* (Verlauf wird gelöscht) |
| Ordner-Symbol | Szene in einen Ordner verschieben |
| Export-Symbol | Szene als Datei (JSON) weitergeben; **Alles exportieren** sichert alle |
| Stift | Szene bearbeiten |
| Papierkorb | Szene samt Verlauf dauerhaft löschen |

Ordner gruppieren Szenen („Szenenordner“). Die Szenen-Galerie der Charakter-Galerie bietet fertige Szenarien („Zu den Stages hinzufügen“).

## 7.2 Eine Szene anlegen

**Neue Szene** öffnet den Szeneneditor mit fünf Abschnitten:

![Szeneneditor](images/pc/buehne_szene_bearbeiten_voll.png)

| Abschnitt | Felder |
| --- | --- |
| **I. Szenenidentität** | Titel, Kurzbeschreibung |
| **II. Weltzustand und Umgebung** | **Weltkontext/Szenario** (wird jedem Prompt als Hintergrund beigefügt), Ausgangsort, **Tageszeit** (Morgen, Tag, Abend, Nacht), **Ton des Spielleiters** (Epische Fantasy, Alltag, Krimi & Noir, Romantik, Horror, Komödie, Sci-Fi), **Erzählstil**, **Ausgangssituation** (Hintergrundbild) und **Ausgangsatmosphäre** (Umgebungsgeräusch), beide vom Planer später dynamisch änderbar, optional **Hintergrund sperren** und **Umgebungsgeräusche deaktivieren** |
| **III. Szenenbeginn** | **Eröffnungserzählung** (die ersten Worte des Erzählers), optional die **erste Nachricht** eines Gruppenmitglieds |
| **IV. Gruppenmitglieder** | beliebige Charaktere aus deiner Liste |
| **V. Engine-Einstellungen** | **Konversationsmethode** (Anbieter), **Benutzerpersona**, **Maximale Anzahl Figuren pro Zug** (1–6, Standard 3), **Lorebooks**, **Würfelwürfe** |

**Speichern & starten** legt die Szene an und beginnt.

## 7.3 Spielen

In der Szene schreibst du, was dein Charakter tut. Die Eingabe hat vier **Modi**:

| Modus | Bedeutung |
| --- | --- |
| 💬 **Sprechen** | laut gesprochen |
| ⚔ **Handeln** | eine Handlung |
| 💭 **Denken** | stiller innerer Gedanke |
| 🎬 **Regie** | Anmerkung außerhalb der Rolle an den Spielleiter |

Weitere Bedienelemente:

* **Als Nächstes:** wählst du, wer als Nächstes spricht (statt dem Spielleiter zu überlassen), oder *Auto*.
* **Privat** („Flüstern“): Deine Nachricht wird privates Wissen nur des gewählten Charakters; die Gruppe erfährt nichts davon.
* **Auswahl-Vorschläge:** Der Spielleiter bietet Handlungsoptionen an (oder du schreibst eigene).
* **Handlung fortsetzen:** die Geschichte läuft weiter; optional gibst du einen Hinweis („Draußen gibt es eine Explosion“).
* **Eingreifen** (⚡): stoppt den KI-Zug.
* **Szenenbild:** erzeugt ein Bild zur aktuellen Szene (benötigt Bildgenerierung).
* **Nachrichtenmenü:** kopieren, bearbeiten (setzt den Weltzustand zurück und spielt den Zug neu), übersetzen, **Runde neu generieren**, löschen.
* **Szene als Markdown exportieren.**
* **Ereigniskarten:** Begegnung, Entdeckung, Besuch, Handlungswendung und „Moment“ erscheinen zufällig mit passenden Hinweisen für deine Antwort.

### Würfelproben
Aktivierst du **Würfelwürfe für diese Szene**, verlangt der Spielleiter bei riskanten oder umstrittenen Aktionen **W20/2W6/3W6**-Proben. Das Würfeln ist deterministisch geregelt und nicht dem Modell überlassen. Fähigkeiten mit Modifikator (−5 bis +10) fließen ein.

### Inventar, Status, Ressourcen
Die Szene zeigt ein **HUD** mit Inventar (Waffen, Verbrauchsgegenstände, Werkzeuge, Wertgegenstände, Quest-Gegenstände, Sonstiges; *Verwenden* und *Ablegen*), Zuständen und Ressourcen („Name: aktuell/maximal“).

## 7.4 Weltzustand und Kampagne

Das **Weltzustand-Fenster** (Symbol im Kopf der Szene) hat Reiter:

| Reiter | Inhalt |
| --- | --- |
| **Szene** | Ort, Tageszeit, Weltkontext |
| **Wichtige Fakten** | „Schlüssel: Wert“ pro Zeile |
| **Inventar** | ein Gegenstand pro Zeile |
| **Status** | Zustände und Zustandseffekte |
| **Ressourcen** | Ressourcen und Fähigkeiten |
| **Weltwissen-Karten** | Kampagnenwissen, das nur bei passenden Auslösern in die Geschichte kommt |
| **Kampagnenübersicht** | **Ziele** („Titel \| aktuell/maximal \| Status \| Beschreibung“) und **Uhren** (Druck-Uhren) |
| **Handlungsbögen** | versteckte Story-Bögen; ein gesperrter Bogen existiert für keine Figur |
| **Beziehungen** | wie eine Figur eine andere sieht („A -> B \| Sympathie −100…100 \| Perspektive \| Stichwörter“) |
| **Charakterzustände** | sich entwickelnde Rollen und persönliche Fakten |
| **Aktive NPCs** | vom Erzähler erzeugte Nebenfiguren (nur lesen) |

## 7.5 Nebenfiguren und Gedächtnis

* Der Erzähler kann **NPCs herbeirufen** („Hinter der Bühne / Rollenliste“); sie haben ein **eigenes Gedächtnis**, das erhalten bleibt (`.soul_stage/npc_memory`). Figuren verlassen die Szene mit einem Hinweis im Protokoll.
* Das **Yume-Gedächtnis** (Symbol *Gedächtnis*) zeigt die Erinnerungen der Gruppenmitglieder, nachdem du die Figur gewählt hast.
* Das Gedächtnis von Charakteren wird auch hier genutzt, wenn das Yume-Gedächtnis aktiv ist ([Kapitel 06](06-gedaechtnis.md)).

## 7.6 Tipps

* Gib dem Spielleiter einen klaren **Weltkontext** und eine **Eröffnungserzählung**: Je konkreter, desto stimmiger.
* Starte mit 2–3 Gruppenmitgliedern; mehr Figuren pro Zug verlängern jede Runde.
* Für Würfelproben und Inventar sollte das Modell gut dem Format folgen (ein 8B-Modell oder besser).
