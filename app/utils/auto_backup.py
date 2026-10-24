"""Automatic profile backups: a .yumepack with the essential data every N days, the newest K are kept.

Contents: characters & chats, settings/personas/presets/lorebooks, soul memory, Soul Stage. Never API keys or big assets.
"""
from __future__ import annotations

import asyncio
import datetime
import logging
import os
import time
from pathlib import Path

logger = logging.getLogger("AutoBackup")

GROUPS = ["characters", "user_data", "soul_memory", "soul_stage"]
PREFIX = "Yume_AutoBackup_"


def auto_dir(root: str | None = None) -> Path:
    return Path(root or os.getcwd()) / "Backups" / "auto"


def list_backups(root: str | None = None) -> list[Path]:
    d = auto_dir(root)
    if not d.is_dir():
        return []
    files = list(d.glob(PREFIX + "*.yumepack")) + list(d.glob(PREFIX + "*.sowpack"))      # older ones (.sowpack) stay in the rotation
    return sorted(files, key=lambda p: p.stat().st_mtime, reverse=True)


def prune(keep: int, root: str | None = None) -> int:
    removed = 0
    for old in list_backups(root)[max(1, keep):]:
        try:
            old.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def create_now(root: str | None = None, app_version: str = "") -> Path | None:
    """Blocking. Returns the file or None when something went wrong."""
    from app.utils.profile_backup import ExportWorker
    root = root or os.getcwd()
    d = auto_dir(root)
    d.mkdir(parents=True, exist_ok=True)
    dest = d / f"{PREFIX}{datetime.datetime.now().strftime('%Y-%m-%d_%H%M')}.yumepack"
    result = {}
    worker = ExportWorker(str(dest), root, GROUPS, app_version)
    worker.finished_ok.connect(lambda p: result.update(ok=p))
    worker.failed.connect(lambda c: result.update(err=c))
    worker.run()  # direct call: runs in the calling (worker) thread
    if "ok" in result:
        return dest
    logger.warning("Automatic backup failed: %s", result.get("err"))
    return None


class AutoBackupScheduler:
    def __init__(self, settings_get, settings_set, busy=None, on_done=None):
        self._get, self._set, self._busy, self._on_done = settings_get, settings_set, busy, on_done
        self._task: asyncio.Task | None = None

    def start(self):
        if self._task is None or self._task.done():
            self._task = asyncio.ensure_future(self._loop())

    def stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

    def enabled(self) -> bool:
        return bool(self._get("autobackup_enabled", False))

    def interval_seconds(self) -> float:
        try:
            days = float(self._get("autobackup_days", 1) or 1)
        except (TypeError, ValueError):
            days = 1.0
        return max(0.25, days) * 86400

    def due(self) -> bool:
        try:
            last = float(self._get("autobackup_last", 0) or 0)
        except (TypeError, ValueError):
            last = 0.0
        return time.time() - last >= self.interval_seconds()

    async def _loop(self):
        await asyncio.sleep(90)  # let the app finish starting first
        while True:
            try:
                if self.enabled() and self.due():
                    if self._busy and self._busy():
                        await asyncio.sleep(300)
                        continue
                    path = await asyncio.to_thread(create_now)
                    if path is not None:
                        self._set("autobackup_last", time.time())
                        try:
                            keep = int(self._get("autobackup_keep", 5) or 5)
                        except (TypeError, ValueError):
                            keep = 5
                        await asyncio.to_thread(prune, keep)
                        logger.info("Automatic backup created: %s", path)
                        if self._on_done:
                            self._on_done(path)
                    else:
                        await asyncio.sleep(1800)  # try again later
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Automatic backup loop error")
            await asyncio.sleep(1800)
