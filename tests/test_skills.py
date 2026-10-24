"""Skills: static safety check, saving after approval, running in a separate process, timeout, changed-after-approval, tool plumbing. Temporary folder."""
import sys, os, asyncio, tempfile, time
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, '.')
from pathlib import Path
from app.utils import skills
tmp = Path(tempfile.mkdtemp())
skills.DIR = tmp / "skills"; skills.APPROVALS = skills.DIR / "approved.json"
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
GOOD = '''NAME = "kurs_rechner"
DESCRIPTION = "Rechnet Euro in eine andere Waehrung um (fester Kurs)"
PARAMETERS = {"betrag": {"type": "number"}, "kurs": {"type": "number"}}
def run(args):
    return "%.2f" % (float(args.get("betrag", 0)) * float(args.get("kurs", 1)))
'''
check("good code passes the check", skills.validate(GOOD)[0])
bad = {
    "subprocess": "import subprocess\nNAME='x'\nDESCRIPTION='d'\nPARAMETERS={}\ndef run(a): return subprocess.run(['calc'])",
    "os.system": "import os\nNAME='x'\nDESCRIPTION='d'\nPARAMETERS={}\ndef run(a): return os.system('del *')",
    "write file": "NAME='x'\nDESCRIPTION='d'\nPARAMETERS={}\ndef run(a):\n    open('a.txt','w').write('x')\n    return ''",
    "eval": "NAME='x'\nDESCRIPTION='d'\nPARAMETERS={}\ndef run(a): return eval(a['e'])",
    "pathlib write": "from pathlib import Path\nNAME='x'\nDESCRIPTION='d'\nPARAMETERS={}\ndef run(a): return Path('a').write_text('x')",
    "socket": "import socket\nNAME='x'\nDESCRIPTION='d'\nPARAMETERS={}\ndef run(a): return ''",
    "no run()": "NAME='x'\nDESCRIPTION='d'\nPARAMETERS={}\n",
    "dunder": "NAME='x'\nDESCRIPTION='d'\nPARAMETERS={}\ndef run(a): return ().__class__.__bases__[0].__subclasses__()",
}
for label, code in bad.items():
    check(f"rejected: {label}", not skills.validate(code)[0])
check("bad name refused", not skills.create("a", GOOD)[0])
check("bad code refused on create", not skills.create("boese", bad["os.system"])[0])
check("create ok", skills.create("kurs rechner", GOOD)[0])
check("listed + approved", [s["name"] for s in skills.list_skills()] == ["kurs_rechner"] and skills.list_skills()[0]["approved"])
r = skills.run("kurs_rechner", {"betrag": 12.5, "kurs": 1.1})
check("runs in its own process", r == (True, "13.75"))
SLOW = GOOD.replace("def run(args):", "def run(args):\n    import time\n    time.sleep(60)")
skills.TIMEOUT = 3
skills.create("langsam", SLOW)
t0 = time.time(); res = skills.run("langsam", {})
check("timeout kills it", not res[0] and "nicht geantwortet" in res[1] and time.time() - t0 < 15)
BROKEN = GOOD.replace("float(args.get(\"betrag\", 0))", "1/0")
skills.create("kaputt", BROKEN)
res = skills.run("kaputt", {})
check("error is reported, not raised", not res[0] and "ZeroDivisionError" in res[1])
# changed after approval
p = Path(skills.get("kurs_rechner")["path"]); p.write_text(GOOD + "\n# tampered\n", encoding="utf-8")
check("changed file is not run any more", not skills.run("kurs_rechner", {})[1].startswith("13") and not skills.get("kurs_rechner")["approved"])
check("delete", skills.delete("kurs_rechner") and skills.get("kurs_rechner") is None)
# tool plumbing
from types import SimpleNamespace
from app.utils.ai_clients import tools as T
t = T.SkillTool()
check("create needs approval, run does not", t.needs_approval({"action": "create"}) and not t.needs_approval({"action": "run"}))
summary = t.get_confirmation_summary({"name": "x", "code": GOOD})
check("approval text shows the code and the check", "def run(args)" in summary and "bestanden" in summary)
phone_ctx = {"system_ref": SimpleNamespace(web_bridge=SimpleNamespace(phone_turn=True))}
res = asyncio.run(t.execute({"action": "create", "name": "neu", "code": GOOD}, phone_ctx))
check("no creation while the user is on the phone", not res["success"] and "am PC" in res["result"])
res = asyncio.run(t.execute({"action": "create", "name": "neu", "code": GOOD}, {"system_ref": SimpleNamespace(web_bridge=SimpleNamespace(phone_turn=False))}))
check("creation on the PC (after approval)", res["success"] and res.get("undo", {}).get("kind") == "skill_add")
res = asyncio.run(t.execute({"action": "run", "name": "neu", "args": {"betrag": 2, "kurs": 3}}, {}))
check("tool run", res["success"] and res["result"] == "6.00")
print("ALL OK" if ok else "FAILED")
