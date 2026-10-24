"""Weather through Open-Meteo (free, no account / key). The place is looked up once by name and remembered in the routine settings."""
from __future__ import annotations

import json
import logging
import time
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

logger = logging.getLogger("Weather")

CODES = {
    0: "klar", 1: "überwiegend klar", 2: "teils bewölkt", 3: "bedeckt", 45: "Nebel", 48: "Reifnebel",
    51: "leichter Nieselregen", 53: "Nieselregen", 55: "starker Nieselregen", 56: "gefrierender Nieselregen", 57: "starker gefrierender Nieselregen",
    61: "leichter Regen", 63: "Regen", 65: "starker Regen", 66: "gefrierender Regen", 67: "starker gefrierender Regen",
    71: "leichter Schneefall", 73: "Schneefall", 75: "starker Schneefall", 77: "Schneegriesel",
    80: "leichte Regenschauer", 81: "Regenschauer", 82: "heftige Regenschauer", 85: "leichte Schneeschauer", 86: "Schneeschauer",
    95: "Gewitter", 96: "Gewitter mit Hagel", 99: "Gewitter mit starkem Hagel",
}
_cache: dict = {}


def _get(url: str, timeout: float = 10.0) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "YumeCompanion"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def geocode(name: str) -> dict | None:
    """-> {'name', 'lat', 'lon', 'country'} or None"""
    name = (name or "").strip()
    if not name:
        return None
    data = _get("https://geocoding-api.open-meteo.com/v1/search?" + urllib.parse.urlencode({"name": name, "count": 1, "language": "de", "format": "json"}))
    hit = (data.get("results") or [None])[0]
    if not hit:
        return None
    return {"name": hit.get("name", name), "lat": hit["latitude"], "lon": hit["longitude"], "country": hit.get("country", "")}


def forecast(lat: float, lon: float, days: int = 7) -> dict:
    key = (round(lat, 2), round(lon, 2), days)
    cached = _cache.get(key)
    if cached and time.time() - cached[0] < 600:
        return cached[1]
    data = _get("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "auto", "forecast_days": days,
        "current": "temperature_2m,apparent_temperature,weather_code,wind_speed_10m,precipitation",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,precipitation_sum,sunrise,sunset,wind_speed_10m_max,uv_index_max"}))
    _cache[key] = (time.time(), data)
    return data


def _day_name(d: datetime, today: datetime) -> str:
    delta = (d.date() - today.date()).days
    if delta == 0:
        return "Heute"
    if delta == 1:
        return "Morgen"
    return ["Montag", "Dienstag", "Mittwoch", "Donnerstag", "Freitag", "Samstag", "Sonntag"][d.weekday()]


def clothing_tip(tmin: float, tmax: float, rain_p, wind, uv=None) -> str:
    """What to wear: from the day's temperatures, rain probability, wind and UV index."""
    parts = []
    feels = (tmin + tmax) / 2 if tmax - tmin < 10 else (tmin * 0.4 + tmax * 0.6)
    if tmax < 2:
        parts.append("richtig warm anziehen: Winterjacke, Mütze, Schal und Handschuhe")
    elif feels < 7:
        parts.append("warme Jacke und Pullover, morgens eventuell Mütze")
    elif feels < 13:
        parts.append("Jacke und etwas Warmes darunter")
    elif feels < 19:
        parts.append("leichte Jacke oder Pullover")
    elif feels < 25:
        parts.append("T-Shirt, abends eine dünne Jacke")
    else:
        parts.append("luftige Sachen, viel trinken")
    if tmax - tmin >= 10 and feels >= 7:
        parts.append(f"große Schwankung ({tmin:.0f} bis {tmax:.0f} °C): Zwiebellook")
    if rain_p is not None and rain_p >= 50:
        parts.append("Regenjacke oder Schirm einpacken")
    elif rain_p is not None and rain_p >= 30:
        parts.append("vielleicht einen Schirm in die Tasche")
    if wind is not None and wind >= 40:
        parts.append("sehr windig, Mütze festhalten")
    if uv is not None and uv >= 6:
        parts.append("Sonnencreme und Sonnenbrille")
    return "; ".join(parts)


def rain_soon(lat: float, lon: float, horizon_min: int = 120) -> dict | None:
    """Short-term rain at a place (15-minute steps). Returns {'in_minutes', 'mm'} when it is dry now and rain starts within the horizon, else None."""
    data = _get("https://api.open-meteo.com/v1/forecast?" + urllib.parse.urlencode({
        "latitude": lat, "longitude": lon, "timezone": "auto", "minutely_15": "precipitation", "forecast_minutely_15": 12}))
    times = data.get("minutely_15", {}).get("time", [])
    rain = data.get("minutely_15", {}).get("precipitation", [])
    if not times or not rain:
        return None
    now = datetime.now()
    slots = [(datetime.fromisoformat(t), float(m or 0)) for t, m in zip(times, rain)]
    upcoming = [(t, m) for t, m in slots if t >= now - timedelta(minutes=15)]
    if not upcoming or upcoming[0][1] >= 0.2:
        return None                                  # it rains already: an alert would be pointless
    for t, m in upcoming:
        if m >= 0.2:
            minutes = max(0, int((t - now).total_seconds() // 60))
            if minutes <= horizon_min:
                return {"in_minutes": minutes, "mm": m}
            return None
    return None


def describe(place: dict, data: dict, which: str = "today") -> str:
    """which: 'now' | 'today' | 'tomorrow' | 'week'"""
    now = datetime.now()
    daily = data.get("daily", {})
    days = daily.get("time", [])

    def day_line(i: int) -> str:
        d = datetime.fromisoformat(days[i])
        rain = daily.get("precipitation_probability_max", [None] * 9)[i]
        mm = daily.get("precipitation_sum", [0] * 9)[i]
        wind = daily.get("wind_speed_10m_max", [None] * 9)[i]
        parts = [f"{_day_name(d, now)}: {CODES.get(daily['weather_code'][i], 'wechselhaft')}, {daily['temperature_2m_min'][i]:.0f}–{daily['temperature_2m_max'][i]:.0f} °C"]
        if rain is not None:
            parts.append(f"Regenwahrscheinlichkeit {rain:.0f} %" + (f" ({mm:.1f} mm)" if mm else ""))
        if wind is not None and wind >= 30:
            parts.append(f"windig (bis {wind:.0f} km/h)")
        return ", ".join(parts)

    head = f"Wetter für {place.get('name', '?')}"
    cur = data.get("current", {})
    now_line = ""
    if cur:
        now_line = (f"Jetzt: {CODES.get(cur.get('weather_code'), 'wechselhaft')}, {cur.get('temperature_2m', 0):.0f} °C "
                    f"(gefühlt {cur.get('apparent_temperature', 0):.0f} °C), Wind {cur.get('wind_speed_10m', 0):.0f} km/h")
    if which == "now":
        return f"{head}\n{now_line}"
    def tip(i: int) -> str:
        try:
            t = clothing_tip(daily["temperature_2m_min"][i], daily["temperature_2m_max"][i], daily.get("precipitation_probability_max", [None] * 9)[i],
                             daily.get("wind_speed_10m_max", [None] * 9)[i], daily.get("uv_index_max", [None] * 9)[i])
            return f"\nKleidung: {t}" if t else ""
        except Exception:
            return ""

    if which == "tomorrow":
        return f"{head}\n{day_line(1)}{tip(1)}" if len(days) > 1 else head
    if which == "week":
        return head + "\n" + "\n".join(day_line(i) for i in range(min(7, len(days))))
    extra = ""
    if days:
        try:
            extra = f"\nSonnenaufgang {daily['sunrise'][0][11:16]}, Sonnenuntergang {daily['sunset'][0][11:16]}"
        except Exception:
            pass
    return f"{head}\n{now_line}\n{day_line(0)}{extra}{tip(0)}" if days else f"{head}\n{now_line}"


def weather_text(location_name: str = "", saved: dict | None = None, which: str = "today") -> tuple[str, dict | None]:
    """-> (text, place). Looks the place up when it differs from the saved one. Raises nothing: problems come back as text."""
    try:
        place = saved if saved and saved.get("lat") is not None and (not location_name or location_name.lower() == str(saved.get("name", "")).lower()) else None
        if place is None:
            place = geocode(location_name)
            if place is None:
                return (f"Den Ort „{location_name}“ habe ich nicht gefunden." if location_name else "Es ist kein Ort für das Wetter eingestellt (Einstellungen > Organizer)."), None
        return describe(place, forecast(place["lat"], place["lon"]), which), place
    except Exception as exc:
        return f"Wetter nicht abrufbar ({str(exc)[:80]}).", None
