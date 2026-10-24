"""Inbox: things the user sends to Yume from the phone with "Share -> Yume" (voice notes, pictures, texts, links, PDFs, Word files).

They are saved in  Downloads\\Yume Eingang  and listed in inbox.json. The chat tool 'inbox' reads them out: voice notes are transcribed (Whisper), pictures are
described (vision model), PDFs / Word / text are read - Yume can then summarise, answer questions about them or forward the content into other tools.
"""
from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
import time
import uuid
from pathlib import Path

DIR = Path(os.environ.get("USERPROFILE") or Path.home()) / "Downloads" / "Yume Eingang"
INDEX = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "inbox.json"
_lock = threading.RLock()
AUDIO = {".ogg", ".opus", ".mp3", ".m4a", ".aac", ".wav", ".amr", ".flac", ".3gp", ".oga", ".webm"}
IMAGE = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp", ".heic"}
TEXT = {".txt", ".md", ".csv", ".json", ".log", ".html", ".xml", ".url"}
MAX_BYTES = 300 * 1024 * 1024


def _load() -> list[dict]:
    try:
        data = json.loads(INDEX.read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


def _save(items: list[dict]):
    INDEX.parent.mkdir(parents=True, exist_ok=True)
    tmp = INDEX.with_suffix(".tmp")
    tmp.write_text(json.dumps(items[-200:], ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(INDEX)


def safe_name(name: str, mime: str = "") -> str:
    name = re.sub(r"[^\w.\- äöüÄÖÜß()]", "_", os.path.basename(name or "")).strip(" .")[:90] or "datei"
    if not Path(name).suffix and mime:
        name += mimetypes.guess_extension(mime.split(";")[0].strip()) or ""
    return name


def kind_of(path: Path, mime: str = "") -> str:
    ext = path.suffix.lower()
    if ext in AUDIO or mime.startswith("audio/"):
        return "audio"
    if ext in IMAGE or mime.startswith("image/"):
        return "image"
    if ext == ".pdf" or mime == "application/pdf":
        return "pdf"
    if ext == ".docx":
        return "word"
    if ext in TEXT or mime.startswith("text/"):
        return "text"
    return "file"


def target_path(name: str) -> Path:
    DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    return DIR / f"{stamp}_{name}"


def register(path: Path, mime: str = "", source: str = "") -> dict:
    item = {"id": uuid.uuid4().hex[:6], "name": path.name, "path": str(path), "kind": kind_of(path, mime), "size": path.stat().st_size,
            "time": time.strftime("%Y-%m-%dT%H:%M:%S"), "source": source}
    with _lock:
        items = _load()
        items.append(item)
        _save(items)
    return item


def save_text(text: str, title: str = "", source: str = "") -> dict:
    text = str(text or "").strip()[:200_000]
    name = safe_name(title or (text.splitlines()[0][:40] if text else "Text")) + ".txt"
    p = target_path(name)
    p.write_text(text, encoding="utf-8")
    return register(p, "text/plain", source)


def list_items(limit: int = 15) -> list[dict]:
    return list(reversed(_load()))[:limit]


def get(item_id: str) -> dict | None:
    key = str(item_id or "").strip().lower()
    items = list(reversed(_load()))
    if not key or key == "latest":
        return items[0] if items else None
    return next((i for i in items if i["id"] == key or key in i["name"].lower()), None)


def read_text(path: Path, kind: str, limit: int = 8000) -> str:
    """Text of a text file / PDF / Word document ('' when none)."""
    if kind == "text":
        return path.read_text(encoding="utf-8", errors="replace")[:limit]
    if kind == "pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        out = []
        for page in reader.pages[:40]:
            out.append(page.extract_text() or "")
            if sum(len(x) for x in out) > limit:
                break
        return "\n".join(out)[:limit]
    if kind == "word":
        import docx
        return "\n".join(p.text for p in docx.Document(str(path)).paragraphs)[:limit]
    return ""
