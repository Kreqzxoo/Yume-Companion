"""Travel assistant: trips with calendar entry and reminders, weather and clothing at the destination, booking mails.
Stored in %LOCALAPPDATA%\\YumeCompanion\\trips.json."""
from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import date, datetime, timedelta
from pathlib import Path

FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "trips.json"
_lock = threading.RLock()


def _load() -> list[dict]:
    try:
        data = json.loads(FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(items: list[dict]):
    FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(items[-60:], ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(FILE)


def add(name: str, destination: str, start: date, end: date | None = None, notes: str = "") -> dict:
    trip = {"id": uuid.uuid4().hex[:6], "name": (name or destination).strip()[:60], "destination": destination.strip()[:80], "start": start.isoformat(),
            "end": (end or start).isoformat(), "notes": notes.strip()[:300]}
    with _lock:
        items = _load()
        items.append(trip)
        _save(items)
    return trip


def list_trips(upcoming_only: bool = True) -> list[dict]:
    today = date.today().isoformat()
    items = [t for t in _load() if not upcoming_only or t["end"] >= today]
    return sorted(items, key=lambda t: t["start"])


def get(key: str) -> dict | None:
    key = str(key or "").strip().lower()
    items = list_trips(False)
    if not key:
        return next(iter(list_trips(True)), None)
    return next((t for t in items if t["id"] == key or key in t["name"].lower() or key in t["destination"].lower()), None)


def remove(key: str) -> dict | None:
    t = get(key)
    if not t:
        return None
    with _lock:
        _save([x for x in _load() if x["id"] != t["id"]])
    return t


def restore(trip: dict):
    with _lock:
        items = _load()
        if not any(x["id"] == trip["id"] for x in items):
            items.append(trip)
            _save(items)


def trip_weather(destination: str, start: date, end: date) -> str:
    """Weather and clothing at the destination for the travel days (forecasts exist for about two weeks ahead)."""
    from app.utils import weather
    place = weather.geocode(destination)
    if place is None:
        return f"Den Ort „{destination}“ habe ich nicht gefunden."
    data = weather.forecast(place["lat"], place["lon"], 16)
    daily = data.get("daily", {})
    days = daily.get("time", [])
    chosen = [i for i, d in enumerate(days) if start.isoformat() <= d <= end.isoformat()]
    if not chosen:
        last = days[-1] if days else "?"
        return (f"Für {place['name']} gibt es Vorhersagen nur bis {last}; deine Reise ({start.strftime('%d.%m.')}–{end.strftime('%d.%m.')}) liegt außerhalb. "
                "Typisches Wetter für die Jahreszeit kenne ich hier nicht sicher - frag mich näher am Reisetermin noch einmal.")
    lines = [f"Wetter in {place['name']} ({place.get('country', '')}):"]
    for i in chosen:
        d = datetime.fromisoformat(days[i])
        rain = daily.get("precipitation_probability_max", [None] * 99)[i]
        lines.append(f"{d.strftime('%a %d.%m.')}: {weather.CODES.get(daily['weather_code'][i], 'wechselhaft')}, {daily['temperature_2m_min'][i]:.0f}–{daily['temperature_2m_max'][i]:.0f} °C"
                     + (f", Regen {rain:.0f} %" if rain is not None else ""))
    tmin = min(daily["temperature_2m_min"][i] for i in chosen)
    tmax = max(daily["temperature_2m_max"][i] for i in chosen)
    rains = [daily.get("precipitation_probability_max", [None] * 99)[i] for i in chosen]
    rain = max([r for r in rains if r is not None] or [0])
    uvs = [daily.get("uv_index_max", [None] * 99)[i] for i in chosen]
    wind = max([daily.get("wind_speed_10m_max", [0] * 99)[i] or 0 for i in chosen] or [0])
    lines.append("Packtipp: " + weather.clothing_tip(tmin, tmax, rain, wind, max([u for u in uvs if u is not None] or [None])))
    return "\n".join(lines)
