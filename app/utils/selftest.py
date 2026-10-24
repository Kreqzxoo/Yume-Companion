"""Self test: checks everything Yume depends on and says in plain words what is missing and what to do.

Each check returns (name, state, detail) with state 'ok' | 'warn' | 'fail' | 'off' ('off' = not set up, nothing wrong).
"""
from __future__ import annotations

import json
import logging
import time
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("SelfTest")
APP_ROOT = Path(__file__).resolve().parents[2]


def _safe(fn, name):
    try:
        return fn()
    except Exception as exc:
        logger.debug("selftest %s failed", name, exc_info=True)
        return [(name, "fail", f"Prüfung abgebrochen: {str(exc)[:100]}")]


def check_llm(signals) -> list[tuple]:
    from app.utils import dashboard_extra
    out = []
    servers = dashboard_extra._servers(signals)
    if not servers:
        return [("Sprachmodell", "off", "Kein Remote-LLM-Server eingestellt (lokales Modell oder Cloud-Anbieter wird verwendet).")]
    chat = servers[0]
    if not chat["ok"]:
        return [("LLM-Server", "fail", f"Nicht erreichbar ({chat['url']}). Läuft der Yume LLM Server, stimmen Adresse/Port, ist die Firewall offen?")]
    detail = f"{chat['model'] or 'Modell'} · Kontext {chat['n_ctx'] or '?'} · {chat['slots'] or '?'} Slot(s)"
    state = "ok"
    if chat["n_ctx"] and int(chat["n_ctx"]) < 12000:
        state, detail = "warn", detail + " – Kontext zu klein für Werkzeuge: im Yume LLM Server auf 16384 stellen und neu starten."
    elif chat["warn"]:
        state, detail = "warn", detail + " – " + chat["warn"]
    out.append(("LLM-Server", state, detail))
    # real tool call (2 seconds): does the model call a tool when it should?
    try:
        base = signals.configuration_api.get_token("REMOTE_LLM_BASE_URL").rstrip("/")
        token = signals.configuration_api.get_token("REMOTE_LLM_API_TOKEN") or ""
        body = {"messages": [{"role": "system", "content": "Call a tool when the user asks for something a tool can do."}, {"role": "user", "content": "Wie viel ist 17 mal 23?"}],
                "tools": [{"type": "function", "function": {"name": "calculator", "description": "Calculate an expression.",
                                                            "parameters": {"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"]}}}],
                "max_tokens": 200, "temperature": 0.1, "chat_template_kwargs": {"enable_thinking": False}}
        req = urllib.request.Request(base + ("/chat/completions" if base.endswith("/v1") else "/v1/chat/completions"), data=json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json", **({"Authorization": "Bearer " + token} if token else {})})
        t0 = time.time()
        with urllib.request.urlopen(req, timeout=30) as r:
            msg = json.loads(r.read().decode())["choices"][0]["message"]
        took = time.time() - t0
        if msg.get("tool_calls"):
            out.append(("Werkzeug-Aufruf", "ok", f"Das Modell ruft Werkzeuge korrekt auf ({took:.1f} s)."))
        else:
            out.append(("Werkzeug-Aufruf", "warn", "Das Modell hat bei einer Rechenaufgabe kein Werkzeug aufgerufen: Modell ohne Function-Calling? Server mit --jinja starten."))
    except Exception as exc:
        out.append(("Werkzeug-Aufruf", "warn", f"Test nicht möglich ({str(exc)[:80]})."))
    return out


def check_spotify() -> list[tuple]:
    from app.utils import spotify_pc
    if not spotify_pc.client_id():
        return [("Spotify", "off", "Nicht eingerichtet (Einstellungen > Spotify).")]
    if not spotify_pc.connected():
        return [("Spotify", "warn", "Client-ID ist eingetragen, aber noch nicht angemeldet.")]
    devs = spotify_pc.devices()
    if not devs:
        return [("Spotify", "warn", "Angemeldet, aber kein Gerät gefunden – öffne Spotify einmal am Handy oder PC (Premium wird zum Steuern benötigt).")]
    return [("Spotify", "ok", f"Angemeldet · {len(devs)} Gerät(e): " + ", ".join(d.get("name", "?") for d in devs[:3]))]


def check_mail_calendar_weather() -> list[tuple]:
    from app.utils import organizer, routines, weather
    out = []
    if organizer.mail_configured():
        ok, text = organizer.mail_test()
        out.append(("Mail", "ok" if ok else "fail", text))
    else:
        out.append(("Mail", "off", "Nicht eingerichtet (Einstellungen > Organizer)."))
    urls = [u for u in organizer.config().get("ics", []) if u.strip()]
    if urls:
        now = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        events, problems = organizer.events_between(now, now + timedelta(days=30))
        n = len([e for e in events if e["source"] == "Kalender"])
        out.append(("Kalender-Links", "fail" if problems else "ok", "; ".join(problems) if problems else f"{len(urls)} Link(s), {n} Termin(e) in 30 Tagen."))
    else:
        out.append(("Kalender-Links", "off", "Keine iCal-Links eingetragen (der Handy-Kalender wird trotzdem gelesen)."))
    cfg = routines.load()
    if not cfg.get("location"):
        out.append(("Wetter", "off", "Kein Ort eingestellt (Einstellungen > Organizer > Routinen)."))
    else:
        text, place = weather.weather_text(cfg["location"], cfg.get("place") or None, "now")
        out.append(("Wetter", "ok" if place else "fail", (text.splitlines() or [""])[-1] if place else text))
    out.append(("Morgen-Briefing", "ok" if cfg["morning"].get("enabled") else "off",
                f"Automatisch um {cfg['morning'].get('time')}" if cfg["morning"].get("enabled") else "Automatik aus („Guten Morgen“ sagen geht trotzdem)."))
    return out


def check_phone(signals) -> list[tuple]:
    from app.utils import mobile_devices
    wb = getattr(signals, "web_bridge", None)
    if wb is None:
        return [("Handy-Server", "fail", "Der Android-Server läuft nicht (Einstellungen > Android Connector).")]
    if not mobile_devices.phone_connected():
        devs = mobile_devices.get_registry().list_devices()
        return [("Handy", "warn", "Kein Handy verbunden." + (f" Bekannt: {', '.join(d['name'] for d in devs[:2])} – App am Handy öffnen, gleiches WLAN?" if devs else " Noch nie gekoppelt."))]
    caps = []
    for meta in wb.manager.meta.values():
        if meta.get("role") == "phone":
            caps = meta.get("caps") or []
            break
    want = {"notify": "Benachrichtigungen vom PC", "calendar": None, "camera": "Kamera", "screen": "Bildschirm lesen/bedienen (Bedienungshilfe)", "notifications": "Benachrichtigungen lesen",
            "location": "Standort", "call": "Anrufe", "contacts": "Kontakte"}
    missing = [label for key, label in want.items() if label and key not in caps]
    detail = "Verbunden · " + ", ".join(caps[:8])
    return [("Handy", "ok" if not missing else "warn", detail + (f" · Nicht freigegeben/aktiv: {', '.join(missing)}" if missing else ""))]


def check_system(signals) -> list[tuple]:
    out = []
    root = APP_ROOT
    try:
        import shutil
        free = shutil.disk_usage(str(root)).free / 1024 ** 3
        out.append(("Speicherplatz", "ok" if free >= 10 else ("warn" if free >= 3 else "fail"), f"{free:.0f} GB frei auf dem Laufwerk der App."))
    except Exception:
        pass
    from app.utils import alerts
    age = alerts.latest_backup_age_days(root)
    if age is None:
        out.append(("Backup", "warn", "Es gibt noch kein Backup (Einstellungen > Backup & Wiederherstellung)."))
    else:
        out.append(("Backup", "ok" if age <= 14 else "warn", f"Letztes Backup vor {age:.0f} Tag(en)."))
    try:
        data = signals.configuration_characters.load_configuration().get("character_list", {})
        name = getattr(signals, "current_active_character", None) or next(iter(data), "")
        info = data.get(name, {})
        engine = str(info.get("current_text_to_speech") or "Nothing")
        out.append(("Sprachausgabe", "ok" if engine not in ("", "Nothing", "None") else "off", f"{name}: {engine}" if engine not in ("Nothing", "None", "") else f"{name}: ausgeschaltet"))
    except Exception:
        pass
    out.append(("Erinnerungen", "ok" if getattr(signals, "_organizer_loop_started", False) else "warn",
                "Planer läuft (prüft alle 15 Sekunden)." if getattr(signals, "_organizer_loop_started", False) else "Der Erinnerungs-Planer wurde nicht gestartet."))
    return out


def run_all(signals) -> list[dict]:
    """Blocking (network calls): run it in a thread."""
    results = []
    for name, fn in (("LLM", lambda: check_llm(signals)), ("Spotify", check_spotify), ("Organizer", check_mail_calendar_weather),
                     ("Handy", lambda: check_phone(signals)), ("System", lambda: check_system(signals))):
        for item in _safe(fn, name):
            results.append({"name": item[0], "state": item[1], "detail": item[2]})
    return results


def summary(results: list[dict]) -> str:
    bad = [r for r in results if r["state"] == "fail"]
    warn = [r for r in results if r["state"] == "warn"]
    if not bad and not warn:
        return "Alles in Ordnung."
    return f"{len(bad)} Fehler, {len(warn)} Hinweis(e)."
