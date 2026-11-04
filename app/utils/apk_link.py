"""Download address of the newest Android app (APK) in the GitHub releases - shown as QR code in the Android Connector."""
from __future__ import annotations

import logging
import re

from app.utils.update_checker import _get_json, _version_tuple, normalize_repo

logger = logging.getLogger("ApkLink")

APK_NAME = "Yume-Companion.apk"
_DOWNLOAD_RE = re.compile(r"^https://github\.com/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/releases/download/[^/\s]+/" + re.escape(APK_NAME) + "$")


def pick_apk_url(releases: list, repo: str) -> str:
    """Address of the APK of the newest release that has one ('' if no release has it). Pre-releases count, drafts do not."""
    candidates = []
    for r in releases or []:
        if not isinstance(r, dict) or r.get("draft") or not r.get("tag_name"):
            continue
        for a in r.get("assets") or []:
            if isinstance(a, dict) and a.get("name") == APK_NAME and a.get("state", "uploaded") == "uploaded":
                url = str(a.get("browser_download_url") or "")
                # only a file of this repository, taken over from the answer of GitHub (never an address from elsewhere)
                if _DOWNLOAD_RE.match(url) and url.lower().startswith(f"https://github.com/{repo.lower()}/releases/download/"):
                    candidates.append((_version_tuple(str(r["tag_name"])), url))
    return max(candidates)[1] if candidates else ""


def releases_page(repo: str) -> str:
    return f"https://github.com/{repo}/releases" if repo else ""


def find_apk_url(repo_value: str) -> str:
    """Looks up the newest APK; falls back to the releases page when GitHub cannot be reached or no release has an APK."""
    repo = normalize_repo(repo_value)
    if not repo:
        return ""
    try:
        return pick_apk_url(_get_json(f"https://api.github.com/repos/{repo}/releases?per_page=30"), repo) or releases_page(repo)
    except Exception as exc:
        logger.info("APK address could not be read (%s)", exc)
        return releases_page(repo)
