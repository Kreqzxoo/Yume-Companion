"""Tests: mail drafts (local), knowledge notes with sources, nearby (opening hours + fake Overpass)."""
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
bad = []


def check(name, ok):
    print(("OK   " if ok else "FAIL ") + name)
    if not ok:
        bad.append(name)


tmp = Path(tempfile.mkdtemp())

# ---- drafts
from app.utils import organizer as o
o.DRAFTS_FILE = tmp / "drafts.json"
o.config = lambda: {}                      # no mail account: local list only
d = o.save_draft("anna@example.de", "Zusage", "Hallo Anna,\nich komme gern.")
check("draft saved locally", "nur in Yume" in d["where"] and o.get_draft("latest")["id"] == d["id"])
check("draft found by subject", o.get_draft("zusage")["id"] == d["id"])
check("mailto url", o.mailto_url(d).startswith("mailto:anna@example.de?subject=Zusage&body=Hallo"))
check("draft deleted", o.delete_draft(d["id"]) is not None and not o.list_drafts())

# ---- knowledge with sources
from app.utils import knowledge as k
k.DIR = tmp; k.CONFIG = tmp / "k.json"; k.DB = tmp / "k.db"; k.SAVED = tmp / "saved"
p = k.add_note("Der Garagencode ist 4711.", "Garage")
hits = k.search("Garagencode")
check("note searchable", bool(hits))
check("note source named", bool(hits) and k.source_of(hits[0]["path"]) == "eigene Notiz")
p2 = k.add_note("Öffnungszeiten der Bibliothek: Dienstag bis Freitag.", "Bibliothek", "https://example.org/bib")
h2 = k.search("Bibliothek Öffnungszeiten")
check("web source kept", bool(h2) and k.source_of(h2[0]["path"]) == "https://example.org/bib")
check("saved folder not in user folders", k.user_folders() == [] and str(k.SAVED) in k.folders())

# ---- nearby
from app.utils import nearby as n
mo10 = datetime(2026, 10, 19, 10, 0)      # Monday
su10 = datetime(2026, 10, 18, 10, 0)      # Sunday
check("open Mo-Fr", n.is_open("Mo-Fr 08:00-18:30; Sa 09:00-13:00", mo10) is True)
check("closed Sunday", n.is_open("Mo-Fr 08:00-18:30; Sa 09:00-13:00", su10) is False)
check("closed late", n.is_open("Mo-Fr 08:00-18:30", datetime(2026, 10, 19, 20, 0)) is False)
check("24/7", n.is_open("24/7", su10) is True)
check("complicated -> unknown", n.is_open("Mo-Fr sunrise-sunset", mo10) is None and n.is_open(None, mo10) is None)
check("two ranges", n.is_open("Mo-Fr 08:00-12:00,14:00-18:00", datetime(2026, 10, 19, 13, 0)) is False)
check("kind map", n.kind_tags("Apotheke") == [("amenity", "pharmacy")] and n.kind_tags("Tankstellen")[0] == ("amenity", "fuel") and n.kind_tags("xyzabc") is None)
n._query = lambda lat, lon, tags, r: [
    {"lat": 52.001, "lon": 13.0, "tags": {"name": "Zu", "opening_hours": "Mo-Fr 08:00-09:00"}},
    {"lat": 52.002, "lon": 13.0, "tags": {"name": "Auf", "opening_hours": "Mo-Fr 08:00-18:00"}},
    {"center": {"lat": 52.003, "lon": 13.0}, "tags": {"name": "Unbekannt"}}]
items = n.find("apotheke", (52.0, 13.0), only_open=True, limit=3, now=mo10)
check("only_open drops closed", [i["name"] for i in items] == ["Auf", "Unbekannt"])
check("describe", "Auf" in n.describe(items, "apotheke", True, "zu Hause") and "OpenStreetMap" in n.describe(items, "apotheke", True, "zu Hause"))

print("\nFEHLER: " + ", ".join(bad) if bad else "\nAlles in Ordnung.")
sys.exit(1 if bad else 0)
