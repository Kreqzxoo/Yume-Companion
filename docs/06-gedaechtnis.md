# 06 Gedächtnis

Yume Companion behält Dinge auf drei Ebenen: den **Chatverlauf** im Kontextfenster, das **Story-Gedächtnis** (verdichtete Zusammenfassung langer Chats) und das **Yume-Gedächtnis** (langfristiges, kognitives Gedächtnis pro Charakter).

## 6.1 Das Yume-Gedächtnis

Statt sich nur auf den Chatverlauf zu verlassen, führt jeder Charakter eigene Dateien (Ordner `.soul/<Charakter>/`):

| Datei / Ebene | Inhalt |
| --- | --- |
| **MEMORY.md** (Kernindex) | Psychologie des Charakters: Stimmung, Ziele, Motive |
| **USER.md** (Benutzerprofil) | was der Charakter über **dich** weiß, Beziehungsdaten |
| **Themen-Archiv** | verdichtete Episoden und Fakten, mit lokalen Einbettungen durchsuchbar |
| **Tagebuch** | persönliche Einträge in der Ich-Form über eure Gespräche |
| **Protokolle zur Selbstkorrektur** | was der Gedächtnis-Agent geändert hat |

Hintergrund-Agenten analysieren die Gespräche selbstständig. Gefühle verblassen mit der Zeit (natürlicher Übergang), Widersprüche werden erkannt und aufgelöst, Doppelungen verschmolzen, Dateien werden sicher (atomar) gespeichert. Das Ergebnis: weniger unnötiger Kontext und eine gleichbleibende Persönlichkeit, auch in der [Yume-Bühne](07-yume-buehne.md) und mit dem [Desktop-Begleiter](08-desktop-begleiter.md).

### Einschalten und Modus wählen
**Einstellungen → Yume-Module → Kognitive Architektur → Yume-Gedächtnis aktivieren.**

![Yume-Module: Webserver, Umgebungsaudio, Gedächtnis](images/pc/optionen_09_sow_system.png)

| Modus | Was aktiv ist | Geeignet für |
| --- | --- | --- |
| **Volle Synchronisation** | alles: Psychologie-Index, Themen/Lore, Tagebuch | starke PCs oder APIs, das beste Erlebnis |
| **Seelenverbindung** | Persönlichkeit und Gefühle (MEMORY.md) und Tagebuch; keine Themen | tiefe Bindung ohne hohe Last |
| **Gedankenfunke** | nur der MEMORY.md-Index | langsame PCs, schnelles Rollenspiel |
| **Reflexionsfluss** | nur das Tagebuch | maximale Geschwindigkeit bei erhaltener Gefühlshistorie |

**Batchgröße** legt fest, nach wie vielen Nachrichten das Gedächtnis aktualisiert wird (0 = nur von Hand). Mit dem Symbol **„Gedächtnis jetzt erzwingen“** in der Chat-Eingabezeile stößt du es sofort an.

### Gedächtnis ansehen und bearbeiten
Im Chat oben rechts das **Gedächtnis-Symbol**:

![Gedächtnis-Archiv](images/pc/dialog_gedaechtnis.png)

Reiter *Gedächtnisdatenbank*, *Benutzerprofil*, *Tagebuch*, *Protokolle zur Selbstkorrektur*. Mit **Bearbeiten** änderst du Fakten von Hand, **Änderungen speichern**, **Datei löschen**, **Aktualisieren** und **.soul-Ordner öffnen**. Ist der Chat leer, weist die App darauf hin („Öffne zuerst einen Chat mit einem Charakter“).

## 6.2 Story-Gedächtnis (automatische Zusammenfassung)

Lange Gespräche würden das Kontextfenster füllen. Darum verdichtet die App ältere Nachrichten zu einer **Zusammenfassung**:

* **Automatische Zusammenfassungen aktivieren** (Yume-Module) mit **Intervall (Nachrichten)**, Standard 25.
* Im Chat das **Zusammenfassungs-Symbol**: *Story-Gedächtnis-Editor* mit dem aktuellen Gedächtnistext („Verlauf: 1–N“), den **Vorgaben für die Zusammenfassung** (wie die KI verdichten soll), den Knöpfen **Zusammenfassung erstellen**, **Gedächtnis leeren**, **Änderungen speichern**.

![Story-Gedächtnis-Editor](images/pc/chat_zusammenfassung.png)

## 6.3 Autorennotizen

Globale Anweisungen, die immer in den Kontext kommen, ohne die Charakterkarte zu ändern. Siehe [Kapitel 03](03-chat-und-charaktere.md#autorennotizen).

## 6.4 Was Yume sich außerdem merkt (Organizer)

Neben dem Gedächtnis pro Charakter gibt es ein **allgemeines Merkbuch**: Sagst du „Merk dir, dass ich morgens keine Regenhinweise mag“, speichert Yume das dauerhaft und nutzt es in jedem Chat, Briefing und jeder Routine. Alles ist im [Organizer](10-organizer.md#107-was-yume-sich-merkt) einsehbar und löschbar.

## 6.5 Daten, Sicherung und Löschen

* Das Gedächtnis liegt im Ordner `.soul` im Programmverzeichnis (nicht im Repository).
* Es ist Teil des **Profil-Backups** (Option *Yume-Gedächtnis*) – siehe [Kapitel 14](14-backup-updates-sicherheit.md).
* Einzelne Dateien löschst du im Archiv. Für **ein einzelnes Gerät oder eine Person** vergessen: Datei im Archiv löschen oder `.soul/<Charakter>` entfernen.
