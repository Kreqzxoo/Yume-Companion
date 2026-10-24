"""Who is speaking? The phone tells the PC with every sentence: 'owner', the name of an enrolled guest, 'unknown' - or nothing (voices are not told apart).

Anything but the owner / nothing gets only harmless tools (music, weather, time, calculator, web search, nearby places); private tools
(mail, calendar, notes, files, contacts, phone ...) stay locked for that turn, and the character is told who is speaking.
"""
from __future__ import annotations

import time

GUEST_TOOLS = {"spotify", "weather", "get_current_datetime", "calculator", "web_search", "nearby"}
_state = {"who": "", "t": 0.0}
VALID_AGE_S = 120


def set_speaker(who: str):
    _state.update(who=str(who or "").strip()[:40], t=time.time())


def current() -> str:
    """The speaker of the running turn when it is NOT the owner ('' = no restriction)."""
    who = _state["who"]
    if not who or who == "owner" or time.time() - _state["t"] > VALID_AGE_S:
        return ""
    return who


def note(who: str) -> str:
    person = "eine unbekannte Person" if who == "unknown" else f"{who} (ein Gast, nicht der Besitzer)"
    return (f"Wichtig: Gerade spricht {person}, NICHT der Besitzer. Gib keine privaten Informationen des Besitzers preis (Termine, Mails, Nachrichten, Kontakte, Notizen, "
            "Tagebuch, Dateien, Standort). Dafür sind die Werkzeuge gesperrt; sag freundlich, dass du das nur dem Besitzer erzählst. Musik, Wetter, Uhrzeit, Rechnen, Recherche "
            "und Smalltalk sind in Ordnung.")
