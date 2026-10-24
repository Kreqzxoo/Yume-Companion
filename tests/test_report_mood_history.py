"""Weekly report and mood history with temporary files (offline)."""
import sys, os, tempfile, datetime, asyncio, json
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, '.')
from pathlib import Path
from app.utils import report, mood, tool_log as tl, jobs, journal, organizer as o, people
from app.utils.quick_commands import detect
tmp = Path(tempfile.mkdtemp())
mood.LOG = tmp / "mood_log.json"; tl.LOG_FILE = tmp / "tl.jsonl"; tl.enabled = lambda: True
jobs.FILE = tmp / "jobs.json"; journal.FILE = tmp / "j.json"; people.FILE = tmp / "p.json"
o.DIR = tmp; o.EVENTS_FILE = tmp / "e.json"; o.REMINDERS_FILE = tmp / "r.json"; o.CONFIG_FILE = tmp / "o.bin"
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
# mood history: three tired days, one stressed day
def day(n): return datetime.datetime.now() - datetime.timedelta(days=n)
data = {}
for n, m in ((1, "tired"), (2, "tired"), (3, "tired"), (4, "stressed"), (40, "sad")):
    data[day(n).strftime("%Y-%m-%d")] = {m: 2}
mood.LOG.write_text(json.dumps(data), encoding="utf-8")
s = mood.summary(7)
check("summary names tired on 3 days and stressed on 1", "müde an 3 Tagen" in s and "gestresst an 1 Tag " in s + " ")
check("old entries are outside the window", "traurig" not in mood.summary(7) and "traurig" in mood.summary(60))
mood._state.update(mood="", t=0)
mood.detect("Ich bin so müde heute", datetime.datetime(2026, 10, 19, 12, 0))
check("detect logs the mood of a message", json.loads(mood.LOG.read_text(encoding="utf-8"))[datetime.datetime.now().strftime("%Y-%m-%d")].get("tired", 0) >= 1)
# report
for tool, okk, sec in (("spotify", True, 0.4), ("spotify", True, 0.5), ("phone", False, 9.0), ("calendar", True, 0.2)):
    tl.record(tool, {"action": "x"}, "not_needed", okk, "r", sec)
tl.record("lists", {"action": "add", "quick": True}, "not_needed", True, "r", 0.1, undo={"kind": "memory_add", "id": "none"})
j = jobs.add("Recherchiere die besten Reisezeiten für Island"); jobs.update(j["id"], status="done", result="x")
journal.add("Heute war ein richtig guter Tag")
o.add_event("Zahnarzt", datetime.datetime.now() + datetime.timedelta(days=2, hours=3), location="Praxis")
text = report.build(7)
check("report: actions counted with names", "AKTIONEN: 5 insgesamt" in text and "Musik 2×" in text)
check("report: failures and slow actions", "fehlgeschlagen" in text and "LANGSAM" in text)
check("report: job, mood, journal, next week", "AUFTRÄGE" in text and "STIMMUNG: müde" in text and "TAGEBUCH: 1 Einträge" in text and "NÄCHSTE WOCHE" in text and "Zahnarzt" in text)
n = report.note(7)
check("note instructs the character and carries the data", n.startswith("[WEEKLY REPORT]") and "Do NOT call any tool" in n and "AKTIONEN" in n)
# phrases
for t, want in (("Wochenbericht", True), ("wie war meine Woche", True), ("Mein Wochenrückblick", True), ("was hast du diese Woche für mich gemacht", True), ("wie war dein Tag", False), ("Woche", False)):
    c = detect(t, True, True, True, True, True)
    check(f"phrase {t!r}", bool(c and c["kind"] == "report") == want)
# tool
from app.utils.ai_clients import tools as T
res = asyncio.run(T.ReportTool().execute({"action": "mood", "days": 7}, {}))
check("tool mood", res["success"] and "müde" in res["result"])
res = asyncio.run(T.ReportTool().execute({"action": "week"}, {}))
check("tool week", res["success"] and "AKTIONEN" in res["result"])
print("ALL OK" if ok else "FAILED")
