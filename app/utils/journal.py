"""Journal: short entries about the day (what happened, how it felt), written by the user's words through Yume.
Stored in %LOCALAPPDATA%\\YumeCompanion\\journal.json (goes into the profile backup with the other organizer data)."""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime, timedelta
from pathlib import Path

from app.utils import mood as mood_mod

FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "journal.json"
_lock = threading.RLock()


def _load() -> list[dict]:
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(items: list[dict]):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def add(text: str, when: datetime | None = None) -> dict | None:
    text = " ".join(str(text or "").split())[:600]
    if len(text) < 3:
        return None
    when = when or datetime.now()
    item = {"id": uuid.uuid4().hex[:6], "date": when.strftime("%Y-%m-%d"), "time": when.strftime("%H:%M"), "text": text,
            "mood": _guess(text)}
    with _lock:
        items = _load()
        items.append(item)
        _save(items[-1500:])
    return item


def _guess(text: str) -> str:
    low = text.lower()
    best, found = 0, ""
    for mood, words in mood_mod.WORDS.items():
        hits = sum(1 for w in words if w in low)
        if hits > best:
            best, found = hits, mood
    return found


def entries(days: int = 7, query: str = "") -> list[dict]:
    since = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    q = (query or "").lower()
    return [i for i in _load() if i["date"] >= since and (not q or q in i["text"].lower())]


def has_today() -> bool:
    today = datetime.now().strftime("%Y-%m-%d")
    return any(i["date"] == today for i in _load())


def remove(key: str) -> list[dict]:
    key = str(key or "").strip().lower()
    with _lock:
        items = _load()
        gone = [i for i in items if i["id"] == key or (key and key in i["text"].lower())] if key not in ("", "all") else []
        if gone:
            _save([i for i in items if i not in gone])
    return gone


def restore(items: list[dict]):
    with _lock:
        cur = _load()
        ids = {i["id"] for i in cur}
        _save(sorted(cur + [i for i in items if i["id"] not in ids], key=lambda i: (i["date"], i["time"])))


def format_text(items: list[dict]) -> str:
    if not items:
        return "Keine Einträge."
    out, day = [], ""
    for i in sorted(items, key=lambda i: (i["date"], i["time"])):
        if i["date"] != day:
            day = i["date"]
            out.append(datetime.strptime(day, "%Y-%m-%d").strftime("%a %d.%m.%Y") + ":")
        out.append(f"  {i['time']}  {i['text']}" + (f"  [{i['mood']}]" if i.get("mood") else "") + f"  [id {i['id']}]")
    return "\n".join(out)
