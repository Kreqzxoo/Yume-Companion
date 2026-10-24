"""Data for the wall / tablet display of the phone app (clock, weather, appointments, reminders, lists, birthdays, music, mails). Cached for 20 seconds."""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta

logger = logging.getLogger("Kiosk")
_cache = {"t": 0.0, "data": None}
_mail = {"t": 0.0, "n": None}


def _weather() -> dict:
    from app.utils import routines, weather
    cfg = routines.load()
    place = cfg.get("place") or None
    if not place and cfg.get("location"):
        place = weather.geocode(cfg["location"])
    if not place:
        return {}
    data = weather.forecast(place["lat"], place["lon"])
    daily, cur = data.get("daily", {}), data.get("current", {})
    out = {"place": place.get("name", "")}
    if cur:
        out.update(temp=round(cur.get("temperature_2m", 0)), text=weather.CODES.get(cur.get("weather_code"), ""), feels=round(cur.get("apparent_temperature", 0)))
    if daily.get("time"):
        out.update(tmax=round(daily["temperature_2m_max"][0]), tmin=round(daily["temperature_2m_min"][0]), rain=daily.get("precipitation_probability_max", [None])[0])
        out["tip"] = weather.clothing_tip(daily["temperature_2m_min"][0], daily["temperature_2m_max"][0], daily.get("precipitation_probability_max", [None])[0],
                                          daily.get("wind_speed_10m_max", [None])[0], daily.get("uv_index_max", [None])[0])
        if len(daily["time"]) > 1:
            out["tomorrow"] = f"{daily['temperature_2m_min'][1]:.0f}–{daily['temperature_2m_max'][1]:.0f} °C, {weather.CODES.get(daily['weather_code'][1], '')}"
    return out


def collect(signals) -> dict:
    if _cache["data"] is not None and time.time() - _cache["t"] < 20:
        return _cache["data"]
    from app.utils import organizer, lists_store, people, spotify_pc
    now = datetime.now()
    today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    data: dict = {"character": str(getattr(signals, "current_active_character", "") or "")}
    try:
        data["weather"] = _weather()
    except Exception:
        logger.debug("kiosk weather failed", exc_info=True)
        data["weather"] = {}
    try:
        events, _ = organizer.events_between(today, today + timedelta(days=2))
        rows = []
        for e in events:
            if e["end"] < now and not e["all_day"]:
                continue
            day = "Heute" if e["start"].date() == now.date() else "Morgen"
            rows.append({"title": e["title"], "day": day, "time": "ganztägig" if e["all_day"] else e["start"].strftime("%H:%M"), "place": e.get("location", "")})
        data["events"] = rows[:6]
    except Exception:
        data["events"] = []
    try:
        data["reminders"] = [{"text": r["text"], "when": datetime.fromisoformat(r["when"]).strftime("%d.%m. %H:%M")} for r in organizer.list_reminders()[:3]]
    except Exception:
        data["reminders"] = []
    try:
        lists = lists_store.show("")
        data["lists"] = {name: [i["text"] for i in items][:8] for name, items in list(lists.items())[:3]}
    except Exception:
        data["lists"] = {}
    try:
        data["birthdays"] = [{"name": b["name"], "in_days": b["in_days"]} for b in people.upcoming_birthdays(14)[:3]]
    except Exception:
        data["birthdays"] = []
    try:
        if spotify_pc.connected():
            n = spotify_pc.now_playing(10)
            if n.get("title"):
                data["music"] = {"title": n["title"], "artist": n.get("artist", ""), "playing": bool(n.get("playing"))}
    except Exception:
        pass
    try:
        if organizer.mail_configured():
            if time.time() - _mail["t"] > 120:
                _mail.update(t=time.time(), n=len(organizer.mail_list(30, True, "")))
            data["unread_mails"] = _mail["n"]
    except Exception:
        data["unread_mails"] = None
    data["time"] = now.strftime("%H:%M")
    _cache.update(t=time.time(), data=data)
    return data
