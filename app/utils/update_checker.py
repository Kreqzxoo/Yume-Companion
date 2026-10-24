"""Check a GitHub repository for a newer Soul of Waifu release.

Only *checks* and reports; nothing is downloaded or installed. The repository
is configured as "owner/repo" (or a github.com URL) in the Updates settings tab
and stored as main setting "update_repo". Empty means "not configured yet".
"""
from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from pathlib import Path

from PyQt6 import QtCore

logger = logging.getLogger("UpdateChecker")

DEFAULT_REPO = ""  # empty = use the "update_repo" value of the branding file when present
VERSION_FILE = Path(__file__).resolve().parents[2] / "VERSION.txt"
_REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def current_version() -> str:
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip() or "unknown"
    except OSError:
        return "unknown"


def normalize_repo(value: str) -> str:
    """Accept 'owner/repo' or a github.com URL; return 'owner/repo' or ''."""
    value = (value or "").strip()
    value = re.sub(r"^https?://(www\.)?github\.com/", "", value, flags=re.I)
    value = re.sub(r"\.git$", "", value.strip("/"))
    parts = value.split("/")
    value = "/".join(parts[:2])
    return value if _REPO_RE.match(value) else ""


def _version_tuple(text: str) -> tuple:
    nums = re.findall(r"\d+", text or "")
    return tuple(int(n) for n in nums[:4])


def is_newer(remote: str, local: str) -> bool:
    r, l = _version_tuple(remote), _version_tuple(local)
    return bool(r) and bool(l) and r > l


def _get_json(url: str):
    req = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "SoulOfWaifu-UpdateChecker",
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def check_for_update(repo: str) -> dict:
    """Return a result dict. Keys: ok, error, local, remote, newer, url, name, notes."""
    local = current_version()
    result = {"ok": False, "error": "", "local": local, "remote": "", "newer": False,
              "url": "", "name": "", "notes": ""}
    repo = normalize_repo(repo)
    if not repo:
        result["error"] = "not_configured"
        return result
    base = f"https://api.github.com/repos/{repo}"
    try:
        try:
            data = _get_json(f"{base}/releases/latest")
            tag, name, url, notes = (data.get("tag_name") or ""), (data.get("name") or ""), \
                (data.get("html_url") or ""), (data.get("body") or "")
        except urllib.error.HTTPError as e:
            if e.code != 404:
                raise
            tags = _get_json(f"{base}/tags?per_page=30")
            if not tags:
                result["error"] = "no_releases"
                return result
            tag = max((t.get("name", "") for t in tags), key=_version_tuple)
            name, notes, url = tag, "", f"https://github.com/{repo}/releases"
    except urllib.error.HTTPError as e:
        result["error"] = "repo_not_found" if e.code == 404 else (
            "rate_limited" if e.code in (403, 429) else f"http_{e.code}")
        return result
    except Exception as e:  # network down, DNS, timeout, bad JSON
        logger.warning("Update check failed: %s", e)
        result["error"] = "network"
        return result

    if not url.startswith("https://github.com/"):
        url = f"https://github.com/{repo}/releases"
    result.update(ok=True, remote=tag, newer=is_newer(tag, local), url=url,
                  name=name or tag, notes=notes[:2000])
    return result


class UpdateCheckWorker(QtCore.QThread):
    finished_check = QtCore.pyqtSignal(dict)

    def __init__(self, repo: str, parent=None):
        super().__init__(parent)
        self.repo = repo

    def run(self):
        self.finished_check.emit(check_for_update(self.repo))
