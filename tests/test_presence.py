"""Tests: presence detection (debounce, arrive / leave / all left)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.utils import presence as p

bad = []


def check(name, ok):
    print(("OK   " if ok else "FAIL ") + name)
    if not ok:
        bad.append(name)


check("private ips", p.is_private("192.168.1.20") and p.is_private("127.0.0.1") and not p.is_private("8.8.8.8") and not p.is_private("abc"))
meta = [{"role": "phone", "device_id": "a", "name": "Max", "ip": "192.168.1.20"}, {"role": "phone", "device_id": "b", "name": "Anna", "ip": "84.1.2.3"}, {"role": "web", "ip": "192.168.1.5"}]
check("only private phones count", p.current_devices(meta) == {"a": "Max"})

p.reset()
T = 1000.0
check("first look = no events", p.update({"a": "Max"}, 300, T) == [])
check("hiccup is not leaving", p.update({}, 300, T + 60) == [] and p.update({"a": "Max"}, 300, T + 100) == [])
check("leaving after delay", p.update({}, 300, T + 200) == [] and p.update({}, 300, T + 520) == [("left", "Max"), ("all_left", "")])
check("arriving", p.update({"a": "Max"}, 300, T + 600) == [("arrived", "Max"), ("first_arrived", "Max")])
ev = p.update({"a": "Max", "b": "Anna"}, 300, T + 700)
check("second arrives, not first", ev == [("arrived", "Anna")])
p.update({"a": "Max"}, 300, T + 800)
check("one leaves, not all", p.update({"a": "Max"}, 300, T + 1200) == [("left", "Anna")])
check("sentences", p.sentences_for("left", {"on_leave": "Licht aus; Musik pausieren\nTür zu"}) == ["Licht aus", "Musik pausieren", "Tür zu"] and p.sentences_for("arrived", {}) == [])

print("\nFEHLER: " + ", ".join(bad) if bad else "\nAlles in Ordnung.")
sys.exit(1 if bad else 0)
