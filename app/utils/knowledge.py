"""Knowledge base: full-text search over the user's own documents (PDF, Word, text, Markdown, CSV, HTML).

Folders are chosen in the settings; the files are cut into small passages and stored in a local SQLite index (FTS5, ranking by BM25, words match as
prefixes so "Kündigung" finds "Kündigungsfrist"). Nothing leaves the PC. Only new / changed files are read again. The index is rebuildable, so it is
not part of the backups; the list of folders is.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sqlite3
import threading
import time
from pathlib import Path

logger = logging.getLogger("Knowledge")
DIR = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion"
CONFIG = DIR / "knowledge.json"
DB = DIR / "knowledge.db"
EXTS = {".pdf", ".docx", ".txt", ".md", ".markdown", ".csv", ".html", ".htm", ".rtf", ".log", ".json"}
MAX_FILE_MB = 60
CHUNK = 900
OVERLAP = 120
_lock = threading.RLock()
progress = {"running": False, "files": 0, "done": 0, "chunks": 0, "message": ""}
SKIP_DIRS = {"node_modules", ".git", "__pycache__", "$recycle.bin", "appdata", "site-packages", "envs", ".venv", "venv"}


# ------------------------------------------------------------------ config
SAVED = DIR / "knowledge_saved"                 # web pages and notes Yume saved: always part of the knowledge base


def user_folders() -> list[str]:
    try:
        return [f for f in json.loads(CONFIG.read_text(encoding="utf-8")).get("folders", []) if f]
    except (OSError, ValueError):
        return []


def folders() -> list[str]:
    items = user_folders()
    if SAVED.is_dir() and str(SAVED) not in items:
        items.append(str(SAVED))
    return items


def _slug(text: str) -> str:
    return re.sub(r"[^\w\- äöüÄÖÜß]", "", text).strip().replace(" ", "_")[:50] or "Notiz"


def add_note(text: str, title: str = "", source: str = "") -> Path:
    """Saves a note (or the text of a web page) as a file with the source in its first line, and reads it into the index."""
    SAVED.mkdir(parents=True, exist_ok=True)
    title = (title or text.strip().splitlines()[0][:50] or "Notiz").strip()
    path = SAVED / f"{time.strftime('%Y-%m-%d')}_{_slug(title)}.txt"
    n = 1
    while path.exists():
        n += 1
        path = SAVED / f"{time.strftime('%Y-%m-%d')}_{_slug(title)}_{n}.txt"
    path.write_text(f"Quelle: {source or 'eigene Notiz'}\nTitel: {title}\n\n{text.strip()}\n", encoding="utf-8")
    try:
        reindex(60)
    except Exception:
        pass
    return path


def fetch_page(url: str) -> tuple[str, str]:
    """-> (title, plain text) of a web page. Raises on errors."""
    import html as h
    import urllib.request
    if not re.match(r"^https?://", url, re.I):
        raise ValueError("keine gültige Adresse")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 YumeCompanion"})
    with urllib.request.urlopen(req, timeout=20) as r:
        ctype = r.headers.get("Content-Type", "")
        if "html" not in ctype and "text" not in ctype:
            raise ValueError("kein Text/HTML-Inhalt")
        raw = r.read(3_000_000).decode(r.headers.get_content_charset() or "utf-8", errors="replace")
    m = re.search(r"(?is)<title[^>]*>(.*?)</title>", raw)
    title = h.unescape(m.group(1)).strip() if m else url
    raw = re.sub(r"(?is)<(script|style|nav|footer|header|noscript)\b.*?</\1>", " ", raw)
    text = h.unescape(re.sub(r"(?s)<[^>]+>", "\n", raw))
    text = re.sub(r"[ \t]+", " ", text)
    text = "\n".join(s.strip() for s in text.splitlines() if len(s.strip()) > 2)
    return title, text


def add_url(url: str) -> Path:
    title, text = fetch_page(url)
    if len(text) < 80:
        raise ValueError("auf der Seite war kaum Text zu finden")
    return add_note(text, title, url)


def source_of(path: str) -> str:
    """For saved pages / notes: the source line; empty for ordinary files."""
    try:
        if Path(path).parent == SAVED:
            first = Path(path).read_text(encoding="utf-8", errors="replace").splitlines()[0]
            return first.replace("Quelle:", "").strip()
    except (OSError, IndexError):
        pass
    return ""


def semantic_enabled() -> bool:
    try:
        return bool(json.loads(CONFIG.read_text(encoding="utf-8")).get("semantic", False))
    except (OSError, ValueError):
        return False


def save_folders(items: list[str]):
    DIR.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"folders": list(dict.fromkeys(i for i in items if i != str(SAVED))), "semantic": semantic_enabled()}, ensure_ascii=False, indent=1), encoding="utf-8")


def set_semantic(on: bool):
    DIR.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps({"folders": user_folders(), "semantic": bool(on)}, ensure_ascii=False, indent=1), encoding="utf-8")


# ------------------------------------------------------------------ meaning-based search (optional): multilingual embeddings, computed once per passage
MODEL_NAME = "intfloat/multilingual-e5-small"                  # about 470 MB, German works well
_model = None
_matrix = {"key": None, "rowids": None, "mat": None}


def _embedder():
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        cache = DIR / "models"
        cache.mkdir(parents=True, exist_ok=True)
        _model = SentenceTransformer(MODEL_NAME, cache_folder=str(cache), device="cpu")
    return _model


def _embed(texts: list[str], prefix: str):
    import numpy as np
    vecs = _embedder().encode([prefix + t for t in texts], normalize_embeddings=True, batch_size=32, show_progress_bar=False)
    return np.asarray(vecs, dtype=np.float16)


def _embed_missing(con) -> int:
    """Vectors for every passage that has none yet (new / changed files). Returns how many were computed."""
    con.execute("create table if not exists vec(rowid integer primary key, emb blob)")
    con.execute("delete from vec where rowid not in (select rowid from passages)")
    done = 0
    while True:
        rows = con.execute("select rowid, text from passages where rowid not in (select rowid from vec) limit 128").fetchall()
        if not rows:
            break
        progress["message"] = f"Berechne Bedeutungs-Vektoren … ({done})"
        vecs = _embed([r[1][:1200] for r in rows], "passage: ")
        con.executemany("insert or replace into vec(rowid, emb) values(?,?)", [(r[0], vecs[i].tobytes()) for i, r in enumerate(rows)])
        con.commit()
        done += len(rows)
    return done


def _load_matrix(con):
    import numpy as np
    count, top = con.execute("select count(*), coalesce(max(rowid),0) from vec").fetchone()
    key = (count, top)
    if _matrix["key"] != key:
        rows = con.execute("select rowid, emb from vec").fetchall()
        _matrix.update(key=key, rowids=np.array([r[0] for r in rows], dtype=np.int64),
                       mat=np.vstack([np.frombuffer(r[1], dtype=np.float16) for r in rows]) if rows else np.zeros((0, 384), dtype=np.float16))
    return _matrix["rowids"], _matrix["mat"]


def semantic_ready() -> bool:
    try:
        con = _db()
        try:
            return bool(con.execute("select name from sqlite_master where name='vec'").fetchone()) and con.execute("select count(*) from vec").fetchone()[0] > 0
        finally:
            con.close()
    except sqlite3.Error:
        return False


# ------------------------------------------------------------------ database
def _db() -> sqlite3.Connection:
    DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(str(DB), timeout=30)
    c.execute("create table if not exists files(path text primary key, mtime real, size integer, chunks integer)")
    c.execute("create virtual table if not exists passages using fts5(text, path unindexed, page unindexed, tokenize='unicode61 remove_diacritics 2')")
    return c


def _chunks(text: str):
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r"\n\s*\n+", "\n\n", text).strip()
    start = 0
    while start < len(text):
        end = min(len(text), start + CHUNK)
        if end < len(text):                              # cut at a sentence / line end when possible
            cut = max(text.rfind(". ", start + 400, end), text.rfind("\n", start + 400, end))
            end = cut + 1 if cut > 0 else end
        piece = text[start:end].strip()
        if len(piece) > 40:
            yield piece
        if end >= len(text):
            break
        start = max(end - OVERLAP, start + 1)


def _pages(path: Path):
    """Yields (page number or 0, text)."""
    ext = path.suffix.lower()
    if ext == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(str(path))
        for i, page in enumerate(reader.pages, 1):
            yield i, page.extract_text() or ""
    elif ext == ".docx":
        import docx
        yield 0, "\n".join(p.text for p in docx.Document(str(path)).paragraphs)
    elif ext in (".html", ".htm"):
        import html as h
        raw = path.read_text(encoding="utf-8", errors="replace")
        raw = re.sub(r"(?is)<(script|style).*?</\1>", " ", raw)
        yield 0, h.unescape(re.sub(r"(?s)<[^>]+>", " ", raw))
    elif ext == ".rtf":
        raw = path.read_text(encoding="utf-8", errors="replace")
        yield 0, re.sub(r"\\[a-z]+-?\d* ?|[{}]", " ", raw)
    else:
        yield 0, path.read_text(encoding="utf-8", errors="replace")


def _walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d.lower() not in SKIP_DIRS and not d.startswith(".")]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in EXTS:
                try:
                    st = p.stat()
                except OSError:
                    continue
                if st.st_size <= MAX_FILE_MB * 1024 * 1024:
                    yield p, st


def reindex(max_seconds: float = 900.0) -> dict:
    """Reads new / changed files, forgets deleted ones. Blocking: run it in a thread."""
    with _lock:
        if progress["running"]:
            return dict(progress)
        progress.update(running=True, files=0, done=0, chunks=0, message="Suche Dateien …")
    started = time.time()
    try:
        seen = {}
        for f in folders():
            root = Path(f)
            if root.is_dir():
                for p, st in _walk(root):
                    seen[str(p)] = (st.st_mtime, st.st_size)
        progress["files"] = len(seen)
        con = _db()
        try:
            known = {r[0]: (r[1], r[2]) for r in con.execute("select path, mtime, size from files")}
            for gone in set(known) - set(seen):                    # deleted or no longer in a chosen folder
                con.execute("delete from passages where path = ?", (gone,))
                con.execute("delete from files where path = ?", (gone,))
            for path, (mtime, size) in seen.items():
                progress["done"] += 1
                if known.get(path) == (mtime, size):
                    continue
                if time.time() - started > max_seconds:
                    progress["message"] = "Zeitlimit erreicht, der Rest folgt beim nächsten Lauf."
                    break
                progress["message"] = os.path.basename(path)
                con.execute("delete from passages where path = ?", (path,))
                n = 0
                try:
                    for page, text in _pages(Path(path)):
                        for piece in _chunks(text):
                            con.execute("insert into passages(text, path, page) values(?,?,?)", (piece, path, page))
                            n += 1
                except Exception as exc:
                    logger.debug("could not read %s: %s", path, exc)
                con.execute("insert or replace into files values(?,?,?,?)", (path, mtime, size, n))
                progress["chunks"] += n
                if progress["done"] % 25 == 0:
                    con.commit()
            con.commit()
            if semantic_enabled():
                try:
                    _embed_missing(con)
                except Exception as exc:
                    logger.warning("Meaning vectors failed", exc_info=True)
                    progress["message"] = f"Bedeutungs-Suche nicht möglich: {str(exc)[:90]}"
        finally:
            con.close()
        if not progress["message"].startswith("Bedeutungs-Suche"):
            progress["message"] = "Fertig."
    except Exception as exc:
        logger.warning("Indexing failed", exc_info=True)
        progress["message"] = f"Fehler: {str(exc)[:100]}"
    finally:
        progress["running"] = False
    return dict(progress)


def status() -> dict:
    try:
        con = _db()
        try:
            files, chunks = con.execute("select count(*), coalesce(sum(chunks),0) from files").fetchone()
        finally:
            con.close()
    except sqlite3.Error:
        files = chunks = 0
    return {"files": files, "chunks": chunks, "folders": folders(), "running": progress["running"], "message": progress["message"]}


_STOP = {"der", "die", "das", "und", "oder", "ist", "sind", "was", "wie", "wo", "wer", "wann", "zu", "zur", "zum", "im", "in", "am", "an", "auf", "von", "mit", "für", "ein", "eine",
         "einen", "dem", "den", "des", "ich", "mein", "meine", "meinem", "meiner", "steht", "stand", "bitte", "mal", "gibt", "es", "dass", "wird", "wurde", "hat", "habe", "kann"}


def search(query: str, limit: int = 5) -> list[dict]:
    """Best passages for the question: [{'path', 'page', 'text', 'score'}]. With the optional meaning search the keyword ranking and the
    similarity ranking are combined (reciprocal rank fusion), so a question without any matching word still finds the passage."""
    hits = _search_keywords(query, 30 if semantic_enabled() else limit)
    if semantic_enabled() and (query or "").strip():
        try:
            sem = _search_semantic(query, 30)
        except Exception:
            logger.debug("semantic search failed", exc_info=True)
            sem = []
        if sem:
            score: dict = {}
            by_id: dict = {}
            for rank, h in enumerate(hits):
                score[h["rowid"]] = score.get(h["rowid"], 0) + 1 / (60 + rank)
                by_id[h["rowid"]] = h
            for rank, h in enumerate(sem):
                score[h["rowid"]] = score.get(h["rowid"], 0) + 1 / (60 + rank)
                by_id.setdefault(h["rowid"], h)
            hits = [dict(by_id[r], score=s) for r, s in sorted(score.items(), key=lambda kv: -kv[1])]
    return hits[:max(1, min(limit, 12))]


def _search_semantic(query: str, limit: int) -> list[dict]:
    import numpy as np
    con = _db()
    try:
        if not con.execute("select name from sqlite_master where name='vec'").fetchone():
            return []
        rowids, mat = _load_matrix(con)
        if len(rowids) == 0:
            return []
        q = _embed([query], "query: ")[0].astype(np.float32)
        sims = mat.astype(np.float32) @ q
        order = np.argsort(-sims)[:limit]
        out = []
        for i in order:
            if sims[i] < 0.78:                       # e5 similarities of unrelated texts are still around 0.7: only clearly related passages count
                continue
            r = con.execute("select path, page, text from passages where rowid = ?", (int(rowids[i]),)).fetchone()
            if r:
                out.append({"rowid": int(rowids[i]), "path": r[0], "page": r[1], "text": r[2], "score": float(sims[i])})
        return out
    finally:
        con.close()


def _search_keywords(query: str, limit: int = 5) -> list[dict]:
    words = [w for w in re.findall(r"[\wäöüßÄÖÜ]{3,}", (query or "").lower()) if w not in _STOP]
    if not words:
        return []
    match = " OR ".join(f'"{w}"*' for w in dict.fromkeys(words))
    try:
        con = _db()
        try:
            rows = con.execute("select path, page, text, bm25(passages), rowid from passages where passages match ? order by bm25(passages) limit ?", (match, max(1, min(limit, 40)))).fetchall()
        finally:
            con.close()
    except sqlite3.Error as exc:
        logger.debug("search failed: %s", exc)
        return []
    return [{"rowid": r[4], "path": r[0], "page": r[1], "text": r[2], "score": -r[3]} for r in rows]
