"""Performance alerts (VRAM, RAM, CPU, GPU temperature, context size, slow LLM/TTS/STT, low disk space).

Runs inside the app (not only while the dashboard is open): the dashboard shows the alerts, the app shows toasts.
"""
from __future__ import annotations

import asyncio
import collections
import logging
import time

logger = logging.getLogger("Alerts")

DEFAULTS = {"vram": 92, "ram": 90, "context": 85, "temp": 85, "cpu": 95}
CRITICAL_BUMP = {"vram": 97, "ram": 96, "context": 95, "temp": 92, "cpu": 99}
COOLDOWN_SECONDS = 300

TEXT = {
    "de": {
        "vram": "Grafikspeicher fast voll ({v:.0f} %)", "ram": "Arbeitsspeicher fast voll ({v:.0f} %)",
        "context": "Kontext fast voll ({v:.0f} %) - ältere Nachrichten fallen bald raus", "temp": "GPU sehr heiß ({v:.0f} °C)",
        "cpu": "CPU dauerhaft ausgelastet ({v:.0f} %)", "disk": "Wenig Speicherplatz frei ({v:.1f} GB)",
        "llm_slow": "KI antwortet langsam ({v:.1f} Tokens/s)", "llm_ttft": "KI braucht lange bis zum ersten Token ({v:.1f} s)",
        "tts_slow": "Sprachausgabe langsamer als Echtzeit (RTF {v:.2f})", "stt_slow": "Spracherkennung langsamer als Echtzeit (RTF {v:.2f})",
        "errors": "Fehler bei {what}", "title": "Yume Alarm",
        "backup_none": "Es gibt noch kein Backup deiner Daten", "backup_old": "Das letzte Backup ist {v:.0f} Tage alt",
    },
    "en": {
        "vram": "GPU memory almost full ({v:.0f} %)", "ram": "System memory almost full ({v:.0f} %)",
        "context": "Context almost full ({v:.0f} %) - older messages will drop out soon", "temp": "GPU very hot ({v:.0f} °C)",
        "cpu": "CPU constantly busy ({v:.0f} %)", "disk": "Low disk space ({v:.1f} GB free)",
        "llm_slow": "AI replies slowly ({v:.1f} tokens/s)", "llm_ttft": "AI takes long to the first token ({v:.1f} s)",
        "tts_slow": "Speech output slower than real time (RTF {v:.2f})", "stt_slow": "Speech input slower than real time (RTF {v:.2f})",
        "errors": "Errors in {what}", "title": "Yume alert",
        "backup_none": "There is no backup of your data yet", "backup_old": "The last backup is {v:.0f} days old",
    },
}


_backup_cache = {"t": 0.0, "age": None}


def latest_backup_age_days(root) -> float | None:
    """Age in days of the newest backup file (.yumepack / .sowpack / .zip in Backups, .soul_stage/backups, ...) or None when there is none."""
    now = time.time()
    if now - _backup_cache["t"] < 600:
        return _backup_cache["age"]
    newest = 0.0
    try:
        from pathlib import Path
        root = Path(root)
        for folder in (root / "Backups", root / "backups", root / ".soul_stage" / "backups", root / "app" / "data" / "backups"):
            if folder.is_dir():
                for f in folder.rglob("*"):
                    if f.is_file() and f.suffix.lower() in (".yumepack", ".sowpack", ".zip", ".sowbackup"):
                        newest = max(newest, f.stat().st_mtime)
    except Exception:
        logger.debug("backup age check failed", exc_info=True)
    _backup_cache.update(t=now, age=((now - newest) / 86400.0) if newest else None)
    return _backup_cache["age"]


class AlertMonitor:
    def __init__(self, settings_getter, notify=None):
        """settings_getter(key, default) -> value; notify(level, title, text) is called for new/escalated alerts."""
        self._get = settings_getter
        self._notify = notify
        self.active: dict[str, dict] = {}
        self.history = collections.deque(maxlen=60)
        self._cpu_high_since = None
        self._last_errors = {"llm": 0, "tts": 0, "stt": 0, "vision": 0}
        self._last_notified: dict[str, float] = {}
        self._task: asyncio.Task | None = None
        self._sampler = None

    # ------------------------------------------------------------------ lifecycle
    def start(self):
        if self._task is None or self._task.done():
            from app.utils.dashboard_server import get_sampler
            self._sampler = get_sampler()
            self._sampler.acquire()
            self._task = asyncio.ensure_future(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass
            self._task = None
        if self._sampler is not None:
            await self._sampler.release()
            self._sampler = None
        self.active.clear()

    async def _loop(self):
        await asyncio.sleep(8)
        while True:
            try:
                self.evaluate()
            except Exception as exc:
                logger.debug("alert evaluation failed: %s", exc)
            await asyncio.sleep(4)

    # ------------------------------------------------------------------ rules
    def _limit(self, key):
        try:
            return float(self._get(f"alert_{key}", DEFAULTS[key]) or DEFAULTS[key])
        except (TypeError, ValueError):
            return float(DEFAULTS[key])

    def _lang(self):
        try:
            return "de" if int(self._get("program_language", 0) or 0) == 2 else "en"
        except (TypeError, ValueError):
            return "en"

    def evaluate(self):
        from app.utils.runtime_stats import stats
        now = time.time()
        txt = TEXT[self._lang()]
        found: dict[str, tuple[str, str]] = {}  # key -> (level, message)

        def level_for(key, value):
            warn = self._limit(key)
            crit = max(CRITICAL_BUMP[key], warn + 3)
            return ("critical" if value >= crit else "warning") if value >= warn else None

        m = getattr(self._sampler, "latest", {}) or {}
        if m:
            gpus = m.get("gpus") or []
            if gpus and gpus[0].get("mem_total"):
                pct = 100.0 * (gpus[0].get("mem_used") or 0) / gpus[0]["mem_total"]
                lvl = level_for("vram", pct)
                if lvl:
                    found["vram"] = (lvl, txt["vram"].format(v=pct))
            for g in gpus:
                if g.get("temp") is not None:
                    lvl = level_for("temp", g["temp"])
                    if lvl:
                        found["temp"] = (lvl, txt["temp"].format(v=g["temp"]))
                        break
            lvl = level_for("ram", m.get("ram", 0))
            if lvl:
                found["ram"] = (lvl, txt["ram"].format(v=m["ram"]))
            cpu = m.get("cpu", 0)
            if level_for("cpu", cpu):
                self._cpu_high_since = self._cpu_high_since or now
                if now - self._cpu_high_since > 30:
                    found["cpu"] = (level_for("cpu", cpu), txt["cpu"].format(v=cpu))
            else:
                self._cpu_high_since = None
            free_gb = (m.get("disk", {}).get("total", 0) - m.get("disk", {}).get("used", 0)) / 1024 ** 3
            if m.get("disk", {}).get("total") and free_gb < 5:
                found["disk"] = ("critical" if free_gb < 2 else "warning", txt["disk"].format(v=free_gb))

        # backup watchdog: no backup for a long time (setting alert_backup_days, 0 = off)
        try:
            days_limit = float(self._get("alert_backup_days", 14) or 0)
        except (TypeError, ValueError):
            days_limit = 14.0
        if days_limit > 0:
            from pathlib import Path as _P
            age = latest_backup_age_days(_P(__file__).resolve().parents[2])
            if age is None:
                found["backup"] = ("warning", txt["backup_none"])
            elif age > days_limit:
                found["backup"] = ("warning", txt["backup_old"].format(v=age))

        s = stats.snapshot()
        ctx = s["context"]
        if ctx.get("max"):
            lvl = level_for("context", 100.0 * ctx["used"] / ctx["max"])
            if lvl:
                found["context"] = (lvl, txt["context"].format(v=100.0 * ctx["used"] / ctx["max"]))
        last = s["llm"].get("last")
        if last and now - last["t"] < 120:
            if last.get("tps") is not None and last["out"] >= 40 and last["tps"] < 3:
                found["llm_slow"] = ("warning", txt["llm_slow"].format(v=last["tps"]))
            if last.get("ttft") and last["ttft"] > 8:
                found["llm_ttft"] = ("warning", txt["llm_ttft"].format(v=last["ttft"]))
        tl = s["tts"].get("last")
        if tl and now - tl["t"] < 180 and tl.get("rtf") and tl["rtf"] > 1.5:
            found["tts_slow"] = ("warning", txt["tts_slow"].format(v=tl["rtf"]))
        rl = s["stt"].get("last")
        if rl and now - rl["t"] < 180 and rl.get("rtf") and rl["rtf"] > 1.0:
            found["stt_slow"] = ("warning", txt["stt_slow"].format(v=rl["rtf"]))
        for name, label in (("llm", "LLM"), ("tts", "TTS"), ("stt", "STT"), ("vision", "Vision")):
            errs = s[name]["errors"]
            if errs > self._last_errors[name]:
                found[f"err_{name}"] = ("warning", txt["errors"].format(what=label))
                self._last_errors[name] = errs
                self._last_notified.pop(f"err_{name}", None)
            elif f"err_{name}" in self.active and now - self.active[f"err_{name}"]["since"] < 120:
                found[f"err_{name}"] = self.active[f"err_{name}"]["level"], self.active[f"err_{name}"]["message"]

        # state transitions
        for key, (level, message) in found.items():
            prev = self.active.get(key)
            if prev is None:
                self.active[key] = {"key": key, "level": level, "message": message, "since": now}
                self.history.appendleft({"t": now, "event": "start", "key": key, "level": level, "message": message})
                self._maybe_notify(key, level, message, now)
            else:
                escalated = prev["level"] == "warning" and level == "critical"
                prev.update(level=level, message=message)
                if escalated:
                    self.history.appendleft({"t": now, "event": "escalate", "key": key, "level": level, "message": message})
                    self._maybe_notify(key, level, message, now, force=True)
        for key in list(self.active):
            if key not in found:
                gone = self.active.pop(key)
                self.history.appendleft({"t": now, "event": "end", "key": key, "level": gone["level"], "message": gone["message"]})

    def _maybe_notify(self, key, level, message, now, force=False):
        if self._notify is None:
            return
        if not force and now - self._last_notified.get(key, 0) < COOLDOWN_SECONDS:
            return
        self._last_notified[key] = now
        try:
            self._notify(level, TEXT[self._lang()]["title"], message)
        except Exception:
            logger.debug("alert notification failed", exc_info=True)

    def snapshot(self) -> dict:
        return {
            "active": sorted(self.active.values(), key=lambda a: (a["level"] != "critical", a["since"])),
            "history": list(self.history),
        }
