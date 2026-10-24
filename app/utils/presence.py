"""Presence: who is at home? A phone counts as "at home" while it is connected to the PC's server from the home network (private / local address).

Leaving and arriving are detected with a delay (default 5 minutes without connection = away, so a short Wi-Fi hiccup is not "leaving").
Events: ("left", name), ("arrived", name), ("all_left", ""), ("first_arrived", name). The PC then runs the user's sentences for them
(Settings > Organizer > Presence), e.g. "Mach das Licht aus und pausiere die Musik".
"""
from __future__ import annotations

import ipaddress
import time

state: dict = {"home": {}, "away_since": {}, "names": {}, "init": False}


def is_private(ip: str) -> bool:
    try:
        a = ipaddress.ip_address(str(ip).split("%")[0])
        return a.is_private or a.is_loopback or a.is_link_local
    except ValueError:
        return False


def settings() -> dict:
    from app.utils import routines
    c = {"enabled": False, "away_min": 5, "on_leave": "", "on_arrive": "", "on_all_left": "", "on_first_arrived": ""}
    c.update(routines.load().get("presence", {}))
    return c


def current_devices(meta_values) -> dict[str, str]:
    """{device key: name} of the phones connected from a private address."""
    out = {}
    for m in meta_values:
        if m.get("role") == "phone" and is_private(m.get("ip", "")):
            out[str(m.get("device_id") or m.get("name") or "phone")] = str(m.get("name") or "Handy")
    return out


def update(now_devices: dict[str, str], away_after_s: float, now: float | None = None) -> list[tuple[str, str]]:
    """Feeds the current devices; returns the events that just happened."""
    now = time.time() if now is None else now
    events: list[tuple[str, str]] = []
    home: dict = state["home"]
    if not state["init"]:                         # first look after the start: remember, do not trigger
        state["init"] = True
        home.update(now_devices)
        state["names"].update(now_devices)
        return events
    for key, name in now_devices.items():
        state["names"][key] = name
        state["away_since"].pop(key, None)
        if key not in home:
            was_empty = not home
            home[key] = name
            events.append(("arrived", name))
            if was_empty:
                events.append(("first_arrived", name))
    for key in list(home):
        if key in now_devices:
            continue
        since = state["away_since"].setdefault(key, now)
        if now - since >= away_after_s:
            name = home.pop(key)
            state["away_since"].pop(key, None)
            events.append(("left", name))
            if not home:
                events.append(("all_left", ""))
    return events


def sentences_for(event: str, cfg: dict) -> list[str]:
    import re
    key = {"left": "on_leave", "arrived": "on_arrive", "all_left": "on_all_left", "first_arrived": "on_first_arrived"}.get(event, "")
    return [s.strip() for s in re.split(r"[\n;]+", str(cfg.get(key, ""))) if s.strip()]


def reset():
    state.update(home={}, away_since={}, names={}, init=False)
