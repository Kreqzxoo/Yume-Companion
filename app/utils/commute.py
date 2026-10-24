"""Punctuality assistant: when do you have to leave for an appointment with a place?

Address -> coordinates with Nominatim (OpenStreetMap), travel time with the OSM routing servers (car / bike / on foot), start from the phone's current
location (when the phone is connected) or the home address. No account and no key; every result is cached.
"""
from __future__ import annotations

import json
import logging
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

from app.utils import routines

logger = logging.getLogger("Commute")
UA = {"User-Agent": "YumeCompanion/1.0 (personal assistant on your own PC)"}
PROFILES = {"car": "routed-car", "bike": "routed-bike", "foot": "routed-foot"}
_geo_cache: dict = {}


def _get(url: str, timeout: float = 12.0):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(address: str) -> tuple[float, float] | None:
    address = " ".join(str(address or "").split())
    if not address:
        return None
    if address in _geo_cache:
        return _geo_cache[address]
    data = _get("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode({"q": address, "format": "json", "limit": 1}))
    point = (float(data[0]["lat"]), float(data[0]["lon"])) if data else None
    _geo_cache[address] = point
    return point


def travel_minutes(origin: tuple[float, float], dest: tuple[float, float], mode: str = "car") -> float | None:
    prof = PROFILES.get(mode, PROFILES["car"])
    url = f"https://routing.openstreetmap.de/{prof}/route/v1/driving/{origin[1]},{origin[0]};{dest[1]},{dest[0]}?overview=false"
    data = _get(url)
    routes = data.get("routes") or []
    return routes[0]["duration"] / 60.0 if routes else None


def settings() -> dict:
    cfg = routines.load()
    c = {"enabled": True, "mode": "car", "buffer": 10, "home": ""}
    c.update(cfg.get("commute", {}))
    return c


def leave_info(location: str, start: datetime, origin: tuple[float, float] | None = None) -> dict:
    """{'ok': bool, 'leave_at', 'minutes', 'origin_text', 'problem'}"""
    cfg = settings()
    dest = geocode(location)
    if dest is None:
        return {"ok": False, "problem": f"Den Ort „{location}“ habe ich nicht gefunden."}
    src, src_text = origin, "deinem Standort"
    if src is None:
        src, src_text = geocode(cfg["home"]), "zu Hause"
    if src is None:
        return {"ok": False, "problem": "Es ist keine Heimadresse eingestellt (Einstellungen > Organizer > Routinen) und kein Handy-Standort verfügbar."}
    minutes = travel_minutes(src, dest, cfg["mode"])
    if minutes is None:
        return {"ok": False, "problem": "Für diese Strecke konnte keine Route berechnet werden."}
    leave_at = start - timedelta(minutes=minutes + float(cfg["buffer"]))
    return {"ok": True, "leave_at": leave_at, "minutes": minutes, "origin_text": src_text, "mode": cfg["mode"], "buffer": cfg["buffer"]}


def describe(info: dict, title: str, start: datetime, rain: str = "") -> str:
    if not info.get("ok"):
        return info.get("problem", "Keine Fahrzeit berechenbar.")
    mode = {"car": "mit dem Auto", "bike": "mit dem Rad", "foot": "zu Fuß"}.get(info["mode"], "")
    text = (f"{title} um {start.strftime('%H:%M')}: Losfahren um {info['leave_at'].strftime('%H:%M')} "
            f"(Fahrzeit {info['minutes']:.0f} Min {mode} von {info['origin_text']}, {info['buffer']:.0f} Min Puffer)")
    return text + (f". {rain}" if rain else ".")


def rain_hint(start: datetime) -> str:
    """'Regenwahrscheinlichkeit 60 % - Jacke / Schirm' for the day of the appointment (empty when dry or unknown)."""
    try:
        from app.utils import weather
        cfg = routines.load()
        place = cfg.get("place") or None
        if not place and cfg.get("location"):
            place = weather.geocode(cfg["location"])
        if not place:
            return ""
        daily = weather.forecast(place["lat"], place["lon"]).get("daily", {})
        day = start.strftime("%Y-%m-%d")
        if day in daily.get("time", []):
            p = daily["precipitation_probability_max"][daily["time"].index(day)]
            if p is not None and p >= 50:
                return f"Regenwahrscheinlichkeit {p:.0f} % - nimm Jacke oder Schirm mit"
    except Exception:
        logger.debug("rain hint failed", exc_info=True)
    return ""

# ------------------------------------------------------------------ with the phone location and the calendar
async def phone_origin() -> tuple[float, float] | None:
    import re
    from app.utils import mobile_devices
    bridge = mobile_devices.BRIDGE
    if bridge is None or not bridge.has_phone():
        return None
    try:
        reply = await bridge.phone_command("location", {}, timeout=10.0)
        m = re.search(r"Position\s+(-?\d+\.\d+),\s*(-?\d+\.\d+)", str(reply.get("data") or ""))
        return (float(m.group(1)), float(m.group(2))) if m else None
    except Exception:
        return None


async def upcoming_with_place(hours: int = 48, query: str = "") -> list[dict]:
    import asyncio
    from app.utils import organizer
    now = datetime.now()
    events, _ = await asyncio.to_thread(organizer.events_between, now, now + timedelta(hours=hours))
    q = (query or "").lower()
    return [e for e in events if e.get("location") and not e["all_day"] and e["start"] > now and (not q or q in e["title"].lower())]


async def next_leave_text(query: str = "") -> str:
    """Answer for 'wann muss ich los?': the next appointment with a place (matching the query)."""
    import asyncio
    found = await upcoming_with_place(72, query)
    if not found:
        return "Ich finde keinen kommenden Termin mit Ort" + (f" zu „{query}“." if query else ". Trage bei Terminen einen Ort ein, dann kann ich die Fahrzeit berechnen.")
    ev = found[0]
    try:
        info = await asyncio.to_thread(leave_info, ev["location"], ev["start"], await phone_origin())
        rain = await asyncio.to_thread(rain_hint, ev["start"]) if info.get("ok") else ""
    except Exception as exc:
        return f"Die Fahrzeit konnte nicht berechnet werden ({str(exc)[:80]})."
    return describe(info, ev["title"], ev["start"], rain)


_notified: set = set()


async def due_leave_notices() -> list[str]:
    """Texts for appointments whose leaving time is within the next 20 minutes (each only once)."""
    import asyncio
    if not settings().get("enabled", True):
        return []
    now = datetime.now()
    out = []
    for ev in await upcoming_with_place(4):
        key = f"{ev['title']}|{ev['start'].isoformat()}"
        if key in _notified:
            continue
        # cheap pre-check: nothing to calculate for appointments that are more than 3 hours away
        if ev["start"] - now > timedelta(hours=3):
            continue
        try:
            info = await asyncio.to_thread(leave_info, ev["location"], ev["start"], await phone_origin())
        except Exception:
            continue
        if not info.get("ok"):
            continue
        if info["leave_at"] - timedelta(minutes=20) <= now:
            _notified.add(key)
            rain = await asyncio.to_thread(rain_hint, ev["start"])
            out.append(describe(info, ev["title"], ev["start"], rain))
    return out
