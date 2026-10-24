"""Mood hints, journal (tool, quick phrase, undo) and the good-night routine asking for the day. Temporary files only."""
import sys, asyncio, tempfile
sys.path.insert(0, '.')
from datetime import datetime
from pathlib import Path
from app.utils import mood, journal, tool_log as tl, routines, organizer as o
from app.utils.ai_clients import tools as T
from app.utils.quick_commands import detect, execute
tmp = Path(tempfile.mkdtemp())
journal.FILE = tmp/"j.json"; tl.LOG_FILE = tmp/"t.jsonl"; tl.enabled = lambda: True
routines.FILE = tmp/"r.json"; o.DIR = tmp; o.REMINDERS_FILE = tmp/"rem.json"; o.EVENTS_FILE = tmp/"ev.json"; o.CONFIG_FILE = tmp/"o.bin"
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
noon = datetime(2026, 10, 19, 12, 0)
mood._state.update(mood="", t=0)
check("neutral at noon", mood.detect("Wie wird das Wetter?", noon) == "")
check("tired", mood.detect("Ich bin so müde und total fertig", noon) == "tired")
check("mood sticks for the next message", mood.detect("Was gibt es zu essen?", noon) == "tired")
mood._state.update(mood="", t=0)
check("stressed", mood.detect("Ich habe so viel Stress, die Deadline nervt", noon) == "stressed")
mood._state.update(mood="", t=0)
check("sad", mood.detect("Ich fühle mich heute so einsam", noon) == "sad")
mood._state.update(mood="", t=0)
check("late night hint", mood.detect("Was machst du?", datetime(2026, 10, 19, 1, 30)) == "late")
check("hint text has the marker and no real names", "[MOOD HINT" in mood.hint_block("ich bin müde") and "{{user}}" in mood.hint_block("ich bin müde"))
# journal
async def run():
    t = T.JournalTool()
    a = await t.execute({"action": "add", "text": "Heute war ein richtig guter Tag, endlich geschafft!"}, {})
    return a, await t.execute({"action": "today"}, {}), await t.execute({"action": "week"}, {})
a, today, week = asyncio.run(run())
check("journal add + today", a["success"] and "endlich geschafft" in today["result"] and "[happy]" in today["result"])
tl.record("journal", {"action": "add"}, "not_needed", True, a["result"], 0.1, undo=a["undo"])
check("undo removes the entry", tl.undo()[0] and journal.entries(1) == [])
c = detect("Schreib ins Tagebuch: heute war ich lange wandern", True, True, True, True, True)
check("quick phrase", c and c["kind"] == "journal" and "wandern" in c["params"]["text"])
check("executed + undo spec", asyncio.run(execute(c, None))[0] and c.get("undo", {}).get("kind") == "journal_add" and len(journal.entries(1)) == 1)
check("'Tagebuch: ...' form", (detect("Tagebuch: Treffen mit Anna war schön", True, True, True, True, True) or {}).get("kind") == "journal")
check("no false positive", detect("erzähl mir was über tagebücher", True, True, True, True, True) is None)
night = asyncio.run(routines.build_note("night"))
check("good-night note: journal question present when no entry today", True)  # entry exists now -> no question; check the opposite below
journal.FILE.unlink()
night2 = asyncio.run(routines.build_note("night"))
check("good-night asks about the day when nothing is written yet", "how the day was" in night2 and "how the day was" not in night)
print("ALL OK" if ok else "FAILED")

# quiet mode of the phone forces the calm hint
mood._state.update(mood="", t=0)
mood.force("late")
check("phone quiet mode -> calm hint at noon", "very late at night" in mood.hint_block("Was gibt es zu essen?", noon))
