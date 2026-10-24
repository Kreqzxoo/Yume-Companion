"""Weekly report ("Wochenrückblick"): what Yume did for you, how you were doing, what is coming up. Built from the tool log, the jobs, the mood log, the journal
and the calendar - all local. The text is given to the character, who tells it in her own words."""
from __future__ import annotations

import time
from collections import Counter
from datetime import datetime, timedelta

NAMES = {"spotify": "Musik", "phone": "Handy-Aktionen", "calendar": "Kalender", "reminder": "Erinnerungen", "mail": "Mails", "weather": "Wetter", "lists": "Listen",
         "journal": "Tagebuch", "remember": "Merken", "files": "Dateien", "inbox": "Geteiltes", "knowledge": "Dokumenten-Suche", "jobs": "Aufträge", "macro": "Abläufe",
         "skill": "Fähigkeiten", "people": "Personen", "trip": "Reisen", "web_search": "Websuche", "media_control": "Medien am PC", "app_control": "Programme am PC",
         "document": "Dokumente", "nearby": "Umgebungssuche", "mood": "Stimmung"}


def build(days: int = 7, now: datetime | None = None) -> str:
    from app.utils import tool_log, jobs, mood, journal, organizer, people, alerts
    now = now or datetime.now()
    since = now - timedelta(days=days)
    parts: list[str] = [f"Zeitraum: {since.strftime('%d.%m.')} bis {now.strftime('%d.%m.%Y')}"]

    # what Yume did
    entries = [e for e in tool_log.read_with_undo(2000) if str(e.get("t", "")) >= since.strftime("%Y-%m-%dT00:00:00")]
    if entries:
        by = Counter(NAMES.get(e["tool"], e["tool"]) for e in entries)
        fails = sum(1 for e in entries if not e.get("success"))
        undone = sum(1 for e in entries if e.get("undone"))
        quick = sum(1 for e in entries if '"quick": true' in str(e.get("args", "")).lower() or "quick" in str(e.get("args", "")))
        top = ", ".join(f"{name} {n}×" for name, n in by.most_common(6))
        parts.append(f"AKTIONEN: {len(entries)} insgesamt ({top}); {fails} davon fehlgeschlagen, {undone} rückgängig gemacht, {quick} als Schnellbefehl ohne Warten.")
        failed_tools = Counter(NAMES.get(e["tool"], e["tool"]) for e in entries if not e.get("success"))
        if failed_tools:
            parts.append("FEHLGESCHLAGEN VOR ALLEM: " + ", ".join(f"{n} {c}×" for n, c in failed_tools.most_common(3)))
        slow = [e for e in entries if float(e.get("sec") or 0) > 8]
        if slow:
            parts.append(f"LANGSAM (über 8 s): {len(slow)} Aktionen")
    else:
        parts.append("AKTIONEN: In diesem Zeitraum hat Yume keine Werkzeuge benutzt.")

    # jobs
    try:
        done = [j for j in jobs.list_jobs(60) if j.get("status") in ("done", "failed") and str(j.get("created", "")) >= since.strftime("%Y-%m-%d")]
        if done:
            parts.append("AUFTRÄGE: " + "; ".join(f"{j['task'][:60]} ({'fertig' if j['status'] == 'done' else 'fehlgeschlagen'})" for j in done[:5]))
    except Exception:
        pass

    # mood
    try:
        m = mood.summary(days)
        if m:
            parts.append("STIMMUNG: " + m)
    except Exception:
        pass

    # journal
    try:
        je = journal.entries(days)
        if je:
            parts.append(f"TAGEBUCH: {len(je)} Einträge, zuletzt: " + " | ".join(f"{e['date'][5:]} {e['text'][:90]}" for e in je[-3:]))
    except Exception:
        pass

    # coming up
    try:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        ev, _ = organizer.events_between(start + timedelta(days=1), start + timedelta(days=8))
        if ev:
            parts.append("NÄCHSTE WOCHE:\n" + organizer.format_events(ev[:8]))
    except Exception:
        pass
    try:
        bd = people.upcoming_birthdays(14)
        if bd:
            parts.append("GEBURTSTAGE (14 Tage):\n" + people.birthday_text(bd))
    except Exception:
        pass
    try:
        age = alerts.latest_backup_age_days(__import__("pathlib").Path(__file__).resolve().parents[2])
        if age is None or age > 14:
            parts.append("HINWEIS: " + ("Es gibt noch kein Backup." if age is None else f"Das letzte Backup ist {age:.0f} Tage alt."))
    except Exception:
        pass
    return "\n\n".join(parts)


def note(days: int = 7) -> str:
    return ("[WEEKLY REPORT] Give the user a short, personal weekly review in your own style (at most 7 sentences, spoken language, no lists): what you did for them, "
            "how they seemed to be doing (be gentle with mood and never diagnose), what is coming up next week, and one useful hint if the data shows a problem (failures, backup). "
            "Use only the data below. Do NOT call any tool.\n\n" + build(days))
