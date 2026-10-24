"""Lists (shopping / to-do), quick phrases for lists and the 'remember' memory incl. the prompt block. Uses temporary files."""
import sys, asyncio, tempfile
sys.path.insert(0, '.')
from pathlib import Path
from app.utils import lists_store as ls, user_memory as um
from app.utils.quick_commands import detect, execute
tmp = Path(tempfile.mkdtemp()); ls.FILE = tmp / "l.json"; um.FILE = tmp / "m.json"
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
c = detect("setz Milch und Brot auf die Einkaufsliste", True, True, True, True, True)
check("add phrase recognised", c and c["kind"] == "lists" and c["action"] == "add")
check("executed", asyncio.run(execute(c, None))[1].startswith("Auf die Einkaufsliste gesetzt: Milch, Brot"))
check("show phrase", (detect("was muss ich noch kaufen", True, True, True, True, True) or {}).get("action") == "show")
check("duplicate ignored", ls.add("Einkaufsliste", "milch")[1] == [])
check("remove by words", ls.remove("Einkaufsliste", "brot") == 1 and [i["text"] for i in ls.show("Einkaufsliste")["Einkaufsliste"]] == ["Milch"])
check("memory add / dedupe", um.add("Ich mag keine Regenhinweise") and len(um.list_items()) == 1 and um.add("ich mag keine regenhinweise")["id"] == um.list_items()[0]["id"])
check("memory prompt block", "keine Regenhinweise" in um.prompt_block() and "{{user}}" in um.prompt_block())
check("memory forget by words", um.forget("regenhinweise") == 1 and um.prompt_block() == "")
print("ALL OK" if ok else "FAILED")
