"""Download of a release setup from GitHub, SHA-256 check and start of the setup (used by the Updates page and the start-up notice).

Safety rules (every one of them stops the update before anything is started):
  * the file must come from the configured repository: https://github.com/<owner>/<repo>/releases/download/<tag>/Yume-Companion-Setup-*.exe,
    and the redirect target must be a GitHub download host;
  * the SHA-256 that GitHub reports for the uploaded file (and, if present, the "<name>.sha256" file of the release) must be known and
    must match the downloaded bytes; without a known checksum nothing is installed;
  * the size must match, enough free disk space is needed, and the file must look like a Windows program;
  * the setup is only started after the check, as a normal wizard (the user still confirms it there); the program is closed by the caller.
"""
from __future__ import annotations

import hashlib
import logging
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable, Optional

from PyQt6 import QtCore

logger = logging.getLogger("UpdateInstaller")

SETUP_NAME_RE = re.compile(r"^Yume-Companion-Setup-[0-9A-Za-z._-]+\.exe$")
DOWNLOAD_HOSTS = ("github.com",)                 # host of the URL that the release lists
REDIRECT_SUFFIXES = ("github.com", "githubusercontent.com")      # hosts GitHub redirects the file download to
CHUNK = 1 << 20
ALLOW_INSECURE_FOR_TESTS = False                 # tests serve the file from 127.0.0.1


class UpdateError(Exception):
    """key: short code (see ERROR_TEXTS in main.py), detail: technical text for the log."""

    def __init__(self, key: str, detail: str = ""):
        super().__init__(f"{key}: {detail}" if detail else key)
        self.key = key
        self.detail = detail


def updates_dir() -> Path:
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "updates"


def _host_ok(host: str, allowed: tuple, suffix: bool) -> bool:
    host = (host or "").lower()
    return any(host == a or (suffix and host.endswith("." + a)) for a in allowed)


def validate(result: dict) -> dict:
    """Checks the result of update_checker.check_for_update and returns what is needed for the download. Raises UpdateError."""
    url = str(result.get("setup_url") or "")
    name = str(result.get("setup_name") or "")
    repo = str(result.get("repo") or "")
    if not url or not name:
        raise UpdateError("no_setup")
    if not SETUP_NAME_RE.match(name):
        raise UpdateError("bad_url", "file name " + name)
    parts = urllib.parse.urlparse(url)
    if ALLOW_INSECURE_FOR_TESTS:
        pass
    else:
        if parts.scheme != "https" or not _host_ok(parts.hostname or "", DOWNLOAD_HOSTS, False):
            raise UpdateError("bad_url", url)
        prefix = f"/{repo}/releases/download/"
        if not repo or not parts.path.lower().startswith(prefix.lower()) or Path(urllib.parse.unquote(parts.path)).name != name:
            raise UpdateError("bad_url", url)
    if not (result.get("sha256") or result.get("sha256_url")):
        raise UpdateError("no_checksum")
    return {"url": url, "name": name, "size": int(result.get("setup_size") or 0),
            "sha256": str(result.get("sha256") or "").lower(), "sha256_url": str(result.get("sha256_url") or "")}


def _open(url: str, timeout: int = 30):
    resp = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "YumeCompanion-Updater"}), timeout=timeout)
    final = urllib.parse.urlparse(resp.geturl())
    if not ALLOW_INSECURE_FOR_TESTS and (final.scheme != "https" or not _host_ok(final.hostname or "", REDIRECT_SUFFIXES, True)):
        resp.close()
        raise UpdateError("bad_url", "redirect to " + resp.geturl())
    return resp


def _sidecar_hash(url: str) -> str:
    """first 64-digit hex number of a '<name>.sha256' file"""
    with _open(url) as resp:
        text = resp.read(4096).decode("utf-8", "replace")
    m = re.search(r"\b[0-9a-fA-F]{64}\b", text)
    if not m:
        raise UpdateError("no_checksum", "sha256 file without a checksum")
    return m.group(0).lower()


def expected_hash(info: dict) -> str:
    """The checksum the download must have. If GitHub's digest and the sha256 file of the release are both known they must agree."""
    api, side = info["sha256"], ""
    if info["sha256_url"]:
        try:
            side = _sidecar_hash(info["sha256_url"])
        except UpdateError:
            if not api:
                raise
        except Exception as exc:
            if not api:
                raise UpdateError("network", str(exc))
            logger.warning("sha256 file not readable: %s", exc)
    if api and side and api != side:
        raise UpdateError("hash_conflict", f"digest {api} vs file {side}")
    value = api or side
    if not value:
        raise UpdateError("no_checksum")
    return value


def download_and_verify(result: dict, progress: Optional[Callable[[int, int], None]] = None,
                        cancelled: Optional[Callable[[], bool]] = None) -> Path:
    """Downloads the setup of a release into %LOCALAPPDATA%\\YumeCompanion\\updates, checks it and returns its path. Raises UpdateError."""
    info = validate(result)
    want = expected_hash(info)
    folder = updates_dir()
    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("Yume-Companion-Setup-*"):            # earlier downloads are not needed any more
        try:
            old.unlink()
        except OSError:
            pass
    size = info["size"]
    if size and shutil.disk_usage(folder).free < size * 1.25:
        raise UpdateError("disk_space", f"{shutil.disk_usage(folder).free} free, {size} needed")
    final = folder / info["name"]
    part = folder / (info["name"] + ".part")
    digest = hashlib.sha256()
    done = 0
    try:
        with _open(info["url"]) as resp, open(part, "wb") as out:
            total = int(resp.headers.get("Content-Length") or size or 0)
            if size and total and total != size:
                raise UpdateError("size_mismatch", f"{total} announced, {size} expected")
            while True:
                if cancelled and cancelled():
                    raise UpdateError("cancelled")
                block = resp.read(CHUNK)
                if not block:
                    break
                out.write(block)
                digest.update(block)
                done += len(block)
                if progress:
                    progress(done, total or size)
        if size and done != size:
            raise UpdateError("size_mismatch", f"{done} received, {size} expected")
        if digest.hexdigest() != want:
            raise UpdateError("hash_mismatch", f"{digest.hexdigest()} received, {want} expected")
        with open(part, "rb") as fh:
            if fh.read(2) != b"MZ":
                raise UpdateError("not_exe")
        part.replace(final)
        return final
    except UpdateError:
        part.unlink(missing_ok=True)
        raise
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        part.unlink(missing_ok=True)
        raise UpdateError("network", str(exc))


def launch_setup(path: Path) -> None:
    """Starts the checked setup as a separate program (no shell). The caller closes Yume Companion afterwards."""
    path = Path(path)
    if not SETUP_NAME_RE.match(path.name) or not path.is_file() or path.parent.resolve() != updates_dir().resolve():
        raise UpdateError("launch_failed", "unexpected file " + str(path))
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    try:
        subprocess.Popen([str(path)], close_fds=True, creationflags=flags, cwd=str(path.parent))
    except OSError as exc:
        raise UpdateError("launch_failed", str(exc))


class DownloadWorker(QtCore.QThread):
    progress = QtCore.pyqtSignal(int, int)          # received, total (bytes)
    finished_ok = QtCore.pyqtSignal(str)            # path of the checked setup
    failed = QtCore.pyqtSignal(str, str)            # key, detail

    def __init__(self, result: dict, parent=None):
        super().__init__(parent)
        self._result = dict(result)
        self._cancel = False

    def cancel(self):
        self._cancel = True

    def run(self):
        try:
            path = download_and_verify(self._result, lambda d, t: self.progress.emit(d, t), lambda: self._cancel)
        except UpdateError as exc:
            logger.warning("update download failed: %s", exc)
            self.failed.emit(exc.key, exc.detail)
            return
        except Exception as exc:  # never let a thread die silently
            logger.exception("update download crashed")
            self.failed.emit("network", str(exc))
            return
        self.finished_ok.emit(str(path))
