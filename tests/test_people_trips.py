"""People (birthdays, notes, gifts, undo) and trips (plan -> calendar + reminder, undo, weather text). Temporary files; the weather part needs internet (--live)."""
import sys, os, asyncio, tempfile, datetime
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, '.')
from pathlib import Path
from app.utils import people, trips, organizer as o, tool_log as tl
tmp = Path(tempfile.mkdtemp())
people.FILE = tmp / "p.json"; trips.FILE = tmp / "t.json"
o.DIR = tmp; o.EVENTS_FILE = tmp / "e.json"; o.REMINDERS_FILE = tmp / "r.json"; o.CONFIG_FILE = tmp / "o.bin"
tl.LOG_FILE = tmp / "tl.jsonl"; tl.enabled = lambda: True
from app.utils.ai_clients import tools as T
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
for text, want in (("12.05.", "05-12"), ("12.05.1990", "1990-05-12"), ("1990-05-12", "1990-05-12"), ("--05-12", "05-12"), ("31.02.x", ""), ("quatsch", "")):
    check(f"birthday {text!r} -> {want!r}", people.parse_birthday(text) == want)
async def run(tool, args):
    res = await tool.execute(args, {})
    tl.record(tool.name, args, "not_needed", res["success"], res["result"], 0.1, undo=res.get("undo"))
    return res
async def main():
    pt, tt = T.PeopleTool(), T.TripTool()
    today = datetime.date.today()
    soon = today + datetime.timedelta(days=1)
    r = await run(pt, {"action": "add", "name": "Anna", "relation": "Schwester", "birthday": soon.strftime("%d.%m.") })
    check("person added", r["success"] and "Anna" in r["result"])
    await run(pt, {"action": "add", "name": "Anna", "note": "mag keine Pilze", "gift": "Buch"})
    show = await run(pt, {"action": "show", "name": "anna"})
    check("notes + gift + fuzzy name", "keine Pilze" in show["result"] and "Buch" in show["result"])
    bd = await run(pt, {"action": "birthdays", "days": 7})
    check("tomorrow's birthday with gift hint", "Anna hat morgen Geburtstag" in bd["result"] and "Letztes Geschenk: Buch" in bd["result"])
    check("bad date refused", not (await run(pt, {"action": "add", "name": "Bob", "birthday": "bald"}))["success"])
    check("undo restores the state before the last add", tl.undo()[0] is True)           # undoes the refused? -> nothing: refused entries have no undo; so this undoes the gift/note add
    check("after undo: no gift any more", "Buch" not in (await run(pt, {"action": "show", "name": "Anna"}))["result"])
    check("forget + undo", (await run(pt, {"action": "forget", "name": "Anna"}))["success"] and tl.undo()[0] and people.get("Anna") is not None)
    # contacts import
    check("import contacts rows", people.import_contacts([("Max Muster", "03-15"), ("Ohne Datum", ""), ("Anna", "01-01")]) == 1 and people.get("Max")["birthday"] == "03-15")
    # trips
    start = today + datetime.timedelta(days=20)
    t = await run(tt, {"action": "plan", "destination": "Rom", "start": start.isoformat(), "end": (start + datetime.timedelta(days=4)).isoformat(), "name": "Urlaub Rom"})
    check("trip planned: calendar + reminder", t["success"] and len(o._read_json(o.EVENTS_FILE, [])) == 1 and len(o.list_reminders()) == 1)
    check("trip listed", "Rom" in (await run(tt, {"action": "list"}))["result"])
    check("undo removes trip, event and reminder", tl.undo()[0] and trips.list_trips() == [] and o._read_json(o.EVENTS_FILE, []) == [] and o.list_reminders() == [])
    check("plan without a date is refused", not (await run(tt, {"action": "plan", "destination": "Rom"}))["success"])
    if "--live" in sys.argv:
        soon_start = today + datetime.timedelta(days=3)
        w = await run(tt, {"action": "weather", "destination": "Rom", "start": soon_start.isoformat(), "end": (soon_start + datetime.timedelta(days=2)).isoformat()})
        print(w["result"][:300])
        check("destination weather with packing tip", w["success"] and "Packtipp" in w["result"])
        far = await run(tt, {"action": "weather", "destination": "Rom", "start": (today + datetime.timedelta(days=90)).isoformat(), "end": (today + datetime.timedelta(days=95)).isoformat()})
        check("too far ahead is said honestly", "nur bis" in far["result"])
asyncio.run(main())
print("ALL OK" if ok else "FAILED")
