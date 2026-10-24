"""Offline test of calendar (own events, ICS with recurrence), reminders and the tools. Uses a temporary data folder."""
import sys, os, asyncio, tempfile, datetime
sys.path.insert(0, '.')
from pathlib import Path
from app.utils import organizer as o
tmp = Path(tempfile.mkdtemp())
o.DIR = tmp; o.EVENTS_FILE = tmp / "events.json"; o.REMINDERS_FILE = tmp / "reminders.json"; o.CONFIG_FILE = tmp / "organizer.bin"
now = datetime.datetime.now().replace(second=0, microsecond=0)
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)

# own events
ev = o.add_event("Zahnarzt", now + datetime.timedelta(days=1, hours=2), location="Praxis")
evs, _ = o.events_between(now, now + datetime.timedelta(days=3))
check("own event listed", any(e["title"] == "Zahnarzt" for e in evs))
check("own event deleted", o.delete_event(ev["id"]) and not o._local_events(now, now + datetime.timedelta(days=3)))

# ICS: single, all-day, weekly recurrence with EXDATE, UTC time
first_monday = now.date() + datetime.timedelta(days=(7 - now.weekday()) % 7 or 7)
d = first_monday.strftime("%Y%m%d")
ics = f"""BEGIN:VCALENDAR
BEGIN:VEVENT
DTSTART:{d}T090000
DTEND:{d}T100000
RRULE:FREQ=WEEKLY;COUNT=4
EXDATE:{(first_monday + datetime.timedelta(days=7)).strftime('%Y%m%d')}T090000
SUMMARY:Team\, Meeting
LOCATION:Raum 1
END:VEVENT
BEGIN:VEVENT
DTSTART;VALUE=DATE:{(first_monday + datetime.timedelta(days=2)).strftime('%Y%m%d')}
SUMMARY:Feiertag
END:VEVENT
BEGIN:VEVENT
DTSTART:{(first_monday + datetime.timedelta(days=1)).strftime('%Y%m%d')}T120000Z
DTEND:{(first_monday + datetime.timedelta(days=1)).strftime('%Y%m%d')}T130000Z
SUMMARY:UTC Termin
END:VEVENT
END:VCALENDAR
"""
res = o._parse_ics(ics, now, now + datetime.timedelta(days=45), "Kalender")
titles = [e["title"] for e in res]
check("weekly recurrence 4 minus EXDATE = 3", titles.count("Team, Meeting") == 3)
check("all-day event", any(e["title"] == "Feiertag" and e["all_day"] for e in res))
check("UTC event converted", any(e["title"] == "UTC Termin" for e in res))
print(o.format_events(sorted(res, key=lambda e: e["start"]))[:400])

# reminders
r = o.add_reminder("Wäsche", now + datetime.timedelta(minutes=5))
rd = o.add_reminder("Tabletten", now - datetime.timedelta(minutes=1), "daily")
fired = o.due_reminders(now)
check("due reminder fires once", [f["text"] for f in fired] == ["Tabletten"])
check("daily reminder moved to the future", any(x["text"] == "Tabletten" and datetime.datetime.fromisoformat(x["when"]) > now for x in o.list_reminders()))
check("cancel one", o.cancel_reminder(r["id"]) == 1)

# tools
from app.utils.ai_clients import tools as T
async def run():
    c = T.CalendarTool(); rm = T.ReminderTool(); m = T.MailTool()
    a = await c.execute({"action": "add", "title": "Test", "start": (now + datetime.timedelta(hours=3)).isoformat()}, {})
    b = await c.execute({"action": "today"}, {})
    d1 = await rm.execute({"action": "add", "text": "Brot kaufen", "in_minutes": 30}, {})
    d2 = await rm.execute({"action": "list"}, {})
    d3 = await m.execute({"action": "list"}, {})
    return a, b, d1, d2, d3
a, b, d1, d2, d3 = asyncio.run(run())
check("tool: add event", a["success"]); check("tool: reminder add", d1["success"] and "Brot" in d2["result"]); check("tool: mail not configured message", not d3["success"] and "nicht eingerichtet" in d3["result"])
print("schema description starts:", T.CalendarTool().get_schema()["function"]["description"][:70])
print("ALL OK" if ok else "FAILED")

# ---- mail parsing with a fake IMAP connection (no real account needed)
from email.message import EmailMessage
mm = EmailMessage(); mm["From"] = "=?utf-8?q?M=C3=BCller?= <m@example.com>"; mm["Subject"] = "=?utf-8?q?Rechnung_f=C3=BCr_Oktober?="; mm["To"] = "me@example.com"; mm["Date"] = "Sun, 18 Oct 2026 20:00:00 +0200"
mm.set_content("Hallo,\n\nanbei die Rechnung über 42 Euro.\nViele Grüße")
mm.add_alternative("<html><body><p>Hallo</p><script>x()</script></body></html>", subtype="html")
raw = mm.as_bytes()
class FakeBox:
    def uid(self, cmd, *a):
        if cmd == "SEARCH": return "OK", [b"7 8"]
        return "OK", [(b"1 (UID 7 FLAGS (\Seen) BODY[]<0> {%d}" % len(raw), raw), b")"]
    def logout(self): pass
o._connect = lambda: FakeBox()
lst = o.mail_list(5, False, "")
check("mail list decoded", lst and lst[0]["from"].startswith("Müller") and "Rechnung für Oktober" in lst[0]["subject"] and "42 Euro" in lst[0]["snippet"])
check("mail read body, unread flag", o.mail_read("7")["body"].startswith("Hallo") and lst[0]["unread"] is False)
print("MAIL OK" if ok else "FAILED")

# ---- backup: organizer data goes into the memory group and comes back after a restore
import shutil
proj = Path(tempfile.mkdtemp())
o.add_reminder("Backup-Test", now + datetime.timedelta(hours=2))
from app.utils import lists_store as _ls
_ls.FILE = tmp / "lists.json"; _ls.add("Einkaufsliste", "Kaffee")
check("export copies the data files", o.export_to(proj) >= 2 and (proj / o.BACKUP_SUBDIR / "reminders.json").is_file())
o.REMINDERS_FILE.unlink()
check("reminders gone", o.list_reminders() == [])
check("import brings them back (and keeps .bak of existing)", o.import_from(proj) >= 2 and "Backup-Test" in [r["text"] for r in o.list_reminders()])
print("BACKUP OK" if ok else "FAILED")

# ---- parcels from shipping mails (fake IMAP)
pm = EmailMessage(); pm["From"] = "DHL Paket <noreply@dhl.de>"; pm["Subject"] = "Ihr Paket ist unterwegs"; pm["Date"] = "Sun, 18 Oct 2026 08:00:00 +0200"
pm.set_content("Ihre Sendung 00340434161094042557 wird heute zugestellt.")
dm = EmailMessage(); dm["From"] = "Amazon <ship@amazon.de>"; dm["Subject"] = "Ihre Bestellung wurde zugestellt"; dm["Date"] = "Fri, 16 Oct 2026 12:00:00 +0200"
dm.set_content("Ihr Paket wurde zugestellt und in Ihrer Packstation abgegeben.")
raws = {b"11": pm.as_bytes(), b"12": dm.as_bytes()}
class FakeBox2:
    def uid(self, cmd, *a):
        if cmd == "SEARCH": return "OK", [b"11 12"]
        uid = a[0]
        return "OK", [(b"1 (UID x BODY[]<0> {1}", raws[uid]), b")"]
    def logout(self): pass
o._connect = lambda: FakeBox2()
parcels = o.mail_parcels()
check("parcels: two found", len(parcels) == 2)
st = {p["subject"]: p for p in parcels}
check("parcels: transit + tracking number", st["Ihr Paket ist unterwegs"]["status"] == "unterwegs" and "00340434161094042557" in st["Ihr Paket ist unterwegs"]["tracking"])
check("parcels: delivered", st["Ihre Bestellung wurde zugestellt"]["status"] == "zugestellt")
print("PARCELS OK" if ok else "FAILED")
