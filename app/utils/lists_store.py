"""Lists ("Einkaufsliste", "To-do", any name) - simple, shared by the chat tool, the quick commands and the Organizer page.
Stored in %LOCALAPPDATA%\\YumeCompanion\\lists.json."""
from __future__ import annotations

import json
import os
import re
import threading
import uuid
from pathlib import Path

FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "lists.json"
_lock = threading.RLock()
ALIASES = {"einkauf": "Einkaufsliste", "einkaufsliste": "Einkaufsliste", "einkaufszettel": "Einkaufsliste", "shopping": "Einkaufsliste",
           "todo": "To-do", "to-do": "To-do", "todos": "To-do", "aufgaben": "To-do", "aufgabenliste": "To-do", "to do": "To-do"}


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


def canonical(name: str) -> str:
    name = " ".join(str(name or "").split()).strip(" .!?:")
    key = re.sub(r"\s+liste$", "", name.lower()) if name.lower() not in ALIASES else name.lower()
    if name.lower() in ALIASES:
        return ALIASES[name.lower()]
    if key in ALIASES:
        return ALIASES[key]
    return name[:1].upper() + name[1:] if name else "To-do"


def _find(data: dict, name: str) -> str | None:
    wanted = canonical(name).lower()
    return next((k for k in data if k.lower() == wanted), None)


def add(list_name: str, items) -> tuple[str, list[dict]]:
    """Adds one item or several (list / 'a, b und c'). Returns (list name, added items)."""
    if isinstance(items, str):
        items = [p for p in re.split(r"\s*(?:,|;|\bund\b)\s*", items) if p.strip()]
    added = []
    with _lock:
        data = _load()
        key = _find(data, list_name) or canonical(list_name)
        lst = data.setdefault(key, [])
        for text in items or []:
            text = " ".join(str(text).split())[:120]
            text = text[:1].upper() + text[1:]
            if len(text) < 2 or any(i["text"].lower() == text.lower() and not i.get("done") for i in lst):
                continue
            it = {"id": uuid.uuid4().hex[:5], "text": text, "done": False}
            lst.append(it)
            added.append(it)
        _save(data)
    return key, added


def show(list_name: str = "") -> dict:
    """{name: [open items]} for one list or all lists."""
    data = _load()
    if list_name:
        key = _find(data, list_name)
        return {key: [i for i in data[key] if not i.get("done")]} if key else {}
    return {k: [i for i in v if not i.get("done")] for k, v in data.items() if any(not i.get("done") for i in v)}


def remove(list_name: str, item: str = "") -> int:
    """Removes an item (by id or words), or everything done / the whole list for item in ('', 'all'). Returns how many were removed."""
    with _lock:
        data = _load()
        key = _find(data, list_name)
        if not key:
            return 0
        before = len(data[key])
        q = " ".join(str(item or "").split()).lower()
        if q in ("", "all", "alles", "alle"):
            data[key] = []
        else:
            data[key] = [i for i in data[key] if i["id"] != q and q not in i["text"].lower()]
        removed = before - len(data[key])
        if not data[key]:
            del data[key]
        _save(data)
    return removed


def remove_items(list_name: str, item: str = "") -> list[dict]:
    """Like remove, but returns the removed entries (for undo)."""
    with _lock:
        data = _load()
        key = _find(data, list_name)
        if not key:
            return []
        q = " ".join(str(item or "").split()).lower()
        gone = [i for i in data[key] if q in ("", "all", "alles", "alle") or i["id"] == q or q in i["text"].lower()]
        data[key] = [i for i in data[key] if i not in gone]
        if not data[key]:
            del data[key]
        _save(data)
    return gone


def readd(list_name: str, items: list[dict]):
    with _lock:
        data = _load()
        lst = data.setdefault(_find(data, list_name) or canonical(list_name), [])
        ids = {i["id"] for i in lst}
        lst += [i for i in items if i["id"] not in ids]
        _save(data)


def format_text(lists: dict) -> str:
    if not lists:
        return "Keine offenen Einträge."
    return "\n".join(f"{name}:\n" + "\n".join(f"  - {i['text']} [id {i['id']}]" for i in items) for name, items in lists.items())
