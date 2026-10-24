"""Extra dashboard data: LLM servers (chat / vision / image), tool models, phones and Spotify. All reads are short and cached."""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger("DashboardExtra")
_cache: dict = {"t": 0.0, "data": None}
_lock = threading.Lock()


def _get(url: str, token: str = "", timeout: float = 1.5):
    req = urllib.request.Request(url)
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read(200_000)
            try:
                return r.status, json.loads(raw.decode("utf-8", "replace"))
            except ValueError:
                return r.status, None
    except urllib.error.HTTPError as exc:
        return exc.code, None
    except Exception:
        return 0, None


def _probe(name: str, base: str, token: str, app_ctx, last_prompt) -> dict:
    root = base.rstrip("/")
    if root.endswith("/v1"):
        root = root[:-3]
    info = {"name": name, "url": root, "ok": False, "model": "", "n_ctx": None, "slots": None, "busy": None, "warn": ""}
    status, _ = _get(root + "/health", token)
    info["ok"] = status == 200
    if status == 0:
        info["warn"] = "nicht erreichbar"
        return info
    st, props = _get(root + "/props", token)
    if st == 200 and isinstance(props, dict):
        gen = props.get("default_generation_settings") or {}
        info["n_ctx"] = gen.get("n_ctx") or (gen.get("params") or {}).get("n_ctx")
        info["slots"] = props.get("total_slots")
        info["model"] = Path(str(props.get("model_path") or props.get("model_alias") or "")).name
    if not info["model"]:
        st, models = _get(root + "/v1/models", token)
        if st == 200 and isinstance(models, dict) and models.get("data"):
            info["model"] = str(models["data"][0].get("id", ""))
    st, slots = _get(root + "/slots", token)
    if st == 200 and isinstance(slots, list):
        info["busy"] = sum(1 for s in slots if s.get("is_processing"))
    warns = []
    n_ctx = info["n_ctx"]
    if n_ctx and app_ctx and int(app_ctx) > int(n_ctx):
        warns.append(f"Server-Kontext ({n_ctx}) ist kleiner als in der App eingestellt ({app_ctx})")
    if n_ctx and last_prompt and int(last_prompt) > int(n_ctx):
        warns.append(f"Letzter Prompt ({last_prompt} Tokens) passt nicht in den Server-Kontext ({n_ctx})")
    if info["slots"] and int(info["slots"]) > 1:
        warns.append(f"{info['slots']} parallele Slots teilen sich den Kontext - Server mit --parallel 1 starten")
    info["warn"] = " · ".join(warns)
    return info


def _servers(signals) -> list[dict]:
    out = []
    try:
        base = signals.configuration_api.get_token("REMOTE_LLM_BASE_URL") or ""
        token = signals.configuration_api.get_token("REMOTE_LLM_API_TOKEN") or ""
    except Exception:
        base, token = "", ""
    if not base:
        return out
    try:
        app_ctx = signals.configuration_settings.get_main_setting("context_size")
    except Exception:
        app_ctx = None
    try:
        from app.utils.runtime_stats import stats
        last_prompt = (stats.snapshot().get("llm", {}).get("last") or {}).get("in")
    except Exception:
        last_prompt = None
    out.append(_probe("Chat / Werkzeug-LLM", base, token, app_ctx, last_prompt))
    parts = urllib.parse.urlparse(base)
    if parts.hostname and parts.port:
        for name, offset in (("Vision-Server", 1), ("Bild-Server", 2)):
            url = f"{parts.scheme}://{parts.hostname}:{parts.port + offset}"
            info = _probe(name, url, token, None, None)
            if info["warn"] == "nicht erreichbar":
                info["warn"] = ""                       # an optional server that is simply not started
            out.append(info)
    return out


def _tool_models(signals) -> list[dict]:
    items = []
    try:
        from app.gui.agent_models import AGENT_MODELS, models_dir
        folder = models_dir()
        active = str(signals.configuration_settings.get_main_setting("local_llm") or "").lower()
        gpus = signals.configuration_settings.get_main_setting("tool_model_gpus")
        gpus = gpus if isinstance(gpus, dict) else {}
        for e in AGENT_MODELS:
            path = folder / e["file"]
            if path.is_file():
                items.append({"name": e["name"], "file": e["file"], "size_gb": round(path.stat().st_size / 1024 ** 3, 1),
                              "active": bool(active) and e["file"].lower() in active, "gpu": str(gpus.get(e["id"], "") or "auto")})
    except Exception:
        logger.debug("tool models unavailable", exc_info=True)
    return items


def _phones(signals) -> dict:
    from app.utils import mobile_devices, tool_log
    devices = []
    now = time.time()
    try:
        for d in mobile_devices.get_registry().list_devices():
            devices.append({"name": d.get("name", "Android"), "ago": int(now - float(d.get("last_seen", 0)))})
    except Exception:
        pass
    actions = []
    try:
        for e in tool_log.read(80):
            if e.get("tool") == "phone":
                actions.append({"t": e.get("t", ""), "args": e.get("args", ""), "ok": bool(e.get("success")), "result": str(e.get("result", ""))[:80]})
                if len(actions) >= 8:
                    break
    except Exception:
        pass
    return {"connected": bool(mobile_devices.phone_connected()), "devices": devices, "actions": actions}


def _tool_stats() -> list[dict]:
    """Per tool: calls, failures, average seconds and the durations of the latest calls (from the tool log)."""
    from app.utils import tool_log
    per: dict = {}
    try:
        for e in reversed(tool_log.read(400)):                       # oldest first
            d = per.setdefault(e.get("tool", "?"), {"tool": e.get("tool", "?"), "n": 0, "fail": 0, "sum": 0.0, "last": []})
            d["n"] += 1
            d["fail"] += 0 if e.get("success") else 1
            sec = float(e.get("sec") or 0)
            d["sum"] += sec
            d["last"].append(round(sec, 2))
    except Exception:
        pass
    out = []
    for d in per.values():
        out.append({"tool": d["tool"], "n": d["n"], "fail": d["fail"], "avg": round(d["sum"] / max(1, d["n"]), 2), "last": d["last"][-24:]})
    return sorted(out, key=lambda x: -x["n"])


def collect(signals) -> dict:
    with _lock:
        if _cache["data"] is not None and time.time() - _cache["t"] < 4.0:
            return _cache["data"]
    from app.utils import spotify_pc
    data = {
        "servers": _servers(signals),
        "tool_models": _tool_models(signals),
        "phone": _phones(signals),
        "tool_stats": _tool_stats(),
        "spotify": spotify_pc.now_playing(4.0),
    }
    with _lock:
        _cache.update(t=time.time(), data=data)
    return data
