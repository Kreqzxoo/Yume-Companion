"""Things the user told Yume to remember (preferences, facts, habits). They are added to the character's prompt, so they are used in every
chat, in the briefing and in the routines. Stored in %LOCALAPPDATA%\\YumeCompanion\\memory.json (shared by all Yume folders of this Windows user)."""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "memory.json"
_lock = threading.RLock()
MAX_ITEMS = 60


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


def add(text: str) -> dict | None:
    text = " ".join(str(text or "").split())[:300]
    if len(text) < 3:
        return None
    with _lock:
        items = _load()
        for it in items:
            if it.get("text", "").lower() == text.lower():
                return it
        item = {"id": uuid.uuid4().hex[:6], "text": text, "created": time.strftime("%Y-%m-%d")}
        items.append(item)
        _save(items[-MAX_ITEMS:])
    return item


def list_items() -> list[dict]:
    return _load()


def forget(key: str) -> int:
    """Removes the item with this id, items containing this text, or everything for 'all'. Returns how many were removed."""
    key = str(key or "").strip().lower()
    with _lock:
        items = _load()
        if key in ("all", "alles"):
            keep = []
        else:
            keep = [i for i in items if i.get("id") != key and key not in i.get("text", "").lower()]
        if len(keep) != len(items):
            _save(keep)
        return len(items) - len(keep)


def forget_items(key: str) -> list[dict]:
    """Like forget, but returns the removed notes (for undo)."""
    key = str(key or "").strip().lower()
    with _lock:
        items = _load()
        gone = [i for i in items if key in ("all", "alles") or i.get("id") == key or key in i.get("text", "").lower()]
        if gone:
            _save([i for i in items if i not in gone])
        return gone


def restore(items: list[dict]):
    with _lock:
        cur = _load()
        ids = {i.get("id") for i in cur}
        _save((cur + [i for i in items if i.get("id") not in ids])[-MAX_ITEMS:])


def prompt_block() -> str:
    items = _load()[-25:]
    if not items:
        return ""
    return ("[THINGS {{user}} TOLD YOU TO REMEMBER - use them naturally, never recite the list]\n" + "\n".join("- " + i["text"] for i in items))
