"""Yume Companion performance & status dashboard (separate web interface, own port, own token).

Read-only: it only reports numbers (CPU, RAM, GPU, processes, services, log tail). It never changes settings and never
exposes chats or API keys. Bound to 127.0.0.1 unless the user enables LAN access.
"""
from __future__ import annotations

import asyncio
import collections
import ipaddress
import logging
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse

logger = logging.getLogger("Dashboard")

APP_ROOT = Path(__file__).resolve().parents[2]
HISTORY_LEN = 150
SAMPLE_SECONDS = 2.0
_SECRET_RE = re.compile(r"(?i)((?:token|api[_-]?key|secret|password|authorization)\W{0,4})([A-Za-z0-9_\-\.=:/+]{8,})")


def _mask(line: str) -> str:
    return _SECRET_RE.sub(lambda m: m.group(1) + "********", line)


def _read_version() -> str:
    try:
        return (APP_ROOT / "VERSION.txt").read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def _gpu_info() -> list[dict]:
    """NVIDIA GPUs through nvidia-smi (fast, no extra packages); empty list if unavailable."""
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        out = subprocess.run(
            ["nvidia-smi", "--query-gpu=index,name,utilization.gpu,memory.used,memory.total,temperature.gpu,power.draw",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=4, creationflags=flags,
        ).stdout
    except Exception:
        return []
    gpus = []
    for line in out.strip().splitlines():
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 6:
            continue

        def num(v):
            try:
                return float(v)
            except ValueError:
                return None
        gpus.append({
            "index": int(num(parts[0]) or 0), "name": parts[1], "util": num(parts[2]),
            "mem_used": num(parts[3]), "mem_total": num(parts[4]), "temp": num(parts[5]),
            "power": num(parts[6]) if len(parts) > 6 else None,
        })
    return gpus


class MetricsSampler:
    """Collects system/app numbers in the background and keeps a short history for the charts."""

    def __init__(self):
        self.history = collections.deque(maxlen=HISTORY_LEN)
        self.latest: dict = {}
        self._proc = psutil.Process(os.getpid())
        self._last_net = psutil.net_io_counters()
        self._last_t = time.time()
        self._thread = None
        self._stop_event = None
        self._users = 0
        psutil.cpu_percent(None)
        self._proc.cpu_percent(None)

    def acquire(self):
        self._users += 1
        self.start()

    async def release(self):
        self._users = max(0, self._users - 1)
        if self._users == 0:
            await self.stop()

    def start(self):
        """Runs in its own thread: independent of the Qt/asyncio loop (which can refuse new tasks during start-up)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop_event = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="YumeMetrics", daemon=True)
        self._thread.start()

    async def stop(self):
        self._stop_sync()

    def _stop_sync(self):
        if self._stop_event is not None:
            self._stop_event.set()
        self._thread = None

    def _loop(self):
        event = self._stop_event
        while not event.is_set():
            try:
                self.latest = self._sample()
                self.history.append({k: self.latest[k] for k in ("t", "cpu", "ram", "gpu", "vram", "net_down", "net_up")})
            except Exception as exc:
                logger.debug("sample failed: %s", exc)
            event.wait(SAMPLE_SECONDS)

    def _sample(self) -> dict:
        now = time.time()
        vm = psutil.virtual_memory()
        net = psutil.net_io_counters()
        dt = max(now - self._last_t, 0.001)
        down = (net.bytes_recv - self._last_net.bytes_recv) / dt
        up = (net.bytes_sent - self._last_net.bytes_sent) / dt
        self._last_net, self._last_t = net, now
        gpus = _gpu_info()
        gpu_util = max((g["util"] or 0 for g in gpus), default=None)
        vram_pct = None
        if gpus and gpus[0]["mem_total"]:
            vram_pct = round(100.0 * (gpus[0]["mem_used"] or 0) / gpus[0]["mem_total"], 1)
        try:
            disk = psutil.disk_usage(str(APP_ROOT.anchor or APP_ROOT))
            disk_info = {"used": disk.used, "total": disk.total, "percent": disk.percent}
        except OSError:
            disk_info = {"used": 0, "total": 0, "percent": 0}

        procs = []
        try:
            family = [self._proc] + self._proc.children(recursive=True)
            for p in family:
                try:
                    with p.oneshot():
                        procs.append({
                            "pid": p.pid, "name": p.name(), "cpu": p.cpu_percent(None) / max(psutil.cpu_count() or 1, 1),
                            "rss": p.memory_info().rss, "threads": p.num_threads(),
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        procs.sort(key=lambda x: x["rss"], reverse=True)
        main = procs[0] if procs else {"cpu": 0, "rss": 0, "threads": 0}
        return {
            "t": int(now), "cpu": psutil.cpu_percent(None), "cores": psutil.cpu_percent(None, percpu=True),
            "cpu_freq": (psutil.cpu_freq().current if psutil.cpu_freq() else None),
            "ram": vm.percent, "ram_used": vm.used, "ram_total": vm.total,
            "gpu": gpu_util, "vram": vram_pct, "gpus": gpus, "disk": disk_info,
            "net_down": down, "net_up": up,
            "app": {"cpu": main["cpu"], "rss": main["rss"], "threads": main["threads"],
                    "uptime": int(now - self._proc.create_time()), "children": len(procs) - 1},
            "procs": procs[:8],
            "boot_time": int(psutil.boot_time()),
        }


_SAMPLER: MetricsSampler | None = None


def get_sampler() -> MetricsSampler:
    """One shared sampler for the dashboard and the alert monitor."""
    global _SAMPLER
    if _SAMPLER is None:
        _SAMPLER = MetricsSampler()
    return _SAMPLER


class DashboardServer:
    def __init__(self, signals, token: str, host: str = "127.0.0.1", port: int = 8765, allow_lan: bool = False, monitor=None):
        self.signals = signals
        self.token = token
        self.host = host
        self.port = int(port)
        self.allow_lan = allow_lan
        self.sampler = get_sampler()
        self.monitor = monitor
        self.app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)
        self._server: uvicorn.Server | None = None
        self._setup()

    # ------------------------------------------------------------------ data helpers
    def _setting(self, key, default=None):
        try:
            value = self.signals.configuration_settings.get_main_setting(key)
            return default if value is None else value
        except Exception:
            return default

    def _llm_method(self) -> str:
        try:
            from app.utils.runtime_stats import stats
            method = stats.llm_info.get("method") or ""
        except Exception:
            method = ""
        if method:
            return method
        value = str(self._setting("conversation_method", "") or "")
        return "" if value.isdigit() else value

    def _tts_info(self) -> dict:
        """Speech engine that is selected for the character currently open in the app."""
        s = self.signals
        try:
            name = getattr(s, "current_active_character", None)
            data = s.configuration_characters.load_configuration().get("character_list", {}).get(name, {}) if name else {}
        except Exception:
            data = {}
        engine = str(data.get("current_text_to_speech") or "")
        if engine in ("", "Nothing", "None"):
            return {"engine": "", "detail": ""}
        parts = []
        if engine == "Qwen-3 TTS":
            parts += [str(data.get("qwen_model_size", "1.7B")), str(data.get("qwen_mode", "presets"))]
            if data.get("qwen_mode", "presets") == "presets" and data.get("voice_type"):
                parts.append(str(data.get("voice_type")))
        elif data.get("voice_type"):
            parts.append(str(data.get("voice_type")))
        if data.get("rvc_enabled") and data.get("rvc_file"):
            parts.append("RVC")
        return {"engine": engine, "detail": " · ".join(p for p in parts if p)}

    def _status(self) -> dict:
        s = self.signals
        tools = []
        try:
            tools = s.tool_registry.tool_names()
        except Exception:
            pass
        try:
            from app.utils.branding import app_name
            name = app_name()
        except Exception:
            name = "Yume Companion"
        lang = "de" if int(self._setting("program_language", 0) or 0) == 2 else "en"
        return {
            "app": name, "version": _read_version(), "lang": lang,
            "character": getattr(s, "current_active_character", None) or "",
            "tools_enabled": bool(getattr(s, "tools_enabled", False)), "tools": tools,
            "llm_method": self._llm_method(),
            "tts": self._tts_info(),
            "local_llm": str(self._setting("local_llm", "")),
            "vision": bool(self._setting("vision_enabled", False)),
            "android_server": bool(getattr(s, "web_server_running", False)),
            "android_port": int(self._setting("web_server_port", 8000) or 8000),
            "dashboard_port": self.port, "lan": self.allow_lan,
            "config": {k: self._setting(k) for k in (
                "context_size", "max_tokens", "gpu_layers", "temperature", "llm_batch_size", "cpu_threads",
                "flash_attention_status", "tts_device", "whisper_device", "vision_device", "vision_model_id")},
        }

    @staticmethod
    def _log_tail(n: int) -> list[str]:
        logs = sorted((APP_ROOT / "logs").glob("sow_*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
        if not logs:
            return []
        try:
            with open(logs[0], "rb") as fh:
                fh.seek(0, os.SEEK_END)
                size = fh.tell()
                fh.seek(max(0, size - 64 * 1024))
                text = fh.read().decode("utf-8", errors="replace")
        except OSError:
            return []
        return [_mask(line) for line in text.splitlines()[-n:]]

    # ------------------------------------------------------------------ http
    def _setup(self):
        app = self.app

        @app.middleware("http")
        async def guard(request: Request, call_next):
            raw_host = (request.headers.get("host") or "").strip().lower()
            if raw_host.startswith("[") and "]" in raw_host:
                host = raw_host[1:raw_host.index("]")]
            else:
                host = raw_host.rsplit(":", 1)[0] if raw_host.count(":") == 1 else raw_host
            if host not in ("localhost", "127.0.0.1", "::1", ""):
                try:
                    ipaddress.ip_address(host)
                except ValueError:
                    return PlainTextResponse("Forbidden host", status_code=400)
                if not self.allow_lan:
                    return PlainTextResponse("LAN access is disabled", status_code=403)
            supplied = request.headers.get("X-Dashboard-Token") or request.query_params.get("token") \
                or request.cookies.get("yume_dash") or ""
            if not supplied or not secrets.compare_digest(supplied, self.token):
                return PlainTextResponse("Unauthorized - open the link from Yume Companion > Settings > Dashboard.",
                                         status_code=401)
            response = await call_next(request)
            if request.query_params.get("token"):
                response.set_cookie("yume_dash", self.token, httponly=True, samesite="strict", max_age=86400 * 30)
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            return response

        @app.get("/", response_class=HTMLResponse)
        async def index():
            return HTMLResponse(DASHBOARD_HTML)

        @app.get("/api/metrics")
        async def metrics():
            return JSONResponse({"now": self.sampler.latest, "history": list(self.sampler.history)})

        @app.get("/api/toollog")
        async def toollog_endpoint(n: int = 12):
            from app.utils import tool_log
            return JSONResponse({"entries": await asyncio.to_thread(tool_log.read, max(1, min(n, 60)))})

        @app.get("/api/alerts")
        async def alerts_endpoint():
            if self.monitor is None:
                return JSONResponse({"enabled": False, "active": [], "history": []})
            return JSONResponse({"enabled": True, **self.monitor.snapshot()})

        @app.get("/api/stats")
        async def stats_endpoint():
            from app.utils.runtime_stats import stats
            return JSONResponse(stats.snapshot())

        @app.get("/api/extra")
        async def extra_endpoint():
            from app.utils import dashboard_extra
            return JSONResponse(await asyncio.to_thread(dashboard_extra.collect, self.signals))

        @app.post("/api/spotify/control")
        async def spotify_control_endpoint(request: Request):
            from app.utils import spotify_pc
            body = await request.json()
            ok, message = await asyncio.to_thread(spotify_pc.control, str(body.get("action", "")), body.get("value"))
            return JSONResponse({"ok": ok, "message": message})

        @app.get("/api/selftest")
        async def selftest_endpoint():
            from app.utils import selftest
            results = await asyncio.to_thread(selftest.run_all, self.signals)
            return JSONResponse({"results": results, "summary": selftest.summary(results)})

        @app.get("/api/status")
        async def status():
            return JSONResponse(self._status())

        @app.get("/api/logs")
        async def logs(n: int = 80):
            return JSONResponse({"lines": await asyncio.to_thread(self._log_tail, max(10, min(n, 300)))})

    # ------------------------------------------------------------------ lifecycle
    def start_in_thread(self):
        """Serve in a private thread with its own event loop (no interaction with the Qt loop, always stoppable)."""
        self.sampler.acquire()
        config = uvicorn.Config(self.app, host=self.host, port=self.port, log_level="warning")
        self._server = uvicorn.Server(config)
        self.error = None

        def run():
            try:
                self._server.run()
            except BaseException as exc:                    # report, never crash the app
                self.error = exc
                logger.error("Dashboard server stopped: %s", exc)
        self._thread = threading.Thread(target=run, name="YumeDashboard", daemon=True)
        self._thread.start()

    def is_running(self) -> bool:
        return getattr(self, "_thread", None) is not None and self._thread.is_alive()

    def stop_thread(self, timeout: float = 5.0):
        if self._server is not None:
            self._server.should_exit = True
        th = getattr(self, "_thread", None)
        if th is not None:
            th.join(timeout)
            if th.is_alive():                               # last resort: stop immediately
                self._server.force_exit = True
                th.join(2.0)
        self._thread = None
        self.sampler._users = max(0, self.sampler._users - 1)
        if self.sampler._users == 0:
            self.sampler._stop_sync()


DASHBOARD_HTML = r"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Yume Dashboard</title>
<style>
:root{--bg:#15101f;--panel:#1f1830;--panel2:#271f3a;--line:rgba(255,160,210,.16);--pink:#ff8fc7;--pink2:#ffc2e2;--lav:#b69cff;
--text:#f3ecf7;--muted:#a99cbd;--ok:#6ee7a0;--warn:#fbbf24;--bad:#f87171}
@media (prefers-color-scheme:light){:root{--bg:#fff4fa;--panel:#ffffff;--panel2:#fdeaf4;--line:rgba(200,80,150,.2);--text:#35223f;--muted:#7d6a8a}}
*{box-sizing:border-box}body{margin:0;background:radial-gradient(1200px 600px at 80% -10%,rgba(255,143,199,.14),transparent),
radial-gradient(900px 500px at -10% 110%,rgba(182,156,255,.14),transparent),var(--bg);color:var(--text);
font-family:"Segoe UI",system-ui,sans-serif;min-height:100vh}
header{display:flex;align-items:center;gap:14px;padding:18px 28px;border-bottom:1px solid var(--line);flex-wrap:wrap}
header h1{margin:0;font-size:20px;letter-spacing:.3px}header h1 span{color:var(--pink)}
.pill{padding:4px 12px;border-radius:999px;background:var(--panel2);border:1px solid var(--line);font-size:12px;color:var(--muted)}
.pill b{color:var(--text)}.dot{display:inline-block;width:8px;height:8px;border-radius:50%;background:var(--ok);margin-right:6px}
.dot.off{background:var(--muted)}main{padding:22px 28px;display:grid;gap:16px;grid-template-columns:repeat(12,1fr);max-width:1500px;margin:auto}
.card{background:var(--panel);border:1px solid var(--line);border-radius:18px;padding:16px 18px;grid-column:span 4;position:relative;overflow:hidden}
.card.w6{grid-column:span 6}.card.w8{grid-column:span 8}.card.w12{grid-column:span 12}
@media(max-width:1000px){.card,.card.w6,.card.w8{grid-column:span 12}}
.card h2{margin:0 0 10px;font-size:12px;letter-spacing:1.4px;text-transform:uppercase;color:var(--lav);font-weight:600}
.big{font-size:34px;font-weight:700;line-height:1}.big small{font-size:14px;color:var(--muted);font-weight:500;margin-left:4px}
.sub{color:var(--muted);font-size:12px;margin-top:4px}
.bar{height:8px;background:var(--panel2);border-radius:6px;margin-top:10px;overflow:hidden}
.bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--pink),var(--lav));border-radius:6px;transition:width .6s}
canvas{width:100%;height:70px;display:block;margin-top:10px}
table{width:100%;border-collapse:collapse;font-size:13px}th{color:var(--muted);text-align:left;font-weight:500;padding:4px 6px}
td{padding:5px 6px;border-top:1px solid var(--line)}td.r,th.r{text-align:right}
.tags{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}.tag{font-size:11px;padding:3px 9px;border-radius:999px;background:rgba(255,143,199,.12);
border:1px solid rgba(255,143,199,.3);color:var(--pink2)}
button{background:var(--panel2);color:var(--pink2);border:1px solid var(--line);border-radius:8px;padding:6px 16px;cursor:pointer;font-size:15px}button:hover{border-color:var(--pink)}
pre{margin:0;max-height:280px;overflow:auto;font:12px/1.5 Consolas,monospace;color:var(--muted);white-space:pre-wrap;word-break:break-all}
.kv{display:grid;grid-template-columns:auto 1fr;gap:6px 14px;font-size:13px}.kv span:nth-child(odd){color:var(--muted)}
.cores{display:grid;grid-template-columns:repeat(auto-fill,minmax(26px,1fr));gap:4px;margin-top:10px}
.core{height:28px;border-radius:5px;background:var(--panel2);position:relative;overflow:hidden}.core i{position:absolute;bottom:0;left:0;right:0;
background:linear-gradient(0deg,var(--pink),var(--lav));opacity:.85;transition:height .6s}
#alertbar.on,#srvbar.on{display:flex!important}.alert{padding:6px 14px;border-radius:999px;font-size:13px;border:1px solid}
.alert.warning{background:rgba(251,191,36,.12);border-color:rgba(251,191,36,.5);color:#fde68a}
.alert.critical{background:rgba(248,113,113,.14);border-color:rgba(248,113,113,.6);color:#fecaca;animation:blink 1.4s infinite}
@keyframes blink{50%{opacity:.55}}.hist{font:12px/1.7 Consolas,monospace;color:var(--muted)}
.petal{position:fixed;top:-20px;width:10px;height:14px;background:rgba(255,160,210,.35);border-radius:70% 0 70% 0;pointer-events:none;
animation:fall linear infinite}@keyframes fall{to{transform:translateY(110vh) rotate(360deg)}}
</style></head><body>
<header><h1><span id="app">Yume</span> Dashboard</h1><span class="pill"><span class="dot" id="live"></span><b id="ver">-</b></span>
<span class="pill" id="char"></span><span class="pill" id="upd"></span></header>
<div id="alertbar" style="display:none;padding:10px 28px;gap:8px;flex-wrap:wrap"></div>
<div id="srvbar" style="display:none;padding:0 28px 10px;gap:8px;flex-wrap:wrap"></div>
<main>
 <div class="card"><h2 data-t="cpu">CPU</h2><div class="big"><span id="cpu">-</span><small>%</small></div><div class="sub" id="cpusub"></div>
  <div class="bar"><i id="cpubar"></i></div><canvas id="cpuc"></canvas></div>
 <div class="card"><h2 data-t="ram">RAM</h2><div class="big"><span id="ram">-</span><small>%</small></div><div class="sub" id="ramsub"></div>
  <div class="bar"><i id="rambar"></i></div><canvas id="ramc"></canvas></div>
 <div class="card"><h2 data-t="gpu">GPU</h2><div class="big"><span id="gpu">-</span><small>%</small></div><div class="sub" id="gpusub"></div>
  <div class="bar"><i id="gpubar"></i></div><canvas id="gpuc"></canvas></div>
 <div class="card w6"><h2><span data-t="llm_t">LLM</span> <span class="pill" id="llm_model" style="text-transform:none;letter-spacing:0"></span></h2>
  <div class="big"><span id="llm_tps">-</span><small data-t="tps">Tokens/s</small></div><div class="sub" id="llm_sub"></div>
  <canvas id="llmc"></canvas><div class="kv" id="llm_kv" style="margin-top:10px"></div></div>
 <div class="card w6"><h2 data-t="ctx_t">Kontext</h2>
  <div class="big"><span id="ctx_used">-</span><small id="ctx_max"></small></div><div class="sub" id="ctx_sub"></div>
  <div class="bar"><i id="ctx_bar"></i></div><div class="kv" id="ctx_kv" style="margin-top:12px"></div></div>
 <div class="card"><h2 data-t="tts_t">TTS</h2><div class="big"><span id="tts_main">-</span><small id="tts_unit"></small></div><div class="sub" id="tts_sub"></div>
  <div class="kv" id="tts_kv" style="margin-top:10px"></div></div>
 <div class="card"><h2 data-t="stt_t">STT (Whisper)</h2><div class="big"><span id="stt_main">-</span><small id="stt_unit"></small></div><div class="sub" id="stt_sub"></div>
  <div class="kv" id="stt_kv" style="margin-top:10px"></div></div>
 <div class="card"><h2 data-t="vis_t">Vision</h2><div class="big"><span id="vis_main">-</span><small id="vis_unit"></small></div><div class="sub" id="vis_sub"></div>
  <div class="kv" id="vis_kv" style="margin-top:10px"></div></div>
 <div class="card w6"><h2 data-t="cores">CPU-Kerne</h2><div class="cores" id="cores"></div>
  <div class="sub" id="net" style="margin-top:12px"></div></div>
 <div class="card w6"><h2 data-t="app">Yume Companion</h2><div class="kv" id="appkv"></div></div>
 <div class="card w6"><h2 data-t="services">Dienste</h2><div class="kv" id="svc"></div><div class="tags" id="tools"></div></div>
 <div class="card w6"><h2 data-t="procs">Prozesse (App + Kinder)</h2><table><thead><tr><th>Name</th><th class="r">CPU</th><th class="r">RAM</th><th class="r">Threads</th></tr></thead><tbody id="procs"></tbody></table></div>
 <div class="card w12"><h2 data-t="st_t">Selbsttest</h2><div style="display:flex;gap:10px;align-items:center"><button onclick="runSelfTest()">Selbsttest starten</button><span class="sub" id="st_sum"></span></div><div class="hist" id="st_res" style="margin-top:10px"></div></div>
 <div class="card w12"><h2 data-t="srv_t">LLM-Server</h2><table><thead><tr><th>Dienst</th><th>Modell</th><th class="r">Kontext/Slot</th><th class="r">Slots (aktiv)</th><th>Status</th></tr></thead><tbody id="srv"></tbody></table><div class="sub" id="srvwarn" style="color:#fde68a"></div></div>
 <div class="card w6"><h2 data-t="tm_t">Werkzeug-Modelle (lokal)</h2><div class="hist" id="tm">-</div></div>
 <div class="card w6"><h2 data-t="phone_t">Handy</h2><div class="kv" id="phonekv"></div><div class="hist" id="phoneact" style="margin-top:10px"></div></div>
 <div class="card w12"><h2 data-t="spot_t">Spotify</h2><div class="big" style="font-size:22px"><span id="sp_title">-</span></div><div class="sub" id="sp_sub"></div>
  <div class="bar"><i id="sp_bar"></i></div>
  <div style="display:flex;gap:8px;margin-top:12px"><button onclick="spc('previous')">⏮</button><button onclick="spc(window.SPPLAY?'pause':'resume')">⏯</button><button onclick="spc('next')">⏭</button></div></div>
 <div class="card w12"><h2 data-t="ts_t">Werkzeug-Statistik</h2><table><thead><tr><th>Werkzeug</th><th class="r">Aufrufe</th><th class="r">Fehler</th><th class="r">&Oslash; Dauer</th><th>Verlauf (letzte Aufrufe)</th></tr></thead><tbody id="tstats"></tbody></table></div>
 <div class="card w12"><h2 data-t="tools_t">Werkzeug-Aktionen</h2><div class="hist" id="toolhist">-</div></div>
 <div class="card w12"><h2 data-t="alerts_t">Alarme</h2><div class="hist" id="alerthist">-</div></div>
 <div class="card w12"><h2 data-t="log">Log</h2><pre id="log"></pre></div>
</main>
<script>
const T={de:{cpu:'CPU',ram:'RAM',gpu:'GPU',cores:'CPU-Kerne',app:'Yume Companion',services:'Dienste',procs:'Prozesse (App + Kinder)',log:'Log',
 uptime:'Laufzeit',mem:'Speicher',threads:'Threads',children:'Kindprozesse',llm:'KI-Methode',model:'Lokales Modell',tools:'Werkzeuge',vision:'Vision',
 android:'Android-Server',dash:'Dashboard-Port',on:'an',off:'aus',lan:'LAN-Zugriff',net:'Netzwerk',disk:'Laufwerk',free:'Kein NVIDIA-GPU erkannt',char:'Charakter',tools_t:'Werkzeug-Aktionen (zuletzt)',srv_t:'LLM-Server',st_t:'Selbsttest',ts_t:'Werkzeug-Statistik',tm_t:'Werkzeug-Modelle (lokal)',phone_t:'Handy',spot_t:'Spotify',notools:'Noch keine Werkzeug-Aktionen.',alerts_t:'Alarme (Verlauf)',noalerts:'Keine Alarme - alles im grünen Bereich.',llm_t:'LLM',tps:'Tokens/s',ctx_t:'Kontext',tts_t:'TTS (Sprachausgabe)',stt_t:'STT (Spracherkennung)',vis_t:'Vision',last:'Letzte Antwort',last_t:'Letzte Antwort',exact:'exakt (Server)',avg:'Ø (letzte 30)',ttft:'Zeit bis 1. Token',dur:'Dauer',req:'Anfragen',err:'Fehler',tin:'Tokens gesendet',tout:'Tokens erhalten',est:'geschätzt',prefill:'Prompt-Verarbeitung',busy:'läuft gerade',idle:'bereit',nodata:'noch keine Daten',used:'belegt',sys:'System-Prompt',mem:'Gedächtnis',lore:'Lorebooks',hist:'Verlauf',free2:'frei',engine:'Engine',chars:'Zeichen',rtf:'Echtzeitfaktor',gent:'Erzeugungszeit',audio:'Audiolänge',proc:'Verarbeitung',total:'Gesamt',secs:'Audio gesamt',cfg:'Konfiguration',ctxsize:'Kontextgröße',maxtok:'Max. Antwort',gpul:'GPU-Layer',temp:'Temperatur',batch:'Batch',flash:'FlashAttention',dev:'Gerät',yes:'ja',no:'nein'},
 en:{cpu:'CPU',ram:'RAM',gpu:'GPU',cores:'CPU cores',app:'Yume Companion',services:'Services',procs:'Processes (app + children)',log:'Log',
 uptime:'Uptime',mem:'Memory',threads:'Threads',children:'Child processes',llm:'AI method',model:'Local model',tools:'Tools',vision:'Vision',
 android:'Android server',dash:'Dashboard port',on:'on',off:'off',lan:'LAN access',net:'Network',disk:'Drive',free:'No NVIDIA GPU detected',char:'Character',tools_t:'Tool actions (latest)',srv_t:'LLM servers',st_t:'Self test',ts_t:'Tool statistics',tm_t:'Tool models (local)',phone_t:'Phone',spot_t:'Spotify',notools:'No tool actions yet.',alerts_t:'Alerts (history)',noalerts:'No alerts - everything looks fine.',llm_t:'LLM',tps:'tokens/s',ctx_t:'Context',tts_t:'TTS (speech output)',stt_t:'STT (speech input)',vis_t:'Vision',last:'Last reply',last_t:'Last reply',exact:'exact (server)',avg:'Avg (last 30)',ttft:'Time to 1st token',dur:'Duration',req:'Requests',err:'Errors',tin:'Tokens sent',tout:'Tokens received',est:'estimated',prefill:'Prompt processing',busy:'working',idle:'ready',nodata:'no data yet',used:'used',sys:'System prompt',mem:'Memory',lore:'Lorebooks',hist:'History',free2:'free',engine:'Engine',chars:'Characters',rtf:'Real-time factor',gent:'Generation time',audio:'Audio length',proc:'Processing',total:'Total',secs:'Audio total',cfg:'Configuration',ctxsize:'Context size',maxtok:'Max reply',gpul:'GPU layers',temp:'Temperature',batch:'Batch',flash:'FlashAttention',dev:'Device',yes:'yes',no:'no'}};
let L=T.en;const $=id=>document.getElementById(id);const esc=v=>String(v==null?'':v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const fmtB=b=>{if(b==null)return'-';const u=['B','KB','MB','GB','TB'];let i=0;while(b>=1024&&i<4){b/=1024;i++}return b.toFixed(i>1?1:0)+' '+u[i]};
const fmtT=s=>{const d=Math.floor(s/86400),h=Math.floor(s%86400/3600),m=Math.floor(s%3600/60);return(d?d+'d ':'')+h+'h '+m+'m'};
function spark(id,data,key){const c=$(id),r=devicePixelRatio||1,w=c.clientWidth,h=c.clientHeight;c.width=w*r;c.height=h*r;const x=c.getContext('2d');x.scale(r,r);
 const pts=data.map(d=>d[key]).filter(v=>v!=null);if(pts.length<2)return;const g=x.createLinearGradient(0,0,0,h);g.addColorStop(0,'rgba(255,143,199,.45)');g.addColorStop(1,'rgba(182,156,255,0)');
 x.beginPath();pts.forEach((v,i)=>{const px=i/(pts.length-1)*w,py=h-Math.min(v,100)/100*(h-4)-2;i?x.lineTo(px,py):x.moveTo(px,py)});
 x.strokeStyle='#ff8fc7';x.lineWidth=2;x.stroke();x.lineTo(w,h);x.lineTo(0,h);x.closePath();x.fillStyle=g;x.fill()}
function setBar(id,v){$(id).style.width=Math.max(0,Math.min(100,v||0))+'%'}
async function j(u){const r=await fetch(u,{cache:'no-store'});if(!r.ok)throw new Error(r.status);return r.json()}
async function tick(){try{const m=await j('/api/metrics'),n=m.now;if(!n||n.cpu==null){return}
 $('live').className='dot';$('cpu').textContent=n.cpu.toFixed(0);setBar('cpubar',n.cpu);$('cpusub').textContent=(n.cpu_freq?(n.cpu_freq/1000).toFixed(2)+' GHz · ':'')+n.cores.length+' threads';
 $('ram').textContent=n.ram.toFixed(0);setBar('rambar',n.ram);$('ramsub').textContent=fmtB(n.ram_used)+' / '+fmtB(n.ram_total);
 if(n.gpus&&n.gpus.length){const g=n.gpus[0];$('gpu').textContent=(g.util??0).toFixed(0);setBar('gpubar',g.util);
  $('gpusub').textContent=g.name+' · '+(g.mem_used/1024).toFixed(1)+'/'+(g.mem_total/1024).toFixed(1)+' GB · '+(g.temp??'-')+' °C'+(g.power?' · '+g.power.toFixed(0)+' W':'')}
 else{$('gpu').textContent='-';$('gpusub').textContent=L.free}
 $('cores').innerHTML=n.cores.map(c=>'<div class="core" title="'+c.toFixed(0)+'%"><i style="height:'+c+'%"></i></div>').join('');
 $('net').textContent=L.net+': ↓ '+fmtB(n.net_down)+'/s  ↑ '+fmtB(n.net_up)+'/s  ·  '+L.disk+': '+fmtB(n.disk.used)+' / '+fmtB(n.disk.total)+' ('+n.disk.percent+'%)';
 spark('cpuc',m.history,'cpu');spark('ramc',m.history,'ram');spark('gpuc',m.history,'gpu');
 const a=n.app;$('appkv').innerHTML='<span>'+L.uptime+'</span><span>'+fmtT(a.uptime)+'</span><span>CPU</span><span>'+a.cpu.toFixed(1)+' %</span><span>'+L.mem+'</span><span>'+fmtB(a.rss)+
  '</span><span>'+L.threads+'</span><span>'+a.threads+'</span><span>'+L.children+'</span><span>'+a.children+'</span>';
 $('procs').innerHTML=n.procs.map(p=>'<tr><td>'+esc(p.name)+'</td><td class="r">'+p.cpu.toFixed(1)+'%</td><td class="r">'+fmtB(p.rss)+'</td><td class="r">'+p.threads+'</td></tr>').join('')
}catch(e){$('live').className='dot off'}}
const kv=(a)=>a.map(x=>'<span>'+esc(x[0])+'</span><span>'+esc(x[1])+'</span>').join('');
const f1=(v,d=1)=>v==null?'-':Number(v).toFixed(d);const fN=n=>n==null?'-':(n>=1e6?(n/1e6).toFixed(2)+'M':n>=1e4?(n/1e3).toFixed(1)+'k':String(Math.round(n)));
const llmHist=[];
async function stat(){try{const s=await j('/api/stats'),l=s.llm,c=s.context,t=s.tts,r=s.stt,v=s.vision;
 $('llm_tps').textContent=f1(l.last&&l.last.tps);$('llm_model').textContent=((l.method&&l.method!=='0'?l.method+' · ':'')+(l.model||'')).slice(0,48)||'-';
 $('llm_sub').textContent=l.active?L.busy:(l.count?((l.last&&l.last.exact)?L.exact:L.est)+' · '+L.last_t:L.nodata);
 const hs=l.hist||[],mx=Math.max(1,...hs);spark('llmc',hs.map(v=>({v:100*v/mx})),'v');
 $('llm_kv').innerHTML=kv([[L.avg+' '+L.tps,f1(l.avg.tps)],[L.ttft,l.last&&l.last.ttft!=null?f1(l.last.ttft,2)+' s':'-'],[L.prefill,l.last&&l.last.prefill_tps?fN(l.last.prefill_tps)+' tok/s':'-'],
  [L.last,l.last?fN(l.last.in)+' → '+fN(l.last.out)+' tok · '+f1(l.last.dur)+' s':'-'],[L.tin,fN(l.total_in)],[L.tout,fN(l.total_out)],[L.req,l.count],[L.err,l.errors]]);
 const pct=c.max?100*c.used/c.max:0;$('ctx_used').textContent=fN(c.used);$('ctx_max').textContent='/ '+fN(c.max)+' tok';setBar('ctx_bar',pct);
 $('ctx_sub').textContent=c.max?pct.toFixed(0)+' % '+L.used+(c.character?' · '+c.character:''):L.nodata;
 const b=c.breakdown||{};$('ctx_kv').innerHTML=kv([[L.sys,fN(b.system)],[L.mem,fN(b.memory)],[L.lore,fN(b.lore)],[L.hist,fN(b.history)],[L.free2,fN(Math.max(0,c.max-c.used))]]);
 const tl=t.last;$('tts_main').textContent=tl?f1(tl.rtf,2):'-';$('tts_unit').textContent=tl?'× RTF':'';{const st=(window.ST&&window.ST.tts)||{};const eng=st.engine?(st.engine+(st.detail?' · '+st.detail:'')):'-';$('tts_sub').textContent=eng+(tl?'':' · '+L.nodata)+(tl&&st.engine&&tl.engine&&tl.engine!==st.engine?' ('+tl.engine+')':'');}
 $('tts_kv').innerHTML=kv([[L.gent,tl?f1(tl.gen,2)+' s':'-'],[L.audio,tl&&tl.audio?f1(tl.audio,1)+' s':'-'],[L.avg+' RTF',f1(t.avg.rtf,2)],[L.chars,fN(t.total_chars)],[L.secs,f1(t.total_audio,1)+' s'],[L.req,t.count],[L.err,t.errors]]);
 const rl=r.last;$('stt_main').textContent=rl?f1(rl.rtf,2):'-';$('stt_unit').textContent=rl?'× RTF':'';$('stt_sub').textContent=rl?'':L.nodata;
 $('stt_kv').innerHTML=kv([[L.proc,rl?f1(rl.proc,2)+' s':'-'],[L.audio,rl?f1(rl.audio,1)+' s':'-'],[L.secs,f1(r.total_audio,0)+' s'],[L.req,r.count],[L.err,r.errors]]);
 const vl=v.last;$('vis_main').textContent=vl?f1(vl.tps):'-';$('vis_unit').textContent=vl?L.tps:'';$('vis_sub').textContent=vl?'':L.nodata;
 $('vis_kv').innerHTML=kv([[L.dur,vl?f1(vl.dur,1)+' s':'-'],[L.tin,fN(v.total_in)],[L.tout,fN(v.total_out)],[L.req,v.count],[L.err,v.errors]])
}catch(e){}}
async function alerts(){try{const a=await j('/api/alerts');const bar=$('alertbar');
 bar.innerHTML=a.active.map(x=>'<span class="alert '+esc(x.level)+'">'+(x.level==='critical'?'⛔ ':'⚠ ')+esc(x.message)+'</span>').join('');bar.className=a.active.length?'on':'';
 const fmt=t=>new Date(t*1000).toLocaleTimeString();const ico={start:'▶',end:'✔',escalate:'⬆'};
 $('alerthist').innerHTML=a.history.length?a.history.slice(0,25).map(h=>fmt(h.t)+'  '+(ico[h.event]||'')+'  '+esc(h.message)).join('<br>'):esc(L.noalerts)}catch(e){}}
async function toolsLog(){try{const r=await j('/api/toollog?n=12');const st={declined:'⛔',approved:'✔',not_needed:'•'};
 $('toolhist').innerHTML=r.entries.length?r.entries.map(e=>esc(e.t.replace('T',' ').slice(5))+'  '+(st[e.approval]||'')+' '+(e.success?'':'⚠ ')+'<b>'+esc(e.tool)+'</b>  '+esc((e.args||'').slice(0,90))).join('<br>'):esc(L.notools)}catch(e){}}
async function slow(){try{const s=await j('/api/status');L=T[s.lang]||T.en;window.ST=s;document.querySelectorAll('[data-t]').forEach(e=>e.textContent=L[e.dataset.t]);
 $('app').textContent=s.app;$('ver').textContent='v'+s.version.replace(/^v/,'');$('char').innerHTML=L.char+': <b>'+esc(s.character||'-')+'</b>';document.title=s.app+' Dashboard';
 const on=v=>v?L.on:L.off;$('svc').innerHTML='<span>'+L.llm+'</span><span>'+esc(s.llm_method||'-')+'</span><span>'+L.model+'</span><span>'+esc(s.local_llm||'-')+'</span><span>TTS</span><span>'+esc((s.tts&&s.tts.engine)?(s.tts.engine+(s.tts.detail?' · '+s.tts.detail:'')):'-')+'</span><span>'+L.tools+
  '</span><span>'+on(s.tools_enabled)+'</span><span>'+L.vision+'</span><span>'+on(s.vision)+'</span><span>'+L.android+'</span><span>'+on(s.android_server)+' (:'+s.android_port+')</span><span>'+L.dash+'</span><span>:'+s.dashboard_port+' · '+L.lan+' '+on(s.lan)+'</span>'+kv([[L.ctxsize,s.config.context_size],[L.maxtok,s.config.max_tokens],[L.gpul,s.config.gpu_layers],[L.temp,s.config.temperature],[L.batch,s.config.llm_batch_size],[L.flash,s.config.flash_attention_status?L.yes:L.no],['TTS '+L.dev,s.config.tts_device],['STT '+L.dev,s.config.whisper_device]]);
 $('tools').innerHTML=s.tools.map(t=>'<span class="tag">'+esc(t)+'</span>').join('');
 const l=await j('/api/logs?n=60');const p=$('log');const bottom=p.scrollTop+p.clientHeight>=p.scrollHeight-20;p.textContent=l.lines.join('\n');if(bottom)p.scrollTop=p.scrollHeight}catch(e){}}
async function extra(){try{const x=await j('/api/extra');
 $('srv').innerHTML=x.servers.length?x.servers.map(s=>'<tr><td>'+esc(s.name)+'</td><td>'+esc(s.model||'-')+'</td><td class="r">'+(s.n_ctx||'-')+'</td><td class="r">'+(s.slots||'-')+(s.busy!=null?' ('+s.busy+')':'')+'</td><td>'+(s.ok?'🟢 ':'🔴 ')+esc(s.ok?'ok':'aus')+'</td></tr>').join(''):'<tr><td colspan=5>Kein Remote-LLM-Server eingestellt.</td></tr>';
 $('srvwarn').innerHTML=x.servers.filter(s=>s.warn).map(s=>'⚠ '+esc(s.name)+': '+esc(s.warn)).join('<br>');
 $('tm').innerHTML=x.tool_models.length?x.tool_models.map(m=>(m.active?'● ':'○ ')+'<b>'+esc(m.name)+'</b>  '+m.size_gb+' GB · GPU '+esc(m.gpu)).join('<br>'):'Keine Werkzeug-Modelle heruntergeladen.';
 const tsd=x.tool_stats||[];$('tstats').innerHTML=tsd.length?tsd.map(s=>{const mx=Math.max(0.1,...s.last);return '<tr><td>'+esc(s.tool)+'</td><td class="r">'+s.n+'</td><td class="r"'+(s.fail?' style="color:#fecaca"':'')+'>'+s.fail+'</td><td class="r">'+s.avg.toFixed(2)+' s</td><td><span style="letter-spacing:1px;color:var(--pink2)">'+s.last.map(v=>'▁▂▃▄▅▆▇█'[Math.min(7,Math.floor(v/mx*7.99))]).join('')+'</span></td></tr>'}).join(''):'<tr><td colspan=5>Noch keine Werkzeug-Aufrufe.</td></tr>';
 $('srvbar').innerHTML=x.servers.filter(s=>s.warn).map(s=>'<span class="alert critical">⚠ '+esc(s.name)+': '+esc(s.warn)+'</span>').join('');$('srvbar').className=x.servers.some(s=>s.warn)?'on':'';
 const p=x.phone;$('phonekv').innerHTML=kv([['Status',p.connected?'🟢 verbunden':'⚪ nicht verbunden']].concat(p.devices.map(d=>[d.name,d.ago<90?'gerade aktiv':'vor '+Math.round(d.ago/60)+' min'])));
 $('phoneact').innerHTML=p.actions.length?p.actions.map(a=>esc(a.t.replace('T',' ').slice(5))+'  '+(a.ok?'✔':'⚠')+' '+esc(a.args.slice(0,60))+' → '+esc(a.result)).join('<br>'):'Noch keine Handy-Aktionen.';
 const s=x.spotify;window.SPPLAY=!!s.playing;
 if(!s.connected){$('sp_title').textContent='Nicht verbunden';$('sp_sub').textContent='Einstellungen > Spotify';setBar('sp_bar',0)}
 else{$('sp_title').textContent=s.title?s.title+' – '+(s.artist||''):(s.error||'Es läuft nichts');$('sp_sub').textContent=(s.playing?'▶ ':'⏸ ')+(s.device||'')+(s.volume!=null?' · '+s.volume+' %':'');setBar('sp_bar',s.duration_ms?100*s.progress_ms/s.duration_ms:0)}
}catch(e){}}
async function runSelfTest(){$('st_sum').textContent='Prüfe …';$('st_res').innerHTML='';try{const r=await j('/api/selftest');const ic={ok:'🟢',warn:'🟡',fail:'🔴',off:'⚪'};
 $('st_sum').textContent=r.summary;$('st_res').innerHTML=r.results.map(x=>(ic[x.state]||'')+' <b>'+esc(x.name)+'</b> – '+esc(x.detail)).join('<br>')}catch(e){$('st_sum').textContent='Selbsttest nicht möglich'}}
async function spc(a){try{await fetch('/api/spotify/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a})});setTimeout(extra,600)}catch(e){}}
for(let i=0;i<8;i++){const p=document.createElement('div');p.className='petal';p.style.left=Math.random()*100+'vw';p.style.animationDuration=(14+Math.random()*14)+'s';p.style.animationDelay=(-Math.random()*20)+'s';document.body.appendChild(p)}
tick();stat();slow();alerts();setInterval(tick,2000);setInterval(stat,2000);setInterval(slow,6000);setInterval(alerts,3000);toolsLog();setInterval(toolsLog,5000);extra();setInterval(extra,4000);
</script></body></html>"""
