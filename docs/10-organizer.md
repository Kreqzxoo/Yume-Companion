# 10 Organizer

Der **Organizer** macht aus dem Charakter eine Alltagshilfe: Kalender, Mails (nur lesen), Erinnerungen, Listen, Morgen-Briefing, Pendelzeit, Geburtstage, eigene Dokumente, Briefe und Rechnungen, Wissensdatenbank und mehr. Alles läuft über **normale Sprache** im Chat (am PC oder am Handy) – die Einstellungen unter **Einstellungen → Organizer** richten nur die Zugänge ein und zeigen, was gespeichert ist.

![Organizer, ganze Seite](images/pc/optionen_18_organizer_voll.png)

**Datenspeicher:** `%LOCALAPPDATA%\YumeCompanion\` (also **außerhalb** des Projektordners, nicht in Releases). Zugangsdaten (iCal-Links, Mail-Passwort, Spotify) sind mit der Windows-Datenschutz-Funktion verschlüsselt. Die Organizer-Daten sind Teil des **Profil-Backups**.

Voraussetzung: **Werkzeugnutzung im Chat aktiv** ([Kapitel 09](09-werkzeuge-und-integrationen.md)) und ein Sprachmodell, das Werkzeuge aufrufen kann.

## 10.1 Kalender

Yume liest Kalender und trägt eigene Termine ein („Trag morgen um 15 Uhr Zahnarzt ein“).

* **Am PC:** unter *Kalender* einen oder mehrere **iCal-Links** (geheime Adresse im iCal-Format von Google, Outlook, Apple, Nextcloud …) einfügen, einen pro Zeile → **Speichern und testen**. ICS-Kalender sind schreibgeschützt; die Links sind verschlüsselt.
* **Am Handy:** der Kalender des Handys wird automatisch über die Handy-App gelesen (Berechtigung nötig).
* **Eigene Termine und Erinnerungen** erscheinen unter *Erinnerungen und eigene Termine* („Aktualisieren“, „Ausgewählte löschen“).

## 10.2 Mail (nur lesen)

Yume nennt und fasst neue Mails zusammen. Sie **liest nur**: Nichts wird gesendet, gelöscht oder als gelesen markiert.

| Feld | Beispiel |
| --- | --- |
| IMAP-Server | `imap.gmail.com` |
| Port | `993` |
| Adresse / Benutzer | `name@example.com` |
| **App-Passwort** | **nicht** das normale Passwort (bei Gmail: Google-Konto → Sicherheit → App-Passwörter; IMAP muss an sein) |
| Ordner | `INBOX` |

**Speichern und testen** / **Mail-Konto entfernen**. Hinweis: Der Text gelesener Mails geht an das gewählte Sprachmodell; bei einem Cloud-Modell also an diesen Anbieter.

**Mailentwürfe:** „Antworte auf die Mail von Anna und sag zu“ schreibt einen **Entwurf**. Yume sendet nie selbst: In *Mailentwürfe* öffnest du ihn im Mailprogramm, kopierst den Text oder löschst ihn.

## 10.3 Erinnerungen

„Erinnere mich in 20 Minuten an die Wäsche.“ Zur Zeit erscheint eine Meldung am PC und als Benachrichtigung auf dem gekoppelten Handy (das Programm muss laufen). Die Liste siehst du im Organizer.

## 10.4 Listen

„Setz Milch auf die Einkaufsliste“ oder „Was muss ich noch kaufen?“. Beliebige Listen (Einkauf, To-do …), Kurzformen wie „einkauf“ werden zusammengeführt. Die Listen gelten für PC- und Handy-Chat und erscheinen auch im Wandmodus des Handys.

## 10.5 Was Yume heute getan hat & Rückgängig

Jede ausgeführte Aktion (Musik, Erinnerungen, Termine, Listen …) steht im Protokoll *Das hat Yume heute getan*. Einträge mit Rückpfeil lassen sich zurücknehmen: per Knopf **Ausgewählte rückgängig machen** oder per Sprache: **„Mach das rückgängig.“**

## 10.6 Routinen

### Morgen-Briefing
Zur eingestellten **Uhrzeit** und an den gewählten **Wochentagen** (Mo–So) sagt Yume in eigenen Worten: **Wetter**, **Termine**, **Erinnerungen**, **neue Mails** (je einzeln wählbar). Wähle, **wo** gesprochen wird: *Handy, wenn verbunden, sonst PC*, *Handy* oder *PC*. **Morgen-Briefing jetzt testen** zeigt das Ergebnis sofort. „Guten Morgen“ oder „Briefing“ im Chat startet es ebenfalls.

* **Ort für das Wetter** (z. B. „Hamburg“) → **Ort speichern und Wetter testen**. Das Wetter kommt von **Open-Meteo** (kostenlos, ohne Konto).

### Gute Nacht
„Gute Nacht“ führt kleine Dinge aus (einzeln abwählbar): **Musik pausieren**, **Taschenlampe aus**, **Wecker prüfen**, **morgige Termine**, **Wetter morgen**. **Gute Nacht jetzt testen**.

### Pünktlichkeits-Assistent
Wann musst du losgehen? Für Termine **mit Ort** rechnet Yume die Fahrzeit (Adresse → Koordinaten über OpenStreetMap, Routen über OSM-Server; Start ist der aktuelle Handy-Standort, sonst deine **Heimadresse**). Einstellbar: **Unterwegs mit** (Auto, Fahrrad oder zu Fuß) und **Puffer** (z. B. 10 Min). **Sag mir, wann ich losgehen muss** schaltet die Hinweise ein.

### Regen-Alarm
Am Handy: Meldung, wenn du unterwegs bist und es gleich zu regnen beginnt (braucht den Handy-Standort).

### Wochenrückblick
Jeden **Sonntag um 18 Uhr**: was Yume getan hat, wie es dir ging (grobe Einschätzung aus deinen Worten), was ansteht. Alles lokal aus Werkzeug-Protokoll, Aufträgen, Stimmungs-Log, Tagebuch und Kalender. Auch auf Zuruf: „Wochenbericht“.

### Anwesenheit
Ein Handy gilt als **zu Hause**, solange es aus dem Heimnetz mit dem PC verbunden ist. Gehst du (ca. 5 Minuten ohne Verbindung) oder kommst du an, führt der PC deine Sätze aus: *Wenn ich gehe*, *Wenn alle weg sind*, *Wenn jemand ankommt*, *Wenn der Erste ankommt*, z. B. „Mach das Licht aus; pausiere die Musik“ (mehrere Schritte mit `;`).

## 10.7 Was Yume sich merkt

„Merk dir, dass ich morgens keine Regenhinweise mag.“ Yume speichert das dauerhaft und nutzt es in jedem Chat, Briefing und jeder Routine. Unter *What Yume remembers* siehst du alles, kannst aktualisieren und **Ausgewählte löschen**.

## 10.8 Gespräche und Stimmung

* **Stimmungs-Gespür:** Yume erkennt Müdigkeit, Stress oder Traurigkeit an deinen Worten und Tageszeit (einfache Wortlisten, kein Modell, keine Cloud) und antwortet passend; die Stimmung hält etwa **40 Minuten**.
* **Stimm-Gespür (experimentell):** schätzt aus Lautstärke, Tonhöhe, Betonung und Tempo, wie du klingst, verglichen mit deinen eigenen Normalwerten (lernt nach ca. 10 Sätzen). **Es werden nur Zahlen ausgewertet; keine Aufnahme wird gespeichert.** Das Ergebnis färbt nur den Ton der Antworten und kann falsch liegen.
* **Denkmodus des Sprachmodells** (langsamer, besser für harte Fragen). Aus = schnellere Antworten und zuverlässigere Werkzeugaufrufe (Modelle wie Qwen3).
* **Selbsttest:** *Selbsttest starten* prüft alles, wovon Yume abhängt (Modelle, Dienste, Verbindungen), und sagt in Klartext, was fehlt und was zu tun ist. Auch im Dashboard.

## 10.9 Tagebuch

„Schreib ins Tagebuch: …“ oder abends einfach erzählen. Die Einträge der letzten Wochen stehen in der Liste. Sie fließen in den Wochenrückblick ein.

## 10.10 Wissensdatenbank (deine Dokumente)

Yume durchsucht **deine** PDFs, Word-Dateien, Markdown, Text, CSV und HTML-Dateien („Was steht im Mietvertrag zur Kündigung?“).

1. **Ordner hinzufügen …**, **Dokumente jetzt lesen** (nur neue/geänderte Dateien werden neu gelesen).
2. Yume antwortet mit Dateiname und Stelle.
3. Optional **bedeutungsbasierte Suche** (findet auch Passagen ohne gleiche Wörter; lädt einmalig ein Modell, ca. 470 MB).

Alles bleibt auf dem PC: lokale SQLite-Datenbank mit Volltextsuche (Teilwörter finden „Kündigung“ in „Kündigungsfrist“). Der Index lässt sich neu aufbauen und ist deshalb **nicht** Teil der Backups; die Ordnerliste schon.

## 10.11 Hintergrund-Aufträge, Abläufe und Skills

| Funktion | Beispiel |
| --- | --- |
| **Aufträge** (Jobs) | Aufgaben, an denen Yume selbstständig arbeitet („Recherchiere … und sag es mir morgen früh“) |
| **Abläufe** (Makros) | per Sprache beigebracht: „Merk dir das als Ablauf *Feierabend*: Licht aus, Musik an, Wecker prüfen.“ Jeder Schritt wird wie ein gesprochener Befehl ausgeführt |
| **Skills** | kleine Python-Programme, die Yume sich selbst schreibt, wenn ihr eine Fähigkeit fehlt („Hol mir den Bitcoin-Preis“) |

**Skill-Sicherheit:** Ein Skill wird erst gespeichert, **nachdem du den Code gelesen und bestätigt hast**. Vorher prüft die App statisch (keine Prozesse, kein Schreiben/Löschen von Dateien, kein dynamischer Code, keine rohen Sockets, keine Registry). Er läuft in einem eigenen kurzlebigen Python-Prozess (25 s Zeitlimit, begrenzte Ausgabe), nie im Programm. Wird die Datei nach der Freigabe geändert, braucht sie eine neue Freigabe. *Skills-Ordner öffnen* zeigt die Dateien. Das ist ein Sicherheitsnetz, kein vollständiger Sandkasten: Der wirkliche Schutz bist du, der den Code freigibt. Skills dürfen das Internet nutzen.

## 10.12 Personen und Reisen

„Anna hat am 12. Mai Geburtstag und mag keine Pilze“, „Was habe ich Anna das letzte Mal geschenkt?“ Geburtstage (auch aus den Handy-Kontakten), Notizen, Geschenkideen und **geplante Reisen**. Yume erinnert an Geburtstage und nutzt alles in ihren Antworten.

## 10.13 Orte in der Nähe

„Wo ist die nächste Apotheke, die noch offen hat?“ Daten aus **OpenStreetMap** (Overpass). Ausgangspunkt: Handy-Standort, sonst Heimadresse. Öffnungszeiten werden aus dem OSM-Tag `opening_hours` gelesen; ist eine Regel zu kompliziert, steht „unbekannt“.

## 10.14 Dokumente: Briefe, Rechnungen, Lebenslauf

Yume schreibt aus deinen Diktaten **Briefe, Rechnungen, freie Dokumente und Lebensläufe** als **PDF und/oder Word-Datei**. Rechnungssummen werden **im Programm berechnet, nie vom Sprachmodell**.

1. Unter **Meine Angaben (für Briefe und Rechnungen)** Name, Firma (optional), Straße, PLZ/Ort, E-Mail, Telefon, IBAN, BIC, Steuernummer eintragen; Haken **Kleinunternehmer** (keine USt. nach § 19 UStG).
2. „Schreib eine Rechnung an …“ im Chat. Dateien liegen in `Dokumente\Yume Dokumente` (Knopf *Dokumente-Ordner öffnen*). PDFs entstehen mit Qt, Word-Dateien mit python-docx.

## 10.15 Eingang („Teilen → Yume“)

Vom Handy mit **Teilen → Yume** schickst du Sprachnachrichten (z. B. aus WhatsApp), Bilder, Screenshots, PDFs, Word-Dateien, Texte oder Links an den PC. Sie landen in `Downloads\Yume Eingang`. Yume liest sie auf Zuruf („Was steht in dem Ding, das ich dir geschickt habe?“): Sprachnachrichten werden **transkribiert** (Whisper), Bilder **beschrieben** (Vision-Modell), PDFs/Word/Text **gelesen** und können zusammengefasst oder weiterverarbeitet werden.

## 10.16 Schnellbefehle ohne Sprachmodell

Kurze, klare Befehle erkennt die App **ohne das Modell** und führt sie sofort aus; die KI bestätigt nur mit eigenen Worten. Beispiele: „Stopp die Musik“, „nächster Song“, „öffne WhatsApp“, „Taschenlampe an“, „lauter“, „Antworte ich komme gleich“ (antwortet am Handy auf die letzte Nachricht), „Wochenbericht“. Alles andere geht wie gewohnt ans Modell.

## 10.17 Hey Yume am PC

Yume **lauscht im Hintergrund** (auch bei geschlossenem Chat) auf deine Weck-Phrase. Hört sie diese, erscheint unten rechts eine kleine Karte mit ihrem 3D-Modell (VRM), du sprichst, sie antwortet.

| Einstellung | Bedeutung |
| --- | --- |
| **Auf Weck-Phrase lauschen** | ein/aus |
| **Weck-Phrase** | z. B. „Hey Yume“ |
| **Wach bleiben nach dem letzten Satz** | Sekunden |
| **3D-Modell (VRM) in der Karte zeigen** | ein/aus |
| **Kurzer Ton beim Aufwachen** | ein/aus |
| **Karte jetzt zeigen (Test)** | Vorschau |

Gebaut aus den vorhandenen Bausteinen (Mikrofon mit Sprachaktivitätserkennung, Echo-Schutz, Whisper): Jedes Gehörte wird nur auf die Weck-Phrase geprüft; **nichts wird gespeichert oder gesendet**.

## 10.18 Wie die Anbindung an Handy und Wandmodus zusammenhängt

* Handy-Chat und PC-Chat benutzen dieselben Listen, Termine, Erinnerungen.
* Der **Wandmodus** des Handys zeigt Uhr, Wetter, Termine, Erinnerungen, Listen, Geburtstage, Musik und Mails (alle 20 Sekunden aktualisiert), siehe [Kapitel 11](11-android-app.md).
