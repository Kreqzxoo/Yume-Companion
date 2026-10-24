"""Mood awareness: a light-weight guess from the user's words and the time of day, handed to the character as a hint (how to answer).

No model, no cloud: simple word lists. The mood sticks for 40 minutes (a "tired" message colours the next replies, too).
"""
from __future__ import annotations

import re
import time
from datetime import datetime, timedelta

WORDS = {
    "tired": ("müde", "erschöpft", "kaputt", "ausgelaugt", "schlapp", "gähn", "kein bock mehr", "brauche schlaf", "schlecht geschlafen", "total fertig"),
    "stressed": ("stress", "überfordert", "deadline", "keine zeit", "genervt", "nervt", "wütend", "ärger", "sauer", "druck", "hektik", "zu viel zu tun", "überlastet"),
    "sad": ("traurig", "einsam", "deprimiert", "schlecht drauf", "heul", "vermisse", "mir geht es nicht gut", "mir geht's nicht gut", "alleine", "hoffnungslos", "down"),
    "sick": ("krank", "kopfschmerz", "erkältet", "fieber", "übel", "bauchschmerz", "halsschmerz", "grippe"),
    "happy": ("super", "freue mich", "geil", "yeah", "juhu", "glücklich", "toll", "endlich geschafft", "bestanden", "gute laune", "bin so happy"),
}
HINTS = {
    "tired": "{{user}} seems tired. Answer softly and short, no long lists, no jokes that need energy; if it fits, gently suggest rest.",
    "stressed": "{{user}} seems stressed or annoyed. Stay calm and supportive, get to the point, offer to take something off their plate; no teasing.",
    "sad": "{{user}} seems sad or lonely. Be warm and present, take the feelings seriously, ask gently; no cheerful dismissal, no fixing at once.",
    "sick": "{{user}} seems unwell. Be caring, keep it short, remind about rest and drinking; mention a doctor only if it sounds serious.",
    "happy": "{{user}} is in a good mood. Share the joy, be playful and energetic.",
    "late": "It is very late at night. Keep replies calm and short, and do not start long topics; a gentle hint to sleep is fine if {{user}} is still up.",
}
_state = {"mood": "", "t": 0.0}


import json
import os
from pathlib import Path

LOG = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "mood_log.json"
LABELS = {"tired": "müde", "stressed": "gestresst", "sad": "traurig", "sick": "angeschlagen", "happy": "fröhlich"}
DAYS = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]


def _log(mood: str):
    """Counts the mood of this message for today (words only; 'late' and forced hints are not moods)."""
    if mood not in LABELS:
        return
    try:
        try:
            data = json.loads(LOG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
        day = datetime.now().strftime("%Y-%m-%d")
        data.setdefault(day, {})
        data[day][mood] = data[day].get(mood, 0) + 1
        for old in sorted(data)[:-120]:
            data.pop(old, None)
        LOG.parent.mkdir(parents=True, exist_ok=True)
        LOG.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def summary(days: int = 7) -> str:
    """'müde an 3 Tagen (Di, Mi, Do), gestresst an 2 Tagen (Mo, Fr)' - '' when nothing was noticed."""
    try:
        data = json.loads(LOG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    per: dict = {}
    for day, counts in data.items():
        if day < since:
            continue
        weekday = DAYS[datetime.strptime(day, "%Y-%m-%d").weekday()]
        for mood, n in counts.items():
            if mood in LABELS and n >= 1:
                per.setdefault(mood, []).append(weekday)
    if not per:
        return ""
    return "; ".join(f"{LABELS[m]} an {len(d)} Tag{'en' if len(d) != 1 else ''} ({', '.join(d)})" for m, d in sorted(per.items(), key=lambda kv: -len(kv[1])))


def detect(text: str, now: datetime | None = None) -> str:
    """Returns the mood key for this message ('' when neutral). Remembers it for 40 minutes."""
    now = now or datetime.now()
    low = re.sub(r"\s+", " ", (text or "").lower())
    found = ""
    best = 0
    for mood, words in WORDS.items():
        hits = sum(1 for w in words if w in low)
        if hits > best:
            best, found = hits, mood
    if found:
        _state.update(mood=found, t=time.time())
        _log(found)
        return found
    if _state["mood"] and time.time() - _state["t"] < 40 * 60:
        return _state["mood"]
    if now.hour >= 23 or now.hour < 5:
        return "late"
    return ""


def from_voice(label: str):
    """The voice sounded tired / stressed / ...: a weaker hint than words (about 10 minutes)."""
    if label in LABELS:
        _state.update(mood=label, t=time.time() - 30 * 60)
        _log(label)


def force(mood: str = "late"):
    """The phone is in quiet mode: calm, short answers for the next 40 minutes."""
    _state.update(mood=mood, t=time.time())


def hint_block(text: str, now: datetime | None = None) -> str:
    mood = detect(text, now)
    return ("[MOOD HINT - never mention that you noticed or guessed it]\n" + HINTS[mood]) if mood else ""
