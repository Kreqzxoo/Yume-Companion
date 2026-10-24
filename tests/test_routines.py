"""Routines: phrase detection (offline) and the collected briefing / good-night notes (weather needs internet, everything else is local)."""
import sys, asyncio
sys.path.insert(0, '.')
from app.utils.quick_commands import detect
from app.utils import routines
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
cases = [("guten morgen", "morning"), ("Moin", "morning"), ("briefing", "morning"), ("was steht heute an?", "morning"), ("wie sieht mein tag aus", "morning"),
         ("gute nacht", "night"), ("ich gehe schlafen", "night"), ("ab ins bett", "night")]
for text, want in cases:
    c = detect(text, True, True, True, True, True)
    check(f"{text!r} -> {want}", c and c["kind"] == "routine" and c["action"] == want)
for text in ["morgen gehe ich zum zahnarzt", "wie war dein morgen", "erzähl mir was über die nacht"]:
    check(f"{text!r} is NOT a routine", not (detect(text, True, True, True, True, True) or {}).get("kind") == "routine")
check("routines off -> no trigger", detect("guten morgen", True, True, True, True, False) is None)
note = asyncio.run(routines.build_note("morning"))
check("morning note has instruction and date", note.startswith("[ROUTINE MORNING]") and "Jetzt:" in note and "TERMINE HEUTE" in note)
night = asyncio.run(routines.build_note("night"))
check("night note has tomorrow part", night.startswith("[ROUTINE NIGHT]") and "TERMINE MORGEN" in night)
print("ALL OK" if ok else "FAILED")
