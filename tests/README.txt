Yume Tests - Entwickler-Tests (gehoeren nicht zum Programm und werden nicht mit ausgeliefert).

Start (im Ordner dieser Datei):   powershell -File run_tests.ps1 [-Project "Pfad zum Yume-Ordner"]

test_quick_commands.py        Schnellbefehle ohne KI: erkennt die richtigen Saetze, ignoriert andere (offline, sicher)
test_organizer.py             Kalender (eigene Termine, ICS mit Wiederholungen), Erinnerungen, Mail-Auswertung (offline, sicher)
test_routines.py              Morgen-Briefing und Gute-Nacht-Routine: Satzerkennung und Zusammenstellung der Daten
test_lists_memory.py          Listen (Einkauf/To-do), Satzerkennung dafür und das Merken von Vorlieben
test_undo.py                  Aktivitätsverlauf: jede Aktion (Erinnerung, Termin, Liste, Merkliste) lässt sich rückgängig machen
test_mood_journal.py          Stimmungs-Hinweise, Tagebuch (Werkzeug, Schnellsatz, Rückgängig), Gute-Nacht-Frage nach dem Tag
test_scenes.py                Erkennung von Home-Assistant-Szenen per Satz
test_inbox.py                 Eingang: Upload-Endpunkt, Werkzeug lesen/transkribieren (Whisper simuliert)
test_knowledge.py             Wissensdatenbank: Einlesen (txt, md, docx), deutsche Volltextsuche, Änderungen und gelöschte Dateien
test_rain_alert.py            Regen-Alarm-Logik (Handy unterwegs / zu Hause / kein Regen / ausgeschaltet)
test_weather_tips.py          Kleidungstipps (offline) und Wettertext mit Tipp (mit --live)
test_commute.py               Pünktlichkeits-Assistent (braucht Internet, nur mit -Live)
test_dashboard_extra.py       Dashboard-Daten /api/extra (nutzt die echte Konfiguration, liest nur)
test_spotify_live.py          Spotify-Zugang: Geraete, Suche, Wiedergabe-Status (liest nur, startet nichts)
test_llm_tool_decision.py     Fragt den echten LLM-Server, ob er bei Musik-Saetzen das richtige Werkzeug waehlt

Die letzten drei brauchen eine laufende Verbindung (LLM-Server / Spotify-Anmeldung) und werden nur auf Wunsch ausgefuehrt (-Live).
