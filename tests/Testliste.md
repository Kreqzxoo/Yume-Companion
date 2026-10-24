# Yume – Testliste (Handy + PC)

Vorher: BETA-App am PC komplett neu starten, neue APK (`tools\android\Yume-Companion.apk`) am Handy installieren, LLM-Server auf Version 1.0.1 mit Kontext 16384.
Wo etwas schiefgeht: `logs\tool_log.jsonl` (Werkzeug-Aufrufe), `logs\sow_*.log`, `logs\exit_debug.log` (nur wenn die App beim Beenden hängt).

## 1. Grundlagen
- [ ] PC-App startet ohne Fehlermeldung, Fenster schließen → nach spätestens 8 s ist kein Yume-Prozess mehr im Task-Manager
- [ ] Handy verbindet sich (grün „Heimnetz“), Chat zeigt den Verlauf
- [ ] Dashboard (Einstellungen > Dashboard) startet; Karten „LLM-Server“ zeigt n_ctx 16384 und 1 Slot, keine rote Warnung
- [ ] Dashboard-Karte „Handy“ zeigt „verbunden“

## 2. Schnellbefehle (ohne KI, sofort) – am Handy tippen oder sprechen
- [ ] „Stopp die Musik“ → Musik pausiert, Status ✓ erscheint, Yume bestätigt kurz
- [ ] „Musik weiter“, „Nächster Song“, „Vorheriger Titel“
- [ ] „Was läuft gerade?“, „Leiser“ / „Lauter“, „Musik Lautstärke 30“
- [ ] „Öffne WhatsApp“ (öffnet am Handy), „Taschenlampe an / aus“
- [ ] „Öffne WhatsApp auf dem PC“ → geht NICHT über den Schnellweg, sondern öffnet am PC

## 3. Spotify (Einstellungen > Spotify)
- [ ] Seite zeigt „Mit Spotify verbunden“, „Läuft gerade“ zeigt den Titel
- [ ] Handy: Spotify-Anmeldung kommt automatisch vom PC (Einstellungen am Handy: „verbunden“)
- [ ] „Spiel Last Christmas“ → richtiger Titel läuft (aktives Gerät ist ggf. der Fernseher; „auf dem Handy“ dazusagen)
- [ ] „Spiel meine Playlist Car“, „Spiel was von den Ärzten“, „Füge … zur Warteschlange hinzu“
- [ ] Dashboard-Karte Spotify: Titel + ⏮ ⏯ ⏭ funktionieren

## 4. Kalender, Erinnerungen, Mail (Einstellungen > Organizer)
- [ ] „Trag morgen um 15 Uhr Zahnarzt ein“ → Termin erscheint in der Liste unten
- [ ] „Was steht heute / diese Woche in meinem Kalender?“
- [ ] Optional: Google-iCal-Link eintragen → „Speichern und testen“ nennt die Anzahl der Termine
- [ ] „Erinnere mich in 2 Minuten an die Wäsche“ → nach 2 Min Meldung am PC UND Benachrichtigung am Handy
- [ ] „Zeig meine Erinnerungen“, „Lösche alle Erinnerungen“
- [ ] Mail: IMAP-Server + App-Passwort eintragen → „Speichern und testen“ sagt „Verbunden“
- [ ] „Habe ich neue Mails?“ / „Fass meine ungelesenen Mails zusammen“ (es wird nichts als gelesen markiert)

## 5. Routinen (Einstellungen > Organizer > Routinen)
- [ ] Ort eintragen → „Ort speichern und Wetter testen“ zeigt das Wetter
- [ ] „Morgen-Briefing jetzt testen“ → Yume sagt Wetter, Termine, Erinnerungen, Mails
- [ ] „Guten Morgen“ tippen → Briefing; „Wie war dein Morgen?“ → KEIN Briefing
- [ ] „Gute Nacht“ → Musik pausiert, Taschenlampe aus, sagt Wecker + Termine morgen
- [ ] Automatik: Zeit auf 2 Minuten in der Zukunft stellen, Haken „automatisch“ → Briefing kommt (auf dem Handy, wenn verbunden)

## 6. Handy-Wake-Word und Statuszeile
- [ ] Wake Word → Overlay öffnet sich, Begrüßung klingt normal (nicht „kaputt“), danach hört sie zu
- [ ] „Öffne Spotify“ per Sprache → Statuszeile „Öffne Spotify …“ → ✓
- [ ] Chat: bei jedem Werkzeug erscheint oberhalb der Eingabe die Statuszeile
- [ ] Bei ausgeschaltetem PC: rote Meldung im Panel („PC nicht erreichbar …“)

## 7. Fehlermeldungen
- [ ] LLM-Server stoppen → Chat zeigt „Der LLM-Server ist nicht erreichbar (…)“ statt eines Fehlertextes
- [ ] Danach wieder starten → Antwort kommt normal

## 8. Backup
- [ ] Backup erstellen (`.yumepack`), wieder einspielen → Neustart-Dialog „Ja“ → App startet von selbst neu
- [ ] Nach Neuinstallation der APK + Backup: 3D-Modell lädt (oder lädt sich automatisch nach)

## Wenn etwas nicht klappt
Notiere: was gesagt/getippt, was passiert ist, Uhrzeit – und schick mir die letzten Zeilen aus `logs\tool_log.jsonl` und dem neuesten `logs\sow_*.log`.

---
## Nachtrag: neue Funktionen (nach der ersten Testrunde)

### 9. Handy ohne PC (Schnellbefehle am Handy)
PC ausschalten oder Handy ins Mobilnetz, dann am Handy sagen/tippen:
- [ ] „Taschenlampe an / aus“, „Öffne WhatsApp“, „Wie spät ist es?“, „Akkustand“
- [ ] „Stelle einen Timer auf 5 Minuten“, „Weck mich morgen um 6:30“
- [ ] „Navigiere nach Hamburg Hauptbahnhof“ → Google Maps startet die Route
- [ ] „Lies mir meine Nachrichten vor“
- [ ] Mit Spotify-Anmeldung am Handy: „Spiel Last Christmas“, „Stopp die Musik“, „Nächster Song“, „Was läuft gerade?“
- [ ] Ohne Offline-Modell funktioniert das trotzdem (nur die Spracherkennung muss geladen sein)

### 10. Sicherheits-PIN (Handy-Einstellungen)
- [ ] PIN festlegen (4–8 Ziffern); danach „Ruf Mama an“ → Benachrichtigung hat ein Eingabefeld „PIN eingeben“
- [ ] Richtige PIN → Anruf-Abfrage geht weiter; falsche PIN → „Falsche PIN. Aktion abgelehnt.“
- [ ] 3× falsch → 5 Minuten gesperrt
- [ ] PIN entfernen → wieder „Erlauben / Ablehnen“

### 11. Merkliste, Listen, Denk-Modus (Einstellungen > Organizer)
- [ ] „Merk dir, dass mein Hund Rex heißt“ → erscheint unter „Das merkt sich Yume“; später: „Wie heißt mein Hund?“
- [ ] „Setz Milch und Brot auf die Einkaufsliste“ → Antwort sofort; „Was muss ich noch kaufen?“; „Streich Milch durch“
- [ ] Denk-Modus aus (Standard): Antworten kommen schnell; an: langsamer, aber ausführlicher

### 12. „Wenn ich nach Hause komme“ (Handy-Einstellungen > Automatisierung)
- [ ] „Aktuelles WLAN übernehmen“ (Standort-Berechtigung nötig), Satz z. B. „Guten Abend“ eintragen, Schalter an
- [ ] „Jetzt ausprobieren“ → Satz wird ausgeführt (PC erreichbar → geht an den PC, sonst Schnellbefehl)
- [ ] WLAN aus- und wieder einschalten (nach mehr als 30 Minuten Abstand) → Satz läuft von selbst

---
## Nachtrag 2: zweite Funktionsrunde

### 13. Selbsttest, Verlauf, Wächter
- [ ] Organizer-Seite > „Selbsttest starten“ (auch im Dashboard): grüne/gelbe/rote Punkte mit Hinweis, was fehlt
- [ ] „Das hat Yume heute getan“ listet Aktionen; Eintrag mit ↶ markieren > „Rückgängig“; per Sprache: „Mach das rückgängig“
- [ ] Alarm im Dashboard „Das letzte Backup ist … Tage alt“ (nach 14 Tagen ohne Backup); Daten (Erinnerungen, Listen, Merkliste, Tagebuch, Routinen) sind nach einem Backup + Wiederherstellen wieder da

### 14. Handy-Statuszeile
- [ ] Im Chat erscheint zwischen den Werkzeugen „denkt nach … / schreibt … / spricht …“

### 15. Pünktlichkeit, Pakete
- [ ] Organizer > Routinen: Heimadresse eintragen; Termin mit Ort anlegen („Trag morgen 15 Uhr Zahnarzt in Hamburg Rathaus ein“) > „Wann muss ich los?“ nennt Fahrzeit + Losfahrzeit
- [ ] Ca. 20 Minuten vor der Losfahrzeit kommt von selbst eine Meldung am PC und Handy
- [ ] Mail eingerichtet: „Welche Pakete kommen?“ nennt Sendungen mit Status (unterwegs / zugestellt) und Sendungsnummer; im Morgen-Briefing steht „Pakete unterwegs“

### 16. Stimmung, Tagebuch
- [ ] „Ich bin so müde“ > Antworten werden weicher und kürzer; Schalter „Stimmungs-Gespür“ im Organizer
- [ ] „Schreib ins Tagebuch: heute war ich wandern“ > Eintrag in der Liste (Organizer > Tagebuch); „Wie war meine Woche?“
- [ ] „Gute Nacht“ fragt kurz nach deinem Tag, wenn heute noch nichts im Tagebuch steht

### 17. Dateien, Szenen
- [ ] „Finde die Rechnung vom Strom“ / „Woran habe ich gestern gearbeitet?“ (Dateiliste); „Öffne …“ fragt vorher nach
- [ ] Home Assistant eingerichtet, Szenen freigegeben: „Filmabend“ startet die Szene

### 18. Kamera, Teilen, Dolmetscher, Auto, Ruhemodus (Handy)
- [ ] Kamera aufs Objekt halten: „Was ist das?“ / „Lies mir das vor“ / „Was siehst du auf meinem Bildschirm?“
- [ ] WhatsApp-Sprachnachricht lange drücken > Teilen > Yume: Yume fasst sie kurz zusammen (Whisper am PC); auch Foto, Screenshot, PDF, Text/Link; Ordner `Downloads\Yume Eingang`
- [ ] „Dolmetscher Englisch“ > alles Gesagte/Getippte wird übersetzt und auf Englisch gesprochen; „Dolmetscher aus“
- [ ] Auto-Modus: Nachricht kommt, Yume liest sie vor; „Antworte ich bin in 10 Minuten da“ > Rückfrage (PIN) > Antwort geht an den Absender
- [ ] Ruhemodus (Einstellungen): im Zeitfenster ist die Stimme leiser und die Antworten kurz und ruhig

---
## Nachtrag 3: Wissensdatenbank, Kleidung, Regen-Alarm

### 19. Wissensdatenbank (Einstellungen > Organizer)
- [ ] „Ordner hinzufügen …“ (z. B. Dokumente mit Verträgen, Anleitungen), danach liest Yume die Dateien ein (Status: „x Dateien, y Abschnitte“)
- [ ] „Was steht im Mietvertrag zur Kündigung?“ → Antwort mit Dateiname und Seite; „Wie lange läuft die Garantie der Waschmaschine?“
- [ ] Datei ändern / löschen → nach dem nächsten Einlesen (Knopf oder automatisch alle 6 Stunden) stimmt die Antwort
- [ ] Nichts passt → Yume sagt ehrlich „nichts gefunden“ (erfindet nichts)

### 20. Kleidung und Regen
- [ ] Morgen-Briefing / „Brauche ich morgen eine Jacke?“ nennt einen Kleidungstipp (Temperatur, Regen, Wind, UV)
- [ ] Heimadresse + Handy-Standort-Freigabe eintragen; draußen sein: ca. 20–60 Minuten vor Regen kommt eine Benachrichtigung „Regen im Anmarsch“ (nicht zu Hause, nicht nachts, höchstens alle 3 Stunden)

---
## Nachtrag 4: Aufträge, Abläufe, Fähigkeiten, Personen, Reisen, Hey Yume, Wand-Modus, Anrufschutz

### 21. Hintergrund-Aufträge (Organizer > „Hintergrund-Aufträge, Abläufe und Fähigkeiten“)
- [ ] „Recherchiere die besten Laptops bis 800 Euro und sag mir morgen früh Bescheid“ → Auftrag erscheint in der Liste; Ergebnis kommt zur genannten Zeit (Handy-Stimme, wenn verbunden)
- [ ] „Welche Aufträge laufen?“ / „Zeig das Ergebnis“ / „Brich den Auftrag ab“

### 22. Abläufe per Sprache
- [ ] „Merk dir das als Ablauf Feierabend: Licht ausschalten, Musik pausieren, Wecker für 6:30 stellen“ → Ablauf in der Liste
- [ ] Nur „Feierabend“ sagen → die Schritte laufen nacheinander, Statuszeile „Schritt 1/3 …“, Yume fasst zusammen; „Mach das rückgängig“ löscht den Ablauf wieder, wenn er gerade neu war

### 23. Neue Fähigkeiten (Skills)
- [ ] „Bau dir eine Fähigkeit, die Euro in Dollar umrechnet“ → am PC erscheint der Code zur Freigabe; erst nach „Ja“ wird gespeichert; danach „Was sind 50 Euro in Dollar?“
- [ ] Am Handy darf Yume keine neuen Fähigkeiten bauen (Meldung „nur am PC“)

### 24. Personen und Reisen
- [ ] „Anna hat am 12. Mai Geburtstag und mag keine Pilze“ → Liste „Personen und Reisen“; „Was schenke ich Anna?“; morgens Hinweis am Tag davor und am Tag selbst
- [ ] „Importiere die Geburtstage aus meinen Kontakten“ (Handy verbunden, Kontakte-Freigabe)
- [ ] „Plane eine Reise nach Rom vom … bis …“ → Kalendereintrag + Erinnerung am Vorabend; „Wie wird das Wetter in Rom?“ → Wetter + Packtipp; „Mach mir eine Packliste“ → Liste „Packliste Rom“; „Suche meine Buchungsbestätigungen“

### 25. Suche nach Bedeutung
- [ ] Wissensdatenbank: Haken „Suche nach Bedeutung“ → einmaliger Modell-Download (ca. 470 MB), danach findet „Wie komme ich aus dem Abo raus?“ die Kündigungs-Passage ohne gleiche Wörter

### 26. Hey Yume am PC
- [ ] Organizer > „Hey Yume am PC“: Haken setzen → „Karte jetzt anzeigen (Test)“ zeigt die Karte unten rechts (mit 3D-Modell)
- [ ] „Hey Yume, wie spät ist es?“ bei geschlossenem Chat → Karte erscheint, Antwort wird gesprochen; weitere Sätze ohne Weckwort, solange sie wach ist; „Tschüss“ beendet
- [ ] Während sie spricht, reagiert sie nicht auf ihre eigene Stimme; in einem Anruf / Sprachmodus pausiert das Zuhören

### 27. Wand-/Tablet-Modus (Handy-Einstellungen)
- [ ] „Wand-/Tablet-Modus starten“: Uhr, Wetter, Termine, Erinnerungen, Listen, Geburtstage, Musik, Mail-Zahl; der Charakter als 3D-Modell (wenn geladen), Bildschirm bleibt an
- [ ] Wake Word funktioniert; Tippen auf den Charakter startet eine Frage; ✕ oder Zurück beendet
- [ ] Nachts (Zeitfenster) wird abgedunkelt (Schalter „Nachts abdunkeln“); ohne PC zeigt er die zuletzt geladenen Daten

### 28. Anrufschutz (Handy-Einstellungen)
- [ ] „Als Anrufschutz-App festlegen“ (Android-Dialog bestätigen); danach Schalter „Anrufschutz“ an
- [ ] Kontakt ruft an → Yume sagt „Anruf von <Name>“; Unbekannter → „Unbekannter Anruf von …“; Nummer mit 0900/0137/01805 → blockiert + Hinweis
- [ ] Nachts unbekannte Nummer lautlos (Schalter + Nachtzeitfenster)

### 29. Dokumente erstellen (PC)
- [ ] Organizer > „Meine Angaben“: Name, Adresse, IBAN … eintragen (bleibt nach Neustart)
- [ ] „Schreib mir eine Rechnung an Max Muster für 3 Stunden Beratung à 80 Euro“ → PDF in Dokumente\Yume Dokumente, Summe stimmt (19 % USt oder Kleinunternehmer)
- [ ] „… als Word“ → .docx; Brief und Lebenslauf; PDF sieht ordentlich aus (Layout wurde nur technisch geprüft!)
- [ ] „Öffne das Dokument“ fragt vorher nach; Aktivitätsprotokoll „Rückgängig“ löscht die Datei

### 30. Wochenbericht, Stimmungs-Verlauf, Stimm-Gespür
- [ ] „Wie war meine Woche?“ → Bericht (Termine, Aufgaben, Stimmung); Haken „Wochenrückblick“ → Sonntag 18 Uhr von selbst
- [ ] Organizer zeigt die Stimmung der letzten 14 Tage
- [ ] Stimm-Gespür (experimentell) an: nach ~10 Sätzen färbt müde/gestresste Stimme den Ton; es wird nichts aufgenommen gespeichert

### 31. Mail-Entwürfe
- [ ] „Antworte auf die Mail von … und sag zu“ → Entwurf (im Entwürfe-Ordner des Kontos, wenn Mail eingerichtet; sonst nur in Yume) – es wird NIE gesendet
- [ ] Organizer > „Mail-Entwürfe“: Liste, „Im Mail-Programm öffnen“, „Text kopieren“, Löschen

### 32. Wissen mit Quellen
- [ ] „Merk dir diese Seite: https://…“ bzw. „Speichere als Notiz: Garagencode 4711“ → danach „Wie war der Garagencode?“ nennt die Quelle („eigene Notiz“ / Web-Adresse)
- [ ] Rückgängig im Aktivitätsprotokoll entfernt die Notiz wieder

### 33. Umgebungssuche (braucht Internet)
- [ ] „Wo ist die nächste Apotheke, die noch offen hat?“ → Name, Entfernung, geöffnet/geschlossen/unbekannt; Start = Handy-Standort, sonst Heimadresse
- [ ] „Tankstelle in der Nähe“, „Bäcker in Hamburg“ (anderer Ort)

### 34. Anwesenheit (Organizer > Routinen)
- [ ] Haken „Anwesenheit“ + Satz bei „Wenn ich gehe“ (z. B. „Pausiere die Musik“)
- [ ] Handy aus dem Heim-WLAN nehmen → nach ~5 Min läuft der Satz am PC; zurückkommen → „Wenn jemand ankommt“
- [ ] Mehrere Handys: „Wenn alle weg sind“ erst, wenn das letzte weg ist. (Handy-Befehle gehen dann nicht – das Handy ist ja weg)

### 35. Stimmen unterscheiden (Handy-Einstellungen, nach „Nur auf meine Stimme“)
- [ ] „Stimmen unterscheiden“ an; Gast „Anna“ anlernen (6× Wake Word)
- [ ] Du fragst nach deinen Terminen → Antwort; Anna fragt dasselbe → Yume verweigert freundlich, Musik/Wetter gehen
- [ ] Unbekannte Stimme verhält sich wie Gast. Ist es nur eine Komfort-Sperre, keine Sicherheit!

### 36. Fahr-Dashboard (Handy, Auto-Modus)
- [ ] Auto-Modus starten (Knopf oder per Auto-Bluetooth): großer Bildschirm mit nächstem Termin, „Navigation starten“ öffnet Google Maps
- [ ] Musiktasten ⏮ ⏯ ⏭ wirken; Yume hört weiter per Sprache; „Auto-Modus beenden“
- [ ] Schalter „Fahr-Dashboard“ aus → alter Auto-Modus-Bildschirm. (Android-Auto-Anzeige im Auto: nicht möglich, Google erlaubt das nicht)

### 37. Werkzeug-Modell extern (PC-App + Yume LLM Server)
- [ ] Yume LLM Server (neu installieren): neuer Tab „Werkzeuge“ (Qwen3 4B/8B/14B, Coder 7B), „beim Start mitstarten“, Server starten → läuft auf Port 8083 (Chat-Modell 8080)
- [ ] PC-App > Werkzeuge: Erklärungskasten „Welche brauche ich?“; Feld „Werkzeug-Modell extern“: Adresse (wird aus dem Chat-Server abgeleitet), „Verbindung testen“ → ✓
- [ ] Haken setzen, „Spiel Musik von …“ / „Was steht morgen an?“ → Werkzeuge funktionieren; Server aus → Chat-Modell übernimmt (Log: „External tool model failed“)
- [ ] Achtung: zwei Modelle gleichzeitig brauchen auf dem Server-PC entsprechend Grafikspeicher

### 38. Neues Aussehen (Desktop)
- [ ] Start: Seitenleiste mit abgerundeten Karten-Schaltflächen und neuen Symbolen; „Startseite“, „Yume-Bühne“, „Werkstatt“, „Charakter-Galerie“, „Modelle“, „Einstellungen“ – alle Texte vollständig lesbar
- [ ] Jeder Eintrag öffnet die richtige Seite; der aktive Eintrag ist rosa hervorgehoben (auch nach Wechsel zwischen den Seiten)
- [ ] Hamburger-Knopf klappt die Seitenleiste ein und wieder aus (jetzt 212 px breit)
- [ ] Einstellungen: Karten mit rosa Titelbalken, Abschnitte mit Punkt; Auswahlfelder, Haken (rosa), Schaltflächen, Schieberegler sehen einheitlich aus; keine abgeschnittenen Texte
- [ ] Einstellungen > Darstellung: Farbe der Seitenleiste ändern → die Karten-Schaltflächen übernehmen die Farbe
- [ ] Über-Dialog: Quellenangabe „Fassung von Soul of Waifu (jofizcd, GPL-3.0)“ sichtbar, keine Links zur Original-Seite / Spendenseite
- [ ] Symbole im Chat, Editoren und Fensterknöpfen sind neu gezeichnet (Logos von OpenAI, Gemini usw. unverändert)

### 39. Reiner Text-Chat am Handy
- [ ] Handy-Einstellungen: „Stimme im Chat“ ist aus (neuer Standard). Schreiben mit dem Charakter → nur Text, keine Sprache, kein Ton am Handy und keine Sprachausgabe am PC (kein GPU-Last durch Sprache)
- [ ] „Stimme im Chat“ an → er spricht auch beim Schreiben; Anrufe und Wake Word sprechen immer
