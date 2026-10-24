"""Tests: voice guard (owner / guest / unknown)."""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.utils import voice_guard as g

bad = []


def check(name, ok):
    print(("OK   " if ok else "FAIL ") + name)
    if not ok:
        bad.append(name)


g.set_speaker("")
check("nothing -> no restriction", g.current() == "")
g.set_speaker("owner")
check("owner -> no restriction", g.current() == "")
g.set_speaker("unknown")
check("unknown -> restricted", g.current() == "unknown" and "unbekannte Person" in g.note("unknown"))
g.set_speaker("Anna")
check("guest -> restricted", g.current() == "Anna" and "Anna" in g.note("Anna"))
g._state["t"] = time.time() - 500
check("old state expires", g.current() == "")
check("private tools are not allowed", not ({"mail", "calendar", "phone", "journal", "files", "knowledge", "people", "remember", "inbox"} & g.GUEST_TOOLS))

print("\nFEHLER: " + ", ".join(bad) if bad else "\nAlles in Ordnung.")
sys.exit(1 if bad else 0)
