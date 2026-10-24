"""Tool-call log: what the AI executed, whether you approved it, and how it went (logs/tool_log.jsonl).

Arguments and results are shortened and secrets are masked. Switch off with the setting ``tool_log_enabled``.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
import uuid
from pathlib import Path

logger = logging.getLogger("ToolLog")

LOG_FILE = Path(__file__).resolve().parents[2] / "logs" / "tool_log.jsonl"
MAX_LINES = 1500
_lock = threading.Lock()
_SECRET = re.compile(r"(?i)((?:token|api[_-]?key|secret|password|authorization)\W{0,4})([A-Za-z0-9_\-\.=:/+]{8,})")


def _clip(value, limit=300) -> str:
    try:
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    except Exception:
        text = str(value)
    text = _SECRET.sub(lambda m: m.group(1) + "********", text)
    return text if len(text) <= limit else text[:limit] + "…"


def enabled() -> bool:
    try:
        from app.configuration.configuration import ConfigurationSettings
        value = ConfigurationSettings().get_main_setting("tool_log_enabled")
        return True if value is None else bool(value)
    except Exception:
        return True


def record(tool: str, args, approval: str, success: bool, result, seconds: float, undo: dict | None = None):
    """approval: 'not_needed' | 'approved' | 'declined'. undo: how to take the action back (see undo())."""
    if not enabled():
        return
    entry = {
        "id": uuid.uuid4().hex[:8],
        "t": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": tool, "args": _clip(args), "approval": approval,
        "success": bool(success), "result": _clip(result, 240), "sec": round(seconds, 2),
    }
    if undo and success:
        entry["undo"] = undo
    try:
        with _lock:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(LOG_FILE, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
            _trim()
    except OSError as exc:
        logger.debug("tool log write failed: %s", exc)


def _mark_undone(entries: list[dict]) -> list[dict]:
    done = {e.get("target") for e in entries if e.get("tool") == "undo"}
    for e in entries:
        e["undone"] = e.get("id") in done
    return [e for e in entries if e.get("tool") != "undo"]


def read_with_undo(limit: int = 300) -> list[dict]:
    """Like read(), with an 'undone' flag per entry and without the undo markers (newest first)."""
    return _mark_undone(read(limit))


def undoable(limit: int = 30) -> list[dict]:
    return [e for e in read_with_undo(400) if e.get("undo") and not e.get("undone")][:limit]


def undo(entry_id: str = "") -> tuple[bool, str]:
    """Takes back one action (the newest undoable one when no id is given). Returns (success, text)."""
    items = undoable(60)
    entry = next((e for e in items if not entry_id or e.get("id") == entry_id), None)
    if entry is None:
        return False, "Es gibt nichts, was ich rückgängig machen könnte."
    spec = entry["undo"]
    kind = spec.get("kind")
    try:
        if kind == "reminder_add":
            from app.utils import organizer
            text = f"Erinnerung gelöscht." if organizer.cancel_reminder(spec["id"]) else "Die Erinnerung war schon weg."
        elif kind == "reminder_cancel":
            from app.utils import organizer
            organizer.restore_reminders(spec["items"])
            text = f"{len(spec['items'])} Erinnerung(en) wiederhergestellt."
        elif kind == "event_add":
            from app.utils import organizer
            text = "Termin gelöscht." if organizer.delete_event(spec["id"]) else "Der Termin war schon weg."
        elif kind == "event_delete":
            from app.utils import organizer
            organizer.restore_event(spec["event"])
            text = "Termin wiederhergestellt."
        elif kind == "list_add":
            from app.utils import lists_store
            for i in spec["ids"]:
                lists_store.remove(spec["list"], i)
            text = f"Von der {spec['list']} wieder entfernt."
        elif kind == "list_remove":
            from app.utils import lists_store
            lists_store.readd(spec["list"], spec["items"])
            text = f"Wieder auf die {spec['list']} gesetzt."
        elif kind == "memory_add":
            from app.utils import user_memory
            user_memory.forget(spec["id"])
            text = "Wieder vergessen."
        elif kind == "memory_forget":
            from app.utils import user_memory
            user_memory.restore(spec["items"])
            text = "Wieder gemerkt."
        elif kind == "journal_add":
            from app.utils import journal
            journal.remove(spec["id"])
            text = "Tagebucheintrag gelöscht."
        elif kind == "journal_remove":
            from app.utils import journal
            journal.restore(spec["items"])
            text = "Tagebucheintrag wiederhergestellt."
        elif kind == "knowledge_add":
            from app.utils import knowledge
            import os as _o
            try:
                _o.remove(spec["path"])
            except OSError:
                pass
            knowledge.reindex(60)
            text = "Aus der Wissensdatenbank entfernt."
        elif kind == "draft_add":
            from app.utils import organizer
            organizer.delete_draft(spec["id"])
            text = "Entwurf aus der Liste gelöscht (eine Kopie im Entwürfe-Ordner deines Mail-Kontos bitte dort löschen)."
        elif kind == "document_create":
            import os as _os
            for pth in spec["paths"]:
                try:
                    _os.remove(pth)
                except OSError:
                    pass
            text = "Dokument gelöscht."
        elif kind == "people_restore":
            from app.utils import people
            people.restore(spec["name"], spec.get("old"))
            text = "Rückgängig gemacht."
        elif kind == "trip_add":
            from app.utils import trips, organizer
            trips.remove(spec["id"])
            organizer.delete_event(spec.get("event", ""))
            if spec.get("reminder"):
                organizer.cancel_reminder(spec["reminder"])
            text = "Reise, Kalendereintrag und Erinnerung gelöscht."
        elif kind == "trip_delete":
            from app.utils import trips
            trips.restore(spec["trip"])
            text = "Reise wiederhergestellt."
        elif kind == "skill_add":
            from app.utils import skills
            skills.delete(spec["name"])
            text = "Fähigkeit gelöscht."
        elif kind == "job_add":
            from app.utils import jobs
            jobs.cancel(spec["id"])
            text = "Auftrag abgebrochen."
        elif kind == "macro_add":
            from app.utils import macros
            macros.remove(spec["name"])
            text = "Ablauf gelöscht."
        elif kind == "macro_delete":
            from app.utils import macros
            macros.restore(spec["macro"])
            text = "Ablauf wiederhergestellt."
        elif kind == "spotify":
            from app.utils import spotify_pc
            ok, msg = spotify_pc.control(spec["action"])
            if not ok:
                return False, msg
            text = "Musik läuft wieder." if spec["action"] == "resume" else "Musik pausiert."
        else:
            return False, "Das lässt sich nicht rückgängig machen."
    except Exception as exc:
        return False, f"Rückgängig machen fehlgeschlagen: {str(exc)[:100]}"
    try:
        with _lock:
            with open(LOG_FILE, "a", encoding="utf-8") as fh:
                fh.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "tool": "undo", "target": entry["id"]}) + "\n")
    except OSError:
        pass
    return True, text


def _trim():
    try:
        if LOG_FILE.stat().st_size < 400_000:
            return
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()
        if len(lines) > MAX_LINES:
            LOG_FILE.write_text("\n".join(lines[-MAX_LINES:]) + "\n", encoding="utf-8")
    except OSError:
        pass


def read(limit: int = 200) -> list[dict]:
    try:
        lines = LOG_FILE.read_text(encoding="utf-8", errors="replace").splitlines()[-limit:]
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    out.reverse()
    return out


def clear():
    try:
        LOG_FILE.unlink()
    except OSError:
        pass
