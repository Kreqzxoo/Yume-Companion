"""Voice-built routines ("Abläufe"): a name and a list of steps in plain words. "Feierabend" -> "Licht aus", "Musik an", "Wecker prüfen" ...
Each step is carried out like a spoken command (quick commands first, otherwise the mini agent with tools). Stored in %LOCALAPPDATA%\\YumeCompanion\\macros.json."""
from __future__ import annotations

import json
import os
import re
import threading
from pathlib import Path

FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "macros.json"
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


def add(name: str, steps: list[str]) -> dict | None:
    steps = [" ".join(str(s).split())[:200] for s in (steps or []) if len(str(s).strip()) >= 3][:12]
    key = _key(name)
    if not key or not steps:
        return None
    with _lock:
        data = _load()
        data[key] = {"name": str(name).strip()[:40], "steps": steps}
        _save(data)
    return data[key]


def get(name: str) -> dict | None:
    return _load().get(_key(name))


def remove(name: str) -> dict | None:
    key = _key(name)
    with _lock:
        data = _load()
        gone = data.pop(key, None)
        if gone is not None:
            _save(data)
    return gone


def restore(macro: dict):
    with _lock:
        data = _load()
        data[_key(macro["name"])] = macro
        _save(data)


def names() -> list[str]:
    return [m["name"] for m in _load().values()]


def match(text: str) -> dict | None:
    """The macro meant by this sentence: its name alone, or 'starte / führe Ablauf X (aus)'."""
    data = _load()
    if not data:
        return None
    s = _key(text)
    s = re.sub(r"^bitte\s+", "", s)
    s = re.sub(r"^(?:bitte\s+)?(?:starte|start|führe|fuehre|mach|lass)\s+(?:den\s+|die\s+|das\s+)?(?:ablauf|routine|makro)?\s*", "", s)
    s = re.sub(r"^(?:ablauf|routine|makro)\s+", "", s)
    s = re.sub(r"\s+(?:aus|los|bitte)$", "", s).strip()
    return data.get(s)
