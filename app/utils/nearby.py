"""Nearby places ("Wo ist die nächste Apotheke, die noch offen hat?") from OpenStreetMap (Overpass API). Needs internet; no key.

Origin: the phone's location when connected, else the home address (Settings > Organizer > Routines). Opening hours are read from the OSM tag
`opening_hours` (simple rules like "Mo-Fr 08:00-18:30; Sa 09:00-13:00"); when a place has none or a complicated rule, "open now" is "unknown".
"""
from __future__ import annotations

import json
import math
import re
import urllib.parse
import urllib.request
from datetime import datetime

UA = {"User-Agent": "YumeCompanion/1.0 (personal assistant on your own PC)"}
ENDPOINTS = ["https://overpass-api.de/api/interpreter", "https://overpass.kumi.systems/api/interpreter"]

# German word -> list of (key, value) OSM tags
KINDS = {
    "apotheke": [("amenity", "pharmacy")], "arzt": [("amenity", "doctors")], "ärztin": [("amenity", "doctors")], "zahnarzt": [("amenity", "dentist")],
    "krankenhaus": [("amenity", "hospital")], "tankstelle": [("amenity", "fuel")], "supermarkt": [("shop", "supermarket")], "bäckerei": [("shop", "bakery")],
    "bäcker": [("shop", "bakery")], "metzger": [("shop", "butcher")], "drogerie": [("shop", "chemist")], "geldautomat": [("amenity", "atm")], "bank": [("amenity", "bank")],
    "post": [("amenity", "post_office")], "briefkasten": [("amenity", "post_box")], "restaurant": [("amenity", "restaurant")], "café": [("amenity", "cafe")], "cafe": [("amenity", "cafe")],
    "kaffee": [("amenity", "cafe")], "imbiss": [("amenity", "fast_food")], "fast food": [("amenity", "fast_food")], "bar": [("amenity", "bar")], "kneipe": [("amenity", "pub")],
    "eisdiele": [("amenity", "ice_cream")], "eis": [("amenity", "ice_cream")], "baumarkt": [("shop", "doityourself"), ("shop", "hardware")], "kiosk": [("shop", "kiosk")],
    "späti": [("shop", "convenience")], "bibliothek": [("amenity", "library")], "schwimmbad": [("leisure", "swimming_pool")], "spielplatz": [("leisure", "playground")],
    "park": [("leisure", "park")], "toilette": [("amenity", "toilets")], "wc": [("amenity", "toilets")], "ladestation": [("amenity", "charging_station")],
    "e-ladesäule": [("amenity", "charging_station")], "fahrradladen": [("shop", "bicycle")], "friseur": [("shop", "hairdresser")], "kino": [("amenity", "cinema")],
    "bahnhof": [("railway", "station")], "haltestelle": [("highway", "bus_stop")], "parkplatz": [("amenity", "parking")], "tierarzt": [("amenity", "veterinary")],
    "optiker": [("shop", "optician")], "buchladen": [("shop", "books")], "buchhandlung": [("shop", "books")], "blumenladen": [("shop", "florist")],
    "elektronik": [("shop", "electronics")], "kleidung": [("shop", "clothes")], "waschsalon": [("shop", "laundry")], "reinigung": [("shop", "dry_cleaning")],
}
DAYS = ["mo", "tu", "we", "th", "fr", "sa", "su"]


def kind_tags(word: str):
    w = str(word or "").strip().lower()
    if w in KINDS:
        return KINDS[w]
    for k, v in KINDS.items():
        if k in w or (len(w) > 3 and w in k):
            return v
    return None


def _distance_m(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 12742000 * math.asin(math.sqrt(h))


def _day_range(spec: str) -> set[int] | None:
    out: set[int] = set()
    for part in spec.lower().replace(" ", "").split(","):
        if "-" in part:
            a, b = part.split("-", 1)
            if a[:2] not in DAYS or b[:2] not in DAYS:
                return None
            i, j = DAYS.index(a[:2]), DAYS.index(b[:2])
            out.update(range(i, j + 1) if i <= j else list(range(i, 7)) + list(range(0, j + 1)))
        elif part[:2] in DAYS:
            out.add(DAYS.index(part[:2]))
        else:
            return None
    return out or None


def is_open(rule: str | None, now: datetime) -> bool | None:
    """True / False, or None when the rule is missing or too complicated."""
    if not rule:
        return None
    rule = rule.strip()
    if rule in ("24/7", "Mo-Su 00:00-24:00"):
        return True
    if any(x in rule.lower() for x in ("sunrise", "sunset", "ph", "sh", "week", "[", "easter")):
        return None
    wd, minutes = now.weekday(), now.hour * 60 + now.minute
    decided = None
    for chunk in [c.strip() for c in rule.split(";") if c.strip()]:
        m = re.match(r"^([A-Za-z,\- ]+?)?\s*((?:\d{1,2}:\d{2}-\d{1,2}:\d{2}(?:\s*,\s*)?)+|off|closed)$", chunk, re.I)
        if not m:
            return None
        days = _day_range(m.group(1)) if m.group(1) else set(range(7))
        if days is None:
            return None
        if wd not in days:
            continue
        times = m.group(2).lower()
        if times in ("off", "closed"):
            decided = False
            continue
        decided = False
        for a, b in re.findall(r"(\d{1,2}:\d{2})-(\d{1,2}:\d{2})", times):
            ha, ma = map(int, a.split(":")); hb, mb = map(int, b.split(":"))
            start, end = ha * 60 + ma, hb * 60 + mb
            if end <= start:
                end += 24 * 60
            if start <= minutes < end or start <= minutes + 24 * 60 < end:
                decided = True
    return decided if decided is not None else False


def _query(lat: float, lon: float, tags, radius: int) -> list[dict]:
    parts = []
    for k, v in tags:
        for t in ("node", "way"):
            parts.append(f'{t}["{k}"="{v}"](around:{radius},{lat},{lon});')
    q = f"[out:json][timeout:20];({''.join(parts)});out center 60;"
    data = urllib.parse.urlencode({"data": q}).encode()
    last: Exception | None = None
    for url in ENDPOINTS:
        try:
            with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=UA), timeout=25) as r:
                return json.loads(r.read().decode("utf-8")).get("elements", [])
        except Exception as exc:                  # next server
            last = exc
    raise RuntimeError(f"Overpass nicht erreichbar: {last}")


def find(kind: str, origin: tuple[float, float], only_open: bool = False, limit: int = 4, now: datetime | None = None) -> list[dict]:
    tags = kind_tags(kind)
    if not tags:
        raise ValueError(f"Mit „{kind}“ kann ich noch nicht suchen.")
    now = now or datetime.now()
    found: list[dict] = []
    for radius in (1500, 4000, 10000):
        found = []
        for el in _query(origin[0], origin[1], tags, radius):
            t = el.get("tags", {})
            pos = (el.get("lat"), el.get("lon")) if "lat" in el else ((el.get("center") or {}).get("lat"), (el.get("center") or {}).get("lon"))
            if pos[0] is None:
                continue
            addr = " ".join(x for x in (t.get("addr:street", ""), t.get("addr:housenumber", "")) if x)
            found.append({"name": t.get("name") or t.get("brand") or t.get("operator") or kind.capitalize(), "address": addr, "meters": _distance_m(origin, pos),
                          "open": is_open(t.get("opening_hours"), now), "hours": t.get("opening_hours", ""), "phone": t.get("phone") or t.get("contact:phone") or ""})
        if only_open:
            found = [f for f in found if f["open"] is not False]
        if len(found) >= limit:
            break
    found.sort(key=lambda f: (f["meters"]))
    return found[:limit]


def describe(items: list[dict], kind: str, only_open: bool, origin_text: str) -> str:
    if not items:
        return f"Ich finde in der Nähe von {origin_text} keine{' geöffnete' if only_open else ''} Treffer für „{kind}“ (Daten von OpenStreetMap, nicht überall vollständig)."
    lines = []
    for i in items:
        d = f"{i['meters'] / 1000:.1f} km" if i["meters"] >= 1000 else f"{int(round(i['meters'], -1))} m"
        state = {True: "jetzt geöffnet", False: "geschlossen", None: "Öffnungszeiten unbekannt"}[i["open"]]
        extra = f", {i['hours']}" if i["hours"] and len(i["hours"]) < 60 else ""
        lines.append(f"{i['name']}{(', ' + i['address']) if i['address'] else ''} – {d}, {state}{extra}{(', Tel. ' + i['phone']) if i['phone'] else ''}")
    return f"Nächste Treffer (von {origin_text}):\n" + "\n".join(lines) + "\n(Quelle: OpenStreetMap; Öffnungszeiten ohne Gewähr)"
