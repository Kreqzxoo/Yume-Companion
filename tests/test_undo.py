"""Activity log with 'undo': every undoable action can be taken back (reminders, events, lists, memory). Temporary files only."""
import sys, asyncio, tempfile, datetime
sys.path.insert(0, '.')
from pathlib import Path
from app.utils import organizer as o, lists_store as ls, user_memory as um, tool_log as tl
from app.utils.ai_clients import tools as T
from app.utils.quick_commands import detect, execute
tmp = Path(tempfile.mkdtemp())
o.DIR = tmp; o.EVENTS_FILE = tmp/"e.json"; o.REMINDERS_FILE = tmp/"r.json"; o.CONFIG_FILE = tmp/"o.bin"
ls.FILE = tmp/"l.json"; um.FILE = tmp/"m.json"; tl.LOG_FILE = tmp/"tool_log.jsonl"
tl.enabled = lambda: True
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
async def run(tool, args):
    res = await tool.execute(args, {})
    tl.record(tool.name, args, "not_needed", res["success"], res["result"], 0.1, undo=res.get("undo"))
    return res
now = datetime.datetime.now().replace(second=0, microsecond=0)
async def main():
    rm, cal, lst, mem = T.ReminderTool(), T.CalendarTool(), T.ListsTool(), T.RememberTool()
    # reminder add -> undo
    await run(rm, {"action": "add", "text": "Wäsche", "in_minutes": 30})
    check("reminder exists", len(o.list_reminders()) == 1)
    check("undo removes it", tl.undo()[0] and o.list_reminders() == [])
    # reminder cancel -> undo restores
    await run(rm, {"action": "add", "text": "Tabletten", "in_minutes": 60})
    await run(rm, {"action": "cancel", "id": "all"})
    check("cancelled", o.list_reminders() == [])
    check("undo restores", tl.undo()[0] and [r["text"] for r in o.list_reminders()] == ["Tabletten"])
    # event add / delete
    a = await run(cal, {"action": "add", "title": "Zahnarzt", "start": (now + datetime.timedelta(days=1)).isoformat()})
    eid = a["undo"]["id"]
    await run(cal, {"action": "delete", "id": eid})
    check("event deleted", o.get_event(eid) is None)
    check("undo restores event", tl.undo()[0] and o.get_event(eid) is not None)
    check("undo of add removes event", tl.undo()[0] and o.get_event(eid) is None)
    # lists
    await run(lst, {"action": "add", "list": "Einkaufsliste", "item": "Milch, Brot"})
    await run(lst, {"action": "remove", "list": "Einkaufsliste", "item": "milch"})
    check("milch removed", [i["text"] for i in ls.show("Einkaufsliste")["Einkaufsliste"]] == ["Brot"])
    check("undo puts milch back", tl.undo()[0] and sorted(i["text"] for i in ls.show("Einkaufsliste")["Einkaufsliste"]) == ["Brot", "Milch"])
    check("undo of add empties the list", tl.undo()[0] and ls.show("Einkaufsliste") == {})
    # memory
    await run(mem, {"action": "add", "text": "Mein Hund heißt Rex"})
    await run(mem, {"action": "forget", "id": "rex"})
    check("forgotten", um.list_items() == [])
    check("undo restores memory", tl.undo()[0] and len(um.list_items()) == 1)
    # a done undo is not offered twice; nothing left to undo -> clear message
    while tl.undoable():
        tl.undo()
    ok_, text = tl.undo()
    check("nothing left to undo", not ok_ and "nichts" in text)
asyncio.run(main())
c = detect("mach das rückgängig", True, True, True, True, True)
check("quick phrase 'mach das rückgängig'", c and c["kind"] == "undo")
check("quick phrase 'rückgängig'", (detect("rückgängig", True, True, True, True, True) or {}).get("kind") == "undo")
check("'stopp' is not undo", (detect("zurück zur musik", True, True, True, False, True) or {}).get("kind") != "undo")
print("ALL OK" if ok else "FAILED")
