"""People and occasions: birthdays, what you know about someone, gift ideas and what you gave last time.
Stored in %LOCALAPPDATA%\\YumeCompanion\\people.json (goes into the profile backup with the other organizer data)."""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import date, datetime
from pathlib import Path

FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "people.json"
_lock = threading.RLock()


def _load() -> dict:
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save(data: dict):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def _key(name: str) -> str:
    return " ".join(re.sub(r"[^\w\säöüß-]", " ", str(name or "").lower()).split())


def parse_birthday(text) -> str:
    """-> 'MM-DD' or 'YYYY-MM-DD' ('' when it cannot be read). Accepts 12.05. / 12.05.1990 / 1990-05-12 / --05-12 / 05-12."""
    s = str(text or "").strip()
    if not s:
        return ""
    m = re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return f"{y:04d}-{mo:02d}-{d:02d}" if 1 <= mo <= 12 and 1 <= d <= 31 else ""
    m = re.fullmatch(r"-{0,2}(\d{1,2})-(\d{1,2})", s)
    if m and 1 <= int(m.group(1)) <= 12 and 1 <= int(m.group(2)) <= 31:
        return f"{int(m.group(1)):02d}-{int(m.group(2)):02d}"
    m = re.fullmatch(r"(\d{1,2})\.\s?(\d{1,2})\.?\s?(\d{4})?", s)
    if m and 1 <= int(m.group(2)) <= 12 and 1 <= int(m.group(1)) <= 31:
        mo, d = int(m.group(2)), int(m.group(1))
        return f"{int(m.group(3)):04d}-{mo:02d}-{d:02d}" if m.group(3) else f"{mo:02d}-{d:02d}"
    return ""


def get(name: str) -> dict | None:
    data = _load()
    key = _key(name)
    if key in data:
        return data[key]
    hits = [p for k, p in data.items() if key and (k.startswith(key) or key in k.split() or key in k)]
    return hits[0] if len(hits) == 1 else None


def add_or_update(name: str, relation: str = "", birthday: str = "", note: str = "", gift: str = "", year: int | None = None) -> tuple[dict | None, dict | None]:
    """-> (new record, previous record or None). Notes and gifts are appended."""
    key = _key(name)
    if not key:
        return None, None
    with _lock:
        data = _load()
        old = json.loads(json.dumps(data.get(key))) if key in data else None
        p = data.setdefault(key, {"name": " ".join(str(name).split())[:50], "relation": "", "birthday": "", "notes": [], "gifts": []})
        if relation:
            p["relation"] = relation.strip()[:40]
        if birthday:
            b = parse_birthday(birthday)
            if b:
                p["birthday"] = b
        if note and note.strip() and note.strip() not in p["notes"]:
            p["notes"].append(note.strip()[:200])
        if gift and gift.strip():
            p["gifts"].append({"what": gift.strip()[:100], "year": int(year or date.today().year)})
        _save(data)
        return p, old


def restore(name: str, old: dict | None):
    key = _key(name)
    with _lock:
        data = _load()
        if old is None:
            data.pop(key, None)
        else:
            data[key] = old
        _save(data)


def remove(name: str) -> dict | None:
    key = _key(name)
    with _lock:
        data = _load()
        if key not in data:
            hit = get(name)
            key = _key(hit["name"]) if hit else key
        gone = data.pop(key, None)
        if gone is not None:
            _save(data)
        return gone


def list_people() -> list[dict]:
    return sorted(_load().values(), key=lambda p: p["name"].lower())


def describe(p: dict) -> str:
    lines = [p["name"] + (f" ({p['relation']})" if p.get("relation") else "")]
    if p.get("birthday"):
        lines.append("Geburtstag: " + _fmt_birthday(p["birthday"]))
    if p.get("notes"):
        lines.append("Wichtig: " + "; ".join(p["notes"]))
    if p.get("gifts"):
        lines.append("Bisherige Geschenke: " + "; ".join(f"{g['what']} ({g['year']})" for g in p["gifts"][-6:]))
    return "\n".join(lines)


def _fmt_birthday(b: str) -> str:
    return datetime.strptime(b, "%Y-%m-%d").strftime("%d.%m.%Y") if len(b) == 10 else datetime.strptime("2000-" + b, "%Y-%m-%d").strftime("%d.%m.")


def upcoming_birthdays(days: int = 30, today: date | None = None) -> list[dict]:
    """[{'name','in_days','date','age','person'}] sorted by date; today counts as in_days = 0."""
    today = today or date.today()
    out = []
    for p in _load().values():
        b = p.get("birthday")
        if not b:
            continue
        try:
            month, day = (int(b[5:7]), int(b[8:10])) if len(b) == 10 else (int(b[:2]), int(b[3:5]))
            year = int(b[:4]) if len(b) == 10 else None
            nxt = date(today.year, month, day) if not (month == 2 and day == 29) else date(today.year, 3, 1)
            if nxt < today:
                nxt = date(today.year + 1, month, day) if not (month == 2 and day == 29) else date(today.year + 1, 3, 1)
        except ValueError:
            continue
        delta = (nxt - today).days
        if delta <= days:
            out.append({"name": p["name"], "in_days": delta, "date": nxt, "age": (nxt.year - year) if year else None, "person": p})
    return sorted(out, key=lambda x: x["in_days"])


def birthday_text(items: list[dict]) -> str:
    lines = []
    for i in items:
        when = "heute" if i["in_days"] == 0 else ("morgen" if i["in_days"] == 1 else f"in {i['in_days']} Tagen ({i['date'].strftime('%d.%m.')})")
        age = f", wird {i['age']}" if i["age"] else ""
        hint = ""
        if i["person"].get("gifts"):
            g = i["person"]["gifts"][-1]
            hint += f" Letztes Geschenk: {g['what']} ({g['year']})."
        if i["person"].get("notes"):
            hint += " Wichtig: " + "; ".join(i["person"]["notes"][:3]) + "."
        lines.append(f"{i['name']} hat {when} Geburtstag{age}.{hint}")
    return "\n".join(lines)


def import_contacts(rows: list[tuple[str, str]]) -> int:
    """rows = [(name, birthday text)] from the phone's contacts. Existing birthdays are kept. Returns how many people were added or completed."""
    n = 0
    with _lock:
        data = _load()
        for name, bday in rows:
            key = _key(name)
            b = parse_birthday(bday)
            if not key or not b:
                continue
            p = data.setdefault(key, {"name": " ".join(name.split())[:50], "relation": "", "birthday": "", "notes": [], "gifts": []})
            if not p["birthday"]:
                p["birthday"] = b
                n += 1
        _save(data)
    return n
