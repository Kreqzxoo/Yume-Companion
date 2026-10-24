"""Organizer: calendar (own events + subscribed ICS calendars), reminders and mail (read-only, IMAP).

* Data lives in %LOCALAPPDATA%\\YumeCompanion (outside the project: not in backups, never in releases); secrets (ICS links, mail password) are
  protected with Windows data protection (same as the Spotify login).
* Calendar: own events + any number of ICS links (Google "secret address in iCal format", Outlook, Apple, Nextcloud ...). The phone's own
  calendar is read through the phone tool. ICS calendars are read-only.
* Mail: IMAP with an app password. Only READS (peek, nothing is marked as read, nothing is sent or deleted).
"""
from __future__ import annotations

import email
import html as html_lib
import imaplib
import json
import logging
import os
import re
import threading
import time
import urllib.request
import uuid
from datetime import date, datetime, timedelta
from email.header import decode_header, make_header
from pathlib import Path

logger = logging.getLogger("Organizer")

DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion"
EVENTS_FILE = DIR / "events.json"
REMINDERS_FILE = DIR / "reminders.json"
CONFIG_FILE = DIR / "organizer.bin"

_lock = threading.RLock()
_ics_cache: dict = {}            # url -> (time, text)


# ------------------------------------------------------------------ storage
def _read_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(path)


def config() -> dict:
    """{'ics': [urls], 'imap': {host, port, user, password, folder}} (encrypted file)."""
    try:
        from app.utils import spotify_pc
        raw = CONFIG_FILE.read_bytes()
        plain = spotify_pc._dpapi(raw, protect=False)
        return json.loads((plain if plain is not None else raw).decode("utf-8"))
    except (OSError, ValueError):
        return {"ics": [], "imap": {}}


def save_config(cfg: dict):
    from app.utils import spotify_pc
    payload = json.dumps(cfg, ensure_ascii=False).encode("utf-8")
    DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_bytes(spotify_pc._dpapi(payload, protect=True) or payload)
    _ics_cache.clear()


# ------------------------------------------------------------------ backup of the organizer data
SHARED_FILES = ["events.json", "reminders.json", "lists.json", "memory.json", "routines.json", "journal.json", "knowledge.json", "people.json", "trips.json", "macros.json", "drafts.json"]
BACKUP_SUBDIR = Path("app") / "data" / ".soul" / "organizer_export"      # inside the "memory" group of the profile backup


def export_to(root) -> int:
    """Copies the organizer data (appointments, reminders, lists, memory, routines, journal) next to the other user data so that the profile backup
    contains it. Secrets (calendar links, mail password, Spotify login) are NOT copied: they are bound to this Windows user anyway."""
    import shutil
    dest = Path(root) / BACKUP_SUBDIR
    n = 0
    try:
        for name in SHARED_FILES:
            src = DIR / name
            if src.is_file():
                dest.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest / name)
                n += 1
    except OSError:
        logger.debug("organizer export failed", exc_info=True)
    return n


def import_from(root) -> int:
    """After a restore: puts the organizer data of the backup back (the current files are kept as .bak)."""
    import shutil
    src = Path(root) / BACKUP_SUBDIR
    n = 0
    try:
        for name in SHARED_FILES:
            f = src / name
            if f.is_file():
                DIR.mkdir(parents=True, exist_ok=True)
                target = DIR / name
                if target.is_file():
                    shutil.copy2(target, target.with_suffix(target.suffix + ".bak"))
                shutil.copy2(f, target)
                n += 1
    except OSError:
        logger.debug("organizer import failed", exc_info=True)
    return n


# ------------------------------------------------------------------ time helpers
def parse_when(value, now: datetime | None = None) -> datetime | None:
    """ISO text ('2026-10-19T15:00', '19.10.2026 15:00', 'morgen 15:00' is NOT understood: the model passes ISO) or minutes from now (int)."""
    now = now or datetime.now()
    if value in (None, ""):
        return None
    if isinstance(value, (int, float)):
        return now + timedelta(minutes=float(value))
    text = str(value).strip()
    try:
        dt = datetime.fromisoformat(text.replace("Z", ""))
    except ValueError:
        try:
            from dateutil import parser as dparser
            dt = dparser.parse(text, dayfirst=True, default=now.replace(hour=9, minute=0, second=0, microsecond=0))
        except Exception:
            return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def fmt(dt: datetime, all_day: bool = False) -> str:
    days = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"]
    base = f"{days[dt.weekday()]} {dt.strftime('%d.%m.')}"
    return base if all_day else f"{base} {dt.strftime('%H:%M')}"


# ------------------------------------------------------------------ own events
def add_event(title: str, start: datetime, end: datetime | None = None, location: str = "", notes: str = "", all_day: bool = False) -> dict:
    ev = {"id": uuid.uuid4().hex[:8], "title": title.strip(), "start": start.isoformat(timespec="minutes"),
          "end": (end or start + timedelta(hours=1)).isoformat(timespec="minutes"), "location": location.strip(), "notes": notes.strip(), "all_day": bool(all_day)}
    with _lock:
        data = _read_json(EVENTS_FILE, [])
        data.append(ev)
        _write_json(EVENTS_FILE, data)
    return ev


def delete_event(event_id: str) -> bool:
    with _lock:
        data = _read_json(EVENTS_FILE, [])
        keep = [e for e in data if e.get("id") != event_id]
        if len(keep) == len(data):
            return False
        _write_json(EVENTS_FILE, keep)
    return True


def _local_events(start: datetime, end: datetime) -> list[dict]:
    out = []
    for e in _read_json(EVENTS_FILE, []):
        try:
            s = datetime.fromisoformat(e["start"]); en = datetime.fromisoformat(e.get("end") or e["start"])
        except (KeyError, ValueError):
            continue
        if en >= start and s <= end:
            out.append({"id": e.get("id", ""), "title": e.get("title", ""), "start": s, "end": en, "location": e.get("location", ""),
                        "all_day": bool(e.get("all_day")), "source": "eigener Termin"})
    return out


# ------------------------------------------------------------------ ICS calendars (read-only)
def _fetch_ics(url: str) -> str:
    cached = _ics_cache.get(url)
    if cached and time.time() - cached[0] < 600:
        return cached[1]
    req = urllib.request.Request(url.replace("webcal://", "https://"), headers={"User-Agent": "YumeCompanion"})
    with urllib.request.urlopen(req, timeout=12) as r:
        text = r.read(8_000_000).decode("utf-8", "replace")
    _ics_cache[url] = (time.time(), text)
    return text


def _ics_dt(value: str, params: str):
    """-> (naive local datetime, all_day)"""
    value = value.strip()
    if "VALUE=DATE" in params or (len(value) == 8 and value.isdigit()):
        d = datetime.strptime(value[:8], "%Y%m%d")
        return d, True
    base = datetime.strptime(value.rstrip("Z")[:15], "%Y%m%dT%H%M%S")
    if value.endswith("Z"):
        from datetime import timezone
        return base.replace(tzinfo=timezone.utc).astimezone().replace(tzinfo=None), False
    m = re.search(r"TZID=([^;:]+)", params)
    if m:
        try:
            from zoneinfo import ZoneInfo
            return base.replace(tzinfo=ZoneInfo(m.group(1))).astimezone().replace(tzinfo=None), False
        except Exception:
            pass
    return base, False


def _parse_ics(text: str, start: datetime, end: datetime, label: str) -> list[dict]:
    lines: list[str] = []
    for raw in text.replace("\r\n", "\n").split("\n"):
        if raw[:1] in (" ", "\t") and lines:
            lines[-1] += raw[1:]
        else:
            lines.append(raw)
    out: list[dict] = []
    ev: dict | None = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            ev = {"EXDATE": []}
        elif line == "END:VEVENT" and ev is not None:
            try:
                out += _expand_ics_event(ev, start, end, label)
            except Exception:
                logger.debug("ICS event skipped", exc_info=True)
            ev = None
        elif ev is not None and ":" in line:
            head, _, val = line.partition(":")
            name, _, params = head.partition(";")
            name = name.upper()
            if name == "EXDATE":
                ev["EXDATE"].append((val, params))
            else:
                ev[name] = (val, params)
    return out


def _unescape(s: str) -> str:
    return s.replace("\\n", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _expand_ics_event(ev: dict, start: datetime, end: datetime, label: str) -> list[dict]:
    if "DTSTART" not in ev:
        return []
    s, all_day = _ics_dt(*ev["DTSTART"])
    if "DTEND" in ev:
        e, _ = _ics_dt(*ev["DTEND"])
    else:
        e = s + (timedelta(days=1) if all_day else timedelta(hours=1))
    dur = max(e - s, timedelta(0))
    title = _unescape(ev.get("SUMMARY", ("(ohne Titel)", ""))[0])
    loc = _unescape(ev.get("LOCATION", ("", ""))[0])
    base = {"id": "", "title": title, "location": loc, "all_day": all_day, "source": label}
    if "RRULE" not in ev:
        return [dict(base, start=s, end=e)] if e >= start and s <= end else []
    from dateutil.rrule import rrulestr
    rule_text = re.sub(r"UNTIL=(\d{8}(?:T\d{6})?)Z?", lambda m: "UNTIL=" + (m.group(1) if "T" in m.group(1) else m.group(1) + "T235959"), ev["RRULE"][0])
    rule = rrulestr("RRULE:" + rule_text, dtstart=s)
    skip = set()
    for val, params in ev["EXDATE"]:
        for part in val.split(","):
            try:
                skip.add(_ics_dt(part, params)[0])
            except Exception:
                pass
    out = []
    for occ in rule.between(start - dur, end, inc=True):
        if occ in skip:
            continue
        out.append(dict(base, start=occ, end=occ + dur))
        if len(out) >= 200:
            break
    return out


def events_between(start: datetime, end: datetime, include_ics: bool = True) -> tuple[list[dict], list[str]]:
    """(events sorted by start, problems)"""
    events = _local_events(start, end)
    problems: list[str] = []
    if include_ics:
        for url in config().get("ics", []):
            url = url.strip()
            if not url:
                continue
            try:
                events += _parse_ics(_fetch_ics(url), start, end, "Kalender")
            except Exception as exc:
                problems.append(f"Kalender-Link nicht lesbar ({str(exc)[:60]})")
    events.sort(key=lambda x: x["start"])
    return events, problems


def format_events(events: list[dict]) -> str:
    lines = []
    for e in events:
        when = fmt(e["start"], e["all_day"]) + ("" if e["all_day"] else f"–{e['end'].strftime('%H:%M')}" if e["end"].date() == e["start"].date() else "")
        loc = f" @ {e['location']}" if e.get("location") else ""
        ident = f" [id {e['id']}]" if e.get("id") else ""
        lines.append(f"{when}  {e['title']}{loc}{ident}")
    return "\n".join(lines)


# ------------------------------------------------------------------ reminders
def add_reminder(text: str, when: datetime, repeat: str = "") -> dict:
    repeat = repeat if repeat in ("daily", "weekly", "monthly") else ""
    r = {"id": uuid.uuid4().hex[:8], "text": text.strip(), "when": when.isoformat(timespec="seconds"), "repeat": repeat, "done": False}
    with _lock:
        data = _read_json(REMINDERS_FILE, [])
        data.append(r)
        _write_json(REMINDERS_FILE, data)
    return r


def list_reminders(include_done: bool = False) -> list[dict]:
    data = _read_json(REMINDERS_FILE, [])
    data = [r for r in data if include_done or not r.get("done")]
    return sorted(data, key=lambda r: r.get("when", ""))


def cancel_reminder(rid: str) -> int:
    """Deletes one reminder (id) or all open ones (id empty / 'all'). Returns how many were removed."""
    with _lock:
        data = _read_json(REMINDERS_FILE, [])
        keep = [r for r in data if r.get("done") or (rid not in ("", "all") and r.get("id") != rid)]
        removed = len(data) - len(keep)
        if removed:
            _write_json(REMINDERS_FILE, keep)
    return removed


def cancel_reminder_items(rid: str) -> list[dict]:
    """Like cancel_reminder, but returns the removed reminders (for undo)."""
    with _lock:
        data = _read_json(REMINDERS_FILE, [])
        gone = [r for r in data if not r.get("done") and (rid in ("", "all") or r.get("id") == rid)]
        if gone:
            _write_json(REMINDERS_FILE, [r for r in data if r not in gone])
    return gone


def restore_reminders(items: list[dict]):
    with _lock:
        data = _read_json(REMINDERS_FILE, [])
        ids = {r.get("id") for r in data}
        data += [r for r in items if r.get("id") not in ids]
        _write_json(REMINDERS_FILE, data)


def get_event(event_id: str) -> dict | None:
    return next((e for e in _read_json(EVENTS_FILE, []) if e.get("id") == event_id), None)


def restore_event(ev: dict):
    with _lock:
        data = _read_json(EVENTS_FILE, [])
        if not any(e.get("id") == ev.get("id") for e in data):
            data.append(ev)
            _write_json(EVENTS_FILE, data)


def due_reminders(now: datetime | None = None) -> list[dict]:
    """Reminders whose time has come; one-time ones are marked done, repeating ones move on."""
    now = now or datetime.now()
    fired = []
    with _lock:
        data = _read_json(REMINDERS_FILE, [])
        changed = False
        for r in data:
            if r.get("done"):
                continue
            try:
                when = datetime.fromisoformat(r["when"])
            except (KeyError, ValueError):
                r["done"] = True; changed = True
                continue
            if when <= now:
                fired.append(dict(r))
                changed = True
                step = {"daily": timedelta(days=1), "weekly": timedelta(days=7)}.get(r.get("repeat", ""))
                if r.get("repeat") == "monthly":
                    month = when.month % 12 + 1
                    year = when.year + (1 if when.month == 12 else 0)
                    try:
                        nxt = when.replace(year=year, month=month)
                    except ValueError:
                        nxt = when + timedelta(days=30)
                elif step:
                    nxt = when
                    while nxt <= now:
                        nxt += step
                else:
                    nxt = None
                if nxt:
                    r["when"] = nxt.isoformat(timespec="seconds")
                else:
                    r["done"] = True
        if changed:
            _write_json(REMINDERS_FILE, data)
    return fired


# ------------------------------------------------------------------ mail (IMAP, read-only)
def mail_configured() -> bool:
    c = config().get("imap", {})
    return bool(c.get("host") and c.get("user") and c.get("password"))


def _dec(value) -> str:
    try:
        return str(make_header(decode_header(value or ""))).strip()
    except Exception:
        return str(value or "")


def _body_text(msg) -> str:
    plain, htmls = [], []
    parts = msg.walk() if msg.is_multipart() else [msg]
    for part in parts:
        if part.get_content_maintype() != "text" or part.get_filename():
            continue
        try:
            payload = part.get_payload(decode=True) or b""
            text = payload.decode(part.get_content_charset() or "utf-8", "replace")
        except Exception:
            continue
        (plain if part.get_content_subtype() == "plain" else htmls).append(text)
    if plain:
        text = "\n".join(plain)
    else:
        text = re.sub(r"(?is)<(script|style).*?</\1>", " ", "\n".join(htmls))
        text = html_lib.unescape(re.sub(r"(?s)<[^>]+>", " ", text))
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n\n", text).strip()


def _connect():
    c = config().get("imap", {})
    box = imaplib.IMAP4_SSL(c["host"], int(c.get("port") or 993), timeout=20)
    box.login(c["user"], c["password"])
    box.select(c.get("folder") or "INBOX", readonly=True)
    return box


def mail_test() -> tuple[bool, str]:
    if not mail_configured():
        return False, "Mail ist nicht eingerichtet."
    try:
        box = _connect()
        status, data = box.search(None, "UNSEEN")
        n = len(data[0].split()) if status == "OK" and data and data[0] else 0
        box.logout()
        return True, f"Verbunden. {n} ungelesene Mail(s)."
    except imaplib.IMAP4.error as exc:
        return False, f"Anmeldung abgelehnt: {str(exc)[:80]}. Bei Gmail braucht man ein App-Passwort, nicht das normale Passwort."
    except Exception as exc:
        return False, f"Keine Verbindung: {str(exc)[:80]}"


def mail_list(limit: int = 10, unread_only: bool = False, query: str = "") -> list[dict]:
    box = _connect()
    try:
        criteria = []
        if unread_only:
            criteria.append("UNSEEN")
        if query:
            criteria += ["TEXT", '"' + query.replace('"', "") + '"']
        status, data = box.uid("SEARCH", None, *(criteria or ["ALL"]))
        uids = data[0].split() if status == "OK" and data and data[0] else []
        out = []
        for uid in reversed(uids[-max(1, min(limit, 30)):]):
            st, parts = box.uid("FETCH", uid, "(FLAGS BODY.PEEK[]<0.6000>)")
            if st != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            flags = parts[0][0].decode("utf-8", "replace")
            msg = email.message_from_bytes(parts[0][1])
            body = _body_text(msg)
            out.append({"uid": uid.decode(), "from": _dec(msg.get("From")), "subject": _dec(msg.get("Subject")) or "(ohne Betreff)",
                        "date": _dec(msg.get("Date"))[:25], "unread": "\\Seen" not in flags, "snippet": re.sub(r"\s+", " ", body)[:240]})
        return out
    finally:
        try:
            box.logout()
        except Exception:
            pass


PARCEL_WORDS = ["Sendung", "Paket", "Versand", "versandt", "Lieferung", "geliefert", "zugestellt", "Zustellung", "Tracking", "DHL", "DPD", "Hermes", "UPS", "GLS", "FedEx",
                "Amazon", "Bestellung", "Packstation", "Paketshop"]
_DELIVERED = ("zugestellt", "geliefert", "abgeholt", "delivered", "übergeben", "in ihrer packstation", "abgegeben")
_TRANSIT = ("unterwegs", "wird heute", "heute zugestellt", "zustellung heute", "auf dem weg", "in zustellung", "out for delivery", "versandt", "versendet", "hat ihr haus verlassen",
            "wurde versandt", "paket ist", "sendung ist")


def _parcel_status(text: str) -> str:
    low = text.lower()
    if re.search(r"wird\s+(?:heute\s+|morgen\s+)?zugestellt|zustellung\s+heute|out for delivery|in zustellung|auf dem weg|unterwegs", low):
        return "unterwegs"                       # "wird heute zugestellt" must not count as delivered
    if any(w in low for w in _DELIVERED):
        return "zugestellt"
    if any(w in low for w in _TRANSIT):
        return "unterwegs"
    return "Bestellung / Info"


def _tracking_numbers(text: str) -> list[str]:
    found = re.findall(r"\b(1Z[0-9A-Z]{16})\b|\b(\d{12,20})\b|\b(JJD\d{15,20})\b|\b(H\d{16,20})\b", text)
    return list(dict.fromkeys(x for tup in found for x in tup if x))[:2]


def mail_parcels(days: int = 21, limit: int = 12) -> list[dict]:
    """Shipping / order mails of the last days with a guessed status and tracking number (newest first). Read-only like everything in mail."""
    since = (datetime.now() - timedelta(days=max(1, min(days, 90)))).strftime("%d-%b-%Y")
    box = _connect()
    try:
        uids: set = set()
        for word in PARCEL_WORDS:
            st, data = box.uid("SEARCH", None, "SINCE", since, "SUBJECT", '"' + word + '"')
            if st == "OK" and data and data[0]:
                uids.update(data[0].split())
        out = []
        for uid in sorted(uids, key=lambda u: int(u), reverse=True)[:limit * 2]:
            st, parts = box.uid("FETCH", uid, "(BODY.PEEK[]<0.8000>)")
            if st != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            msg = email.message_from_bytes(parts[0][1])
            body = _body_text(msg)
            subject = _dec(msg.get("Subject")) or "(ohne Betreff)"
            blob = subject + " " + body
            out.append({"uid": uid.decode(), "from": _dec(msg.get("From")), "subject": subject, "date": _dec(msg.get("Date"))[:25],
                        "status": _parcel_status(blob), "tracking": _tracking_numbers(blob), "snippet": re.sub(r"\s+", " ", body)[:160]})
            if len(out) >= limit:
                break
        return out
    finally:
        try:
            box.logout()
        except Exception:
            pass


def mail_bookings(days: int = 120, limit: int = 12) -> list[dict]:
    """Booking / reservation / ticket mails of the last days (flights, hotels, trains ...), newest first - the model reads the details from the snippets."""
    since = (datetime.now() - timedelta(days=max(1, min(days, 365)))).strftime("%d-%b-%Y")
    words = ["Buchung", "Buchungsbestätigung", "Reservierung", "Flug", "Boarding", "Hotel", "Check-in", "Ticket", "Bahn", "Reise", "booking", "reservation", "itinerary"]
    box = _connect()
    try:
        uids: set = set()
        for word in words:
            try:
                st, data = box.uid("SEARCH", None, "SINCE", since, "SUBJECT", '"' + word + '"')
            except Exception:
                continue
            if st == "OK" and data and data[0]:
                uids.update(data[0].split())
        out = []
        for uid in sorted(uids, key=lambda u: int(u), reverse=True)[:limit]:
            st, parts = box.uid("FETCH", uid, "(BODY.PEEK[]<0.9000>)")
            if st != "OK" or not parts or not isinstance(parts[0], tuple):
                continue
            msg = email.message_from_bytes(parts[0][1])
            body = _body_text(msg)
            out.append({"uid": uid.decode(), "from": _dec(msg.get("From")), "subject": _dec(msg.get("Subject")) or "(ohne Betreff)", "date": _dec(msg.get("Date"))[:25],
                        "snippet": re.sub(r"\s+", " ", body)[:420]})
        return out
    finally:
        try:
            box.logout()
        except Exception:
            pass


# ------------------------------------------------------------------ mail drafts (Yume NEVER sends: she writes the draft, you send it)
DRAFTS_FILE = DIR / "drafts.json"
DRAFT_FOLDERS = ["Drafts", "[Gmail]/Drafts", "[Google Mail]/Drafts", "INBOX.Drafts", "Entwürfe", "[Gmail]/Entwürfe", "[Google Mail]/Entwürfe", "Draft"]


def _connect_rw():
    c = config().get("imap", {})
    box = imaplib.IMAP4_SSL(c["host"], int(c.get("port") or 993), timeout=20)
    box.login(c["user"], c["password"])
    return box


def _find_drafts_folder(box) -> str | None:
    try:
        st, data = box.list()
        names = []
        if st == "OK":
            for line in data or []:
                s = line.decode("utf-8", "replace") if isinstance(line, bytes) else str(line)
                m = re.search(r'\((.*?)\)\s+"(.*?)"\s+"?(.*?)"?$', s)
                if m:
                    names.append((m.group(1), m.group(3).strip('"')))
        for flags, name in names:
            if "\\Drafts" in flags:
                return name
        have = {n for _, n in names}
        for cand in DRAFT_FOLDERS:
            if cand in have:
                return cand
    except Exception:
        pass
    return None


def save_draft(to: str, subject: str, body: str, reply_to_uid: str = "") -> dict:
    """Saves a draft: in the 'Drafts' folder of the mail account (when possible) and always in the local list. Returns {'id', 'where', 'to', 'subject'}."""
    from email.message import EmailMessage
    from email.utils import formatdate, make_msgid
    me = config().get("imap", {})
    msg = EmailMessage()
    msg["From"] = me.get("user", "")
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = make_msgid()
    in_reply = ""
    if reply_to_uid and mail_configured():
        try:
            box = _connect()
            try:
                st, parts = box.uid("FETCH", str(reply_to_uid), "(BODY.PEEK[HEADER])")
                if st == "OK" and parts and isinstance(parts[0], tuple):
                    orig = email.message_from_bytes(parts[0][1])
                    to = to or _dec(orig.get("Reply-To") or orig.get("From"))
                    subj = _dec(orig.get("Subject"))
                    subject = subject or (subj if subj.lower().startswith(("re:", "aw:")) else "Re: " + subj)
                    in_reply = orig.get("Message-ID", "")
            finally:
                try:
                    box.logout()
                except Exception:
                    pass
        except Exception:
            logger.debug("reply headers could not be read", exc_info=True)
    msg["To"] = to
    msg["Subject"] = subject or "(ohne Betreff)"
    if in_reply:
        msg["In-Reply-To"] = in_reply
        msg["References"] = in_reply
    msg.set_content(body)
    where = "nur in Yume (Entwurfsliste)"
    if mail_configured():
        try:
            box = _connect_rw()
            try:
                folder = _find_drafts_folder(box)
                if folder:
                    box.append('"' + folder + '"', "\\Draft", imaplib.Time2Internaldate(time.time()), msg.as_bytes())
                    where = f"im Ordner „{folder}“ deines Mail-Kontos"
            finally:
                try:
                    box.logout()
                except Exception:
                    pass
        except Exception as exc:
            logger.debug("draft could not be saved on the server: %s", exc)
    item = {"id": uuid.uuid4().hex[:6], "to": to, "subject": msg["Subject"], "body": body, "created": datetime.now().isoformat(timespec="minutes"), "where": where}
    with _lock:
        items = _read_json(DRAFTS_FILE, [])
        items.append(item)
        _write_json(DRAFTS_FILE, items[-60:])
    return item


def list_drafts() -> list[dict]:
    return list(reversed(_read_json(DRAFTS_FILE, [])))


def get_draft(key: str) -> dict | None:
    key = str(key or "").strip().lower()
    items = list_drafts()
    if not key or key == "latest":
        return items[0] if items else None
    return next((d for d in items if d["id"] == key or key in d["subject"].lower()), None)


def delete_draft(key: str) -> dict | None:
    d = get_draft(key)
    if not d:
        return None
    with _lock:
        _write_json(DRAFTS_FILE, [x for x in _read_json(DRAFTS_FILE, []) if x["id"] != d["id"]])
    return d


def mailto_url(d: dict) -> str:
    from urllib.parse import quote
    return f"mailto:{quote(d['to'], safe='@,;')}?subject={quote(d['subject'])}&body={quote(d['body'])}"


def mail_read(uid: str, limit: int = 5000) -> dict | None:
    box = _connect()
    try:
        st, parts = box.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if st != "OK" or not parts or not isinstance(parts[0], tuple):
            return None
        msg = email.message_from_bytes(parts[0][1])
        return {"uid": str(uid), "from": _dec(msg.get("From")), "to": _dec(msg.get("To")), "subject": _dec(msg.get("Subject")),
                "date": _dec(msg.get("Date")), "body": _body_text(msg)[:limit]}
    finally:
        try:
            box.logout()
        except Exception:
            pass
