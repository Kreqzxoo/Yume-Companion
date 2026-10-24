"""File helper: find files by name, list what changed recently, open a file. Only the user's own folders (Desktop, Documents, Downloads, Pictures,
Videos, Music and their OneDrive versions); program folders, caches and system folders are skipped. Read-only except 'open' (asks first)."""
from __future__ import annotations

import os
import re
import time
from datetime import datetime
from pathlib import Path

SKIP_DIRS = {"node_modules", ".git", "__pycache__", "venv", ".venv", "site-packages", "envs", "$recycle.bin", "appdata", "cache", "caches", ".cache", "temp", "tmp",
             "logs", ".soul", ".soul_stage", "yume android", "yume companion 2.5.3 main", "yume companion 3.0.0 beta", "yume updater", "build", "intermediates"}
KINDS = {
    "bild": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic"}, "foto": {".jpg", ".jpeg", ".png", ".heic"},
    "video": {".mp4", ".mkv", ".mov", ".avi", ".webm"}, "musik": {".mp3", ".flac", ".wav", ".m4a", ".ogg"},
    "dokument": {".pdf", ".doc", ".docx", ".txt", ".odt", ".rtf", ".md"}, "tabelle": {".xlsx", ".xls", ".csv", ".ods"},
    "praesentation": {".pptx", ".ppt", ".odp"}, "archiv": {".zip", ".7z", ".rar"}, "code": {".py", ".js", ".ts", ".cs", ".kt", ".java", ".cpp", ".html", ".css"},
}


def roots() -> list[Path]:
    home = Path.home()
    names = ["Desktop", "Documents", "Downloads", "Pictures", "Videos", "Music", "Dokumente", "Bilder", "Musik"]
    found = []
    for base in (home, home / "OneDrive"):
        for n in names:
            p = base / n
            if p.is_dir() and p not in found:
                found.append(p)
    return found


def _walk(budget_s: float = 6.0, max_files: int = 300_000):
    """Yields (path, size, mtime) of files in the user folders (time and count limited)."""
    t0 = time.time()
    count = 0
    stack = [(r, 0) for r in roots()]
    while stack:
        folder, depth = stack.pop()
        try:
            with os.scandir(folder) as it:
                for e in it:
                    if time.time() - t0 > budget_s or count > max_files:
                        return
                    try:
                        if e.is_dir(follow_symlinks=False):
                            if depth < 7 and e.name.lower() not in SKIP_DIRS and not e.name.startswith("."):
                                stack.append((Path(e.path), depth + 1))
                        elif e.is_file(follow_symlinks=False):
                            st = e.stat()
                            count += 1
                            yield Path(e.path), st.st_size, st.st_mtime
                    except OSError:
                        continue
        except OSError:
            continue


def _size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024


def _line(p: Path, size: int, mtime: float) -> str:
    return f"{datetime.fromtimestamp(mtime).strftime('%d.%m.%Y %H:%M')}  {_size(size)}  {p}"


def _kind_exts(kind: str) -> set[str]:
    k = (kind or "").lower().replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    for key, exts in KINDS.items():
        if key in k:
            return exts
    return set()


def find(query: str, kind: str = "", limit: int = 15) -> list[str]:
    words = [w for w in re.split(r"\s+", (query or "").lower().strip()) if w]
    exts = _kind_exts(kind)
    hits = []
    for p, size, mtime in _walk():
        name = p.name.lower()
        if words and not all(w in name or w in str(p.parent).lower() for w in words):
            continue
        if exts and p.suffix.lower() not in exts:
            continue
        hits.append((mtime, p, size))
    hits.sort(reverse=True)
    return [_line(p, s, m) for m, p, s in hits[:limit]]


def recent(days: float = 1.0, kind: str = "", limit: int = 25) -> list[str]:
    since = time.time() - days * 86400
    exts = _kind_exts(kind)
    hits = [(m, p, s) for p, s, m in _walk() if m >= since and (not exts or p.suffix.lower() in exts)]
    hits.sort(reverse=True)
    return [_line(p, s, m) for m, p, s in hits[:limit]]


def inside_roots(path: str) -> Path | None:
    try:
        p = Path(path).expanduser().resolve()
    except OSError:
        return None
    for r in roots():
        try:
            p.relative_to(r.resolve())
            return p if p.exists() else None
        except ValueError:
            continue
    return None
