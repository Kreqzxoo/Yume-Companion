"""Punctuality assistant (needs internet: Nominatim + OSM routing). Uses temporary data files."""
import sys, asyncio, tempfile, datetime
sys.path.insert(0, '.')
from pathlib import Path
from app.utils import organizer as o, routines, commute
tmp = Path(tempfile.mkdtemp())
o.DIR = tmp; o.EVENTS_FILE = tmp/"e.json"; o.REMINDERS_FILE = tmp/"r.json"; o.CONFIG_FILE = tmp/"o.bin"
routines.FILE = tmp/"ro.json"
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
cfg = routines.load(); cfg["commute"] = {"home": "Hamburg Hauptbahnhof", "mode": "car", "buffer": 10, "enabled": True}; routines.save(cfg)
now = datetime.datetime.now().replace(second=0, microsecond=0)
o.add_event("Zahnarzt", now + datetime.timedelta(hours=26), location="Hamburg Rathaus")
o.add_event("Ohne Ort", now + datetime.timedelta(hours=3))
text = asyncio.run(commute.next_leave_text(""))
print(text)
check("leave time for the appointment with a place", "Zahnarzt" in text and "Losfahren um" in text and "Fahrzeit" in text)
check("appointment without a place is ignored", "Ohne Ort" not in text)
check("unknown query", "keinen kommenden Termin" in asyncio.run(commute.next_leave_text("gibtsnicht")))
# a notice appears 20 minutes before the leaving time: appointment in 25 min, travel 6 + 10 buffer
o.EVENTS_FILE.write_text("[]", encoding="utf-8")
o.add_event("Treffen", now + datetime.timedelta(minutes=25), location="Hamburg Rathaus")
notices = asyncio.run(commute.due_leave_notices())
check("notice shortly before leaving", len(notices) == 1 and "Treffen" in notices[0])
check("only once", asyncio.run(commute.due_leave_notices()) == [])
print("ALL OK" if ok else "FAILED")
