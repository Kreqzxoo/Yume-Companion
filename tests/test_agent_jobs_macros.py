"""Mini agent with the real LLM server (calculator / date tools), jobs store, macros store and macro matching. Temporary files; the agent part needs the LLM server."""
import sys, os, asyncio, tempfile, datetime
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, '.')
from pathlib import Path
from types import SimpleNamespace
from app.utils import jobs, macros, agent
tmp = Path(tempfile.mkdtemp())
jobs.FILE = tmp / "jobs.json"; macros.FILE = tmp / "macros.json"
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
# jobs
now = datetime.datetime.now()
j = jobs.add("Recherchiere die besten Reisezeiten für Island", None, now + datetime.timedelta(hours=10))
check("job queued and due", j and jobs.next_to_run() and jobs.next_to_run()["id"] == j["id"])
check("too short task refused", jobs.add("hm") is None)
jobs.update(j["id"], status="done", result="Juni bis August.")
check("not delivered before deliver_at", jobs.next_to_deliver() is None)
jobs.update(j["id"], deliver_at=(now - datetime.timedelta(minutes=1)).isoformat(timespec="seconds"))
check("delivered when due", jobs.next_to_deliver()["id"] == j["id"])
jobs.update(j["id"], delivered=True)
check("nothing more to deliver", jobs.next_to_deliver() is None)
j2 = jobs.add("Suche Zugverbindungen nach Köln heraus")
check("cancel", jobs.cancel(j2["id"]) == 1 and jobs.next_to_run() is None)
# macros
m = macros.add("Feierabend", ["Licht ausschalten", "Musik pausieren", "Wecker für 6:30 stellen"])
check("macro saved", m and len(m["steps"]) == 3)
for text in ("Feierabend", "starte Feierabend", "führe den Ablauf Feierabend aus", "Ablauf Feierabend", "bitte feierabend"):
    check(f"match {text!r}", (macros.match(text) or {}).get("name") == "Feierabend")
check("no match for other sentences", macros.match("wie war dein Feierabend gestern") is None and macros.match("Musik an") is None)
gone = macros.remove("feierabend")
check("remove + restore", gone and macros.get("Feierabend") is None and (macros.restore(gone) or macros.get("Feierabend")))
if "--live" in sys.argv:
    from app.utils.ai_clients import tools as T
    from app.configuration import configuration as cfgmod
    reg = T.ToolRegistry()
    signals = SimpleNamespace(tool_registry=reg, current_active_character="X",
                              configuration_characters=SimpleNamespace(load_configuration=lambda: {"character_list": {"X": {"conversation_method": "Remote LLM"}}}))
    text = asyncio.run(agent.run_agent(signals, "Wie viel ist 17 mal 23 plus 100? Nutze den Taschenrechner und nenne das Ergebnis.", {"calculator", "get_current_datetime"}, max_steps=5, max_tokens=300))
    print("agent answer:", text)
    check("agent used the calculator (491)", "491" in text)
print("ALL OK" if ok else "FAILED")
