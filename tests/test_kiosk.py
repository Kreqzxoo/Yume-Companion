"""Data for the wall / tablet display: structure and content with temporary stores and a fake weather (offline)."""
import sys, os, tempfile, datetime
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, '.')
from pathlib import Path
from types import SimpleNamespace
from app.utils import kiosk, organizer as o, lists_store as ls, people
tmp = Path(tempfile.mkdtemp())
o.DIR = tmp; o.EVENTS_FILE = tmp / "e.json"; o.REMINDERS_FILE = tmp / "r.json"; o.CONFIG_FILE = tmp / "o.bin"
ls.FILE = tmp / "l.json"; people.FILE = tmp / "p.json"
kiosk._weather = lambda: {"place": "Hamburg", "temp": 12, "text": "bedeckt", "tmax": 14, "tmin": 9, "rain": 40, "tip": "Jacke"}
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
now = datetime.datetime.now().replace(second=0, microsecond=0)
o.add_event("Zahnarzt", now + datetime.timedelta(hours=2), location="Praxis")
o.add_reminder("Wäsche aufhängen", now + datetime.timedelta(hours=1))
ls.add("Einkaufsliste", "Milch, Brot")
people.add_or_update("Anna", birthday=(datetime.date.today() + datetime.timedelta(days=1)).strftime("%d.%m."))
d = kiosk.collect(SimpleNamespace(current_active_character="Yume"))
check("weather", d["weather"]["temp"] == 12 and d["weather"]["tip"] == "Jacke")
check("event with day and time", d["events"] and d["events"][0]["title"] == "Zahnarzt" and d["events"][0]["day"] in ("Heute", "Morgen") and ":" in d["events"][0]["time"])
check("reminder", d["reminders"] and d["reminders"][0]["text"] == "Wäsche aufhängen")
check("shopping list", d["lists"].get("Einkaufsliste") == ["Milch", "Brot"])
check("birthday tomorrow", d["birthdays"] and d["birthdays"][0]["in_days"] == 1)
check("character and clock", d["character"] == "Yume" and len(d["time"]) == 5)
check("cached for 20 seconds", kiosk.collect(SimpleNamespace(current_active_character="X")) is d)
print("ALL OK" if ok else "FAILED")
