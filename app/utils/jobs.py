"""Background jobs: tasks Yume works on by herself ("research ... and tell me tomorrow morning"). Stored in %LOCALAPPDATA%\\YumeCompanion\\jobs.json."""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path

FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "jobs.json"
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
    tmp.write_text(json.dumps(items[-80:], ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def add(task: str, run_at: datetime | None = None, deliver_at: datetime | None = None) -> dict | None:
    task = " ".join(str(task or "").split())[:800]
    if len(task) < 8:
        return None
    job = {"id": uuid.uuid4().hex[:6], "task": task, "created": datetime.now().isoformat(timespec="seconds"),
           "run_at": (run_at or datetime.now()).isoformat(timespec="seconds"), "deliver_at": deliver_at.isoformat(timespec="seconds") if deliver_at else "",
           "status": "queued", "result": "", "delivered": False}
    with _lock:
        items = _load()
        items.append(job)
        _save(items)
    return job


def list_jobs(limit: int = 20) -> list[dict]:
    return list(reversed(_load()))[:limit]


def get(job_id: str) -> dict | None:
    key = str(job_id or "").strip().lower()
    items = list(reversed(_load()))
    if not key or key == "latest":
        return items[0] if items else None
    return next((j for j in items if j["id"] == key or key in j["task"].lower()), None)


def update(job_id: str, **fields):
    with _lock:
        items = _load()
        for j in items:
            if j["id"] == job_id:
                j.update(fields)
        _save(items)


def cancel(job_id: str) -> int:
    key = str(job_id or "").strip().lower()
    with _lock:
        items = _load()
        keep = [j for j in items if not (j["status"] in ("queued", "running") and (key in ("", "all") or j["id"] == key))]
        n = len(items) - len(keep)
        if n:
            _save(keep)
    return n


def next_to_run(now: datetime | None = None) -> dict | None:
    now = now or datetime.now()
    for j in _load():
        if j["status"] == "queued" and datetime.fromisoformat(j["run_at"]) <= now:
            return j
    return None


def next_to_deliver(now: datetime | None = None) -> dict | None:
    now = now or datetime.now()
    for j in _load():
        if j["status"] in ("done", "failed") and not j["delivered"] and (not j["deliver_at"] or datetime.fromisoformat(j["deliver_at"]) <= now):
            return j
    return None


def reset_stuck():
    """A job that was 'running' when the program was closed starts again."""
    with _lock:
        items = _load()
        for j in items:
            if j["status"] == "running":
                j["status"] = "queued"
        _save(items)
