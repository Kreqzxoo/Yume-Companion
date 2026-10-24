"""Vision plugin: a separate local vision-language model (llama.cpp + mmproj).

Images (chat attachments, Discord images) are described by a small vision model
running in its own llama-server process on a GPU of the user's choice. The
description is handed to the chat model as text, so any LLM - local, remote or
text-only - can "see" images.

Everything here is optional: with ``vision_enabled`` off nothing is started.
"""
from __future__ import annotations

import atexit
import base64
import hashlib
import io
import json
import logging
import os
import subprocess
import threading
import time
from pathlib import Path

import requests
from PyQt6 import QtCore

from app.configuration import configuration

logger = logging.getLogger("Vision")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
VISION_DIR = PROJECT_ROOT / "assets" / "vision_models"
BACKEND_DIR = PROJECT_ROOT / "app" / "utils" / "ai_clients" / "backend"
PID_FILE = BACKEND_DIR / "_temp" / "vision_server.pid"
CACHE_FILE = PROJECT_ROOT / "app" / "cache" / "vision_captions.json"
LOG_FILE = PROJECT_ROOT / "logs" / "vision_server.log"

SERVER_PORT = 48598
HF = "https://huggingface.co"

DEFAULT_PROMPT = (
    "Describe this image for someone who cannot see it. Be factual and concise (at most about 150 words): "
    "main subjects, people and what they do, setting, notable objects, colours, mood, and any visible text "
    "(quote it exactly)."
)

# Answer-language instructions, written in the target language (small models follow these best).
LANGUAGE_INSTRUCTIONS = {
    "de": "Antworte ausschließlich auf Deutsch.",
    "en": "Answer in English only.",
    "ru": "Отвечай только на русском языке.",
}
PROGRAM_LANGUAGE_BY_INDEX = {0: "en", 1: "ru", 2: "de"}  # order of the program-language selector


def answer_language() -> str:
    """'de' / 'en' / 'ru': explicit choice, or the program language when set to auto."""
    choice = str(cfg("vision_language", "auto") or "auto").lower()
    if choice in LANGUAGE_INSTRUCTIONS:
        return choice
    try:
        return PROGRAM_LANGUAGE_BY_INDEX.get(int(cfg("program_language", 0) or 0), "en")
    except (TypeError, ValueError):
        return "en"


# Small vision models follow the language of the *whole* instruction, so the default
# instruction exists once per language instead of only an appended sentence.
DEFAULT_PROMPTS = {
    "en": DEFAULT_PROMPT,
    "de": ("Beschreibe dieses Bild für jemanden, der es nicht sehen kann. Sei sachlich und knapp "
           "(höchstens etwa 150 Wörter): Hauptmotive, Personen und was sie tun, Umgebung, auffällige Objekte, "
           "Farben, Stimmung und jeder sichtbare Text (wörtlich zitieren). Antworte ausschließlich auf Deutsch."),
    "ru": ("Опиши это изображение для человека, который его не видит. Будь точным и кратким "
           "(не более 150 слов): главные объекты, люди и их действия, обстановка, заметные предметы, цвета, "
           "настроение и любой видимый текст (процитируй дословно). Отвечай только на русском языке."),
}


def default_prompt() -> str:
    return DEFAULT_PROMPTS[answer_language()]


def is_default_prompt(text: str) -> bool:
    return (text or "").strip() in DEFAULT_PROMPTS.values()


def build_prompt(prompt: str | None = None) -> str:
    custom = (prompt or str(cfg("vision_prompt", "") or "")).strip()
    if not custom or is_default_prompt(custom):
        return default_prompt()  # already written in the answer language
    # A user-written instruction: keep it and state the answer language at the end.
    return f"{custom}\n\n{LANGUAGE_INSTRUCTIONS[answer_language()]}"


# Curated, verified GGUF repositories (ggml-org publishes model + mmproj pairs).
CATALOG = [
    {
        "id": "smolvlm2-2b",
        "name": "SmolVLM2 2.2B (sehr schnell)",
        "repo": "ggml-org/SmolVLM2-2.2B-Instruct-GGUF",
        "files": ["SmolVLM2-2.2B-Instruct-Q4_K_M.gguf", "mmproj-SmolVLM2-2.2B-Instruct-Q8_0.gguf"],
        "size_gb": 1.7, "min_vram_gb": 3,
        "desc": "Kleinstes Modell, läuft auch auf schwachen GPUs oder CPU. Gut für einfache Bildbeschreibungen.",
    },
    {
        "id": "qwen25vl-3b",
        "name": "Qwen2.5-VL 3B (empfohlen)",
        "repo": "ggml-org/Qwen2.5-VL-3B-Instruct-GGUF",
        "files": ["Qwen2.5-VL-3B-Instruct-Q4_K_M.gguf", "mmproj-Qwen2.5-VL-3B-Instruct-Q8_0.gguf"],
        "size_gb": 2.8, "min_vram_gb": 4,
        "desc": "Guter Allrounder, stark bei Text im Bild (OCR) und Bildschirminhalten.",
    },
    {
        "id": "gemma3-4b",
        "name": "Gemma 3 4B",
        "repo": "ggml-org/gemma-3-4b-it-GGUF",
        "files": ["gemma-3-4b-it-Q4_K_M.gguf", "mmproj-model-f16.gguf"],
        "size_gb": 3.3, "min_vram_gb": 5,
        "desc": "Sehr gute allgemeine Beschreibungen und Mehrsprachigkeit. Es gelten die Gemma-Nutzungsbedingungen.",
    },
    {
        "id": "qwen25vl-7b",
        "name": "Qwen2.5-VL 7B (genauer)",
        "repo": "ggml-org/Qwen2.5-VL-7B-Instruct-GGUF",
        "files": ["Qwen2.5-VL-7B-Instruct-Q4_K_M.gguf", "mmproj-Qwen2.5-VL-7B-Instruct-Q8_0.gguf"],
        "size_gb": 5.5, "min_vram_gb": 8,
        "desc": "Deutlich genauer, braucht aber viel Grafikspeicher (neben LLM und TTS wird es eng).",
    },
    {
        "id": "gemma3-12b",
        "name": "Gemma 3 12B (Oberklasse)",
        "repo": "ggml-org/gemma-3-12b-it-GGUF",
        "files": ["gemma-3-12b-it-Q4_K_M.gguf", "mmproj-model-f16.gguf"],
        "size_gb": 8.2, "min_vram_gb": 12,
        "desc": "Beste Qualität dieser Liste; nur für Karten ab ca. 12 GB oder eine eigene zweite GPU.",
    },
]
CUSTOM_ID = "custom"


# ----------------------------------------------------------------- settings
def _settings() -> dict:
    try:
        return configuration.ConfigurationSettings().load_configuration().get("main_settings", {}) or {}
    except Exception:
        return {}


def cfg(key: str, default=None):
    value = _settings().get(key)
    return default if value is None else value


def is_enabled() -> bool:
    return bool(cfg("vision_enabled", False))


def entry_by_id(entry_id: str):
    return next((e for e in CATALOG if e["id"] == entry_id), None)


def entry_paths(entry: dict) -> tuple[Path, Path]:
    folder = VISION_DIR / entry["id"]
    return folder / entry["files"][0], folder / entry["files"][1]


def is_installed(entry: dict) -> bool:
    return all(p.is_file() and p.stat().st_size > 0 for p in entry_paths(entry))


def selected_model_paths() -> tuple[Path | None, Path | None]:
    """(model, mmproj) of the configured model, or (None, None)."""
    model_id = str(cfg("vision_model_id", "") or "")
    if model_id == CUSTOM_ID:
        m, p = cfg("vision_custom_model", ""), cfg("vision_custom_mmproj", "")
        mp, pp = Path(m) if m else None, Path(p) if p else None
        return (mp if mp and mp.is_file() else None, pp if pp and pp.is_file() else None)
    entry = entry_by_id(model_id)
    if entry and is_installed(entry):
        return entry_paths(entry)
    return None, None


def remote_url() -> str:
    """Base URL of a vision server on another PC (Yume LLM Server), '' = run the vision model on this PC."""
    return str(cfg("vision_remote_url", "") or "").strip().rstrip("/")


def _remote_headers() -> dict:
    try:
        from app.configuration import configuration
        key = configuration.ConfigurationAPI().get_token("REMOTE_VISION_API_TOKEN") or ""
    except Exception:
        key = ""
    return {"Authorization": f"Bearer {key}"} if key else {}


def is_ready() -> bool:
    if remote_url():
        return is_enabled()
    m, p = selected_model_paths()
    return is_enabled() and m is not None and p is not None


def plugin_applies(conversation_method: str, native_vision_providers) -> bool:
    """Should images be described by the plugin instead of sent to the chat model?"""
    if not is_ready():
        return False
    if str(cfg("vision_mode", "fallback")) == "always":
        return True
    # Local LLM runs without an mmproj in this app, so it cannot see images itself.
    return conversation_method == "Local LLM" or conversation_method not in native_vision_providers


# --------------------------------------------------------------- download
class VisionDownloadWorker(QtCore.QThread):
    """Downloads all files of a catalog entry (safe: .part files, atomic rename)."""

    progress = QtCore.pyqtSignal(int, str)
    finished_ok = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)
    cancelled = QtCore.pyqtSignal()

    def __init__(self, entry: dict):
        super().__init__()
        self.entry = entry
        self._cancel = False

    def cancel(self):
        self._cancel = True

    @staticmethod
    def _fmt(n: float) -> str:
        for unit in ("B", "KB", "MB", "GB"):
            if n < 1024:
                return f"{n:.1f} {unit}"
            n /= 1024
        return f"{n:.1f} TB"

    def run(self):
        entry = self.entry
        folder = VISION_DIR / entry["id"]
        try:
            folder.mkdir(parents=True, exist_ok=True)
            urls = [(f, f"{HF}/{entry['repo']}/resolve/main/{f}") for f in entry["files"]]
            sizes = {}
            for name, url in urls:
                head = requests.head(url, allow_redirects=True, timeout=20)
                head.raise_for_status()
                sizes[name] = int(head.headers.get("content-length", 0))
            total = sum(sizes.values()) or 1
            done_before = 0
            started = time.time()
            for name, url in urls:
                target = folder / name
                if target.is_file() and sizes[name] and target.stat().st_size == sizes[name]:
                    done_before += sizes[name]
                    continue
                part = folder / (name + ".part")
                with requests.get(url, stream=True, allow_redirects=True, timeout=30) as r:
                    r.raise_for_status()
                    got = 0
                    with open(part, "wb") as fh:
                        for chunk in r.iter_content(chunk_size=1024 * 256):
                            if self._cancel:
                                break
                            if not chunk:
                                continue
                            fh.write(chunk)
                            got += len(chunk)
                            overall = done_before + got
                            speed = overall / max(time.time() - started, 0.001)
                            self.progress.emit(
                                min(99, int(overall * 100 / total)),
                                f"{name}  {self._fmt(overall)} / {self._fmt(total)}  -  {self._fmt(speed)}/s",
                            )
                if self._cancel:
                    part.unlink(missing_ok=True)
                    self.cancelled.emit()
                    return
                if sizes[name] and part.stat().st_size != sizes[name]:
                    part.unlink(missing_ok=True)
                    raise RuntimeError(f"Download incomplete: {name}")
                part.replace(target)
                done_before += sizes[name]
            self.progress.emit(100, "100%")
            self.finished_ok.emit(str(folder))
        except Exception as exc:  # network, disk, HTTP errors
            if not self._cancel:
                self.failed.emit(str(exc))
            else:
                self.cancelled.emit()


def delete_entry(entry: dict) -> None:
    folder = VISION_DIR / entry["id"]
    for name in entry["files"]:
        for suffix in ("", ".part"):
            try:
                (folder / (name + suffix)).unlink()
            except FileNotFoundError:
                pass
    try:
        folder.rmdir()
    except OSError:
        pass


# ----------------------------------------------------------------- server
class _VisionServer:
    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.RLock()
        self._idle_timer: threading.Timer | None = None
        self._signature = None

    # -- helpers --
    @staticmethod
    def _executable(device: str) -> Path | None:
        order = ["cuda", "vulkan"] if device == "cuda" else ["cpu"]
        for name in order:
            p = BACKEND_DIR / name / "llama-server.exe"
            if p.is_file():
                return p
        return None

    @staticmethod
    def _kill_stale():
        try:
            pid = int(PID_FILE.read_text().strip())
        except Exception:
            return
        try:
            import psutil
            proc = psutil.Process(pid)
            if "llama-server" in proc.name().lower():
                proc.kill()
        except Exception:
            pass
        PID_FILE.unlink(missing_ok=True)

    def is_running(self) -> bool:
        with self._lock:
            return self._proc is not None and self._proc.poll() is None

    def _healthy(self) -> bool:
        try:
            return requests.get(f"http://127.0.0.1:{SERVER_PORT}/health", timeout=2).status_code == 200
        except Exception:
            return False

    def ensure_running(self, timeout: int = 240) -> None:
        """Start (or restart after a settings change) and wait until the model is loaded."""
        with self._lock:
            model, mmproj = selected_model_paths()
            if not model or not mmproj:
                raise RuntimeError("Vision model not installed.")
            device = str(cfg("vision_device", "cuda") or "cuda").lower()
            gpu_list = ",".join(p for p in str(cfg("vision_gpu_indices", "") or "").replace(" ", "").split(",") if p.isdigit())
            gpu = gpu_list or str(int(cfg("vision_gpu_index", 0) or 0))
            ctx = int(cfg("vision_context", 4096) or 4096)
            signature = (str(model), str(mmproj), device, gpu, ctx)
            if self.is_running() and signature == self._signature and self._healthy():
                self._touch()
                return
            self.stop()
            self._kill_stale()
            exe = self._executable(device)
            if exe is None:
                raise RuntimeError("llama-server backend not found (app/utils/ai_clients/backend).")
            cmd = [str(exe), "-m", str(model), "--mmproj", str(mmproj), "--port", str(SERVER_PORT),
                   "-c", str(ctx), "--parallel", "1", "--jinja"]
            env = os.environ.copy()
            if exe.parent.name != "cpu":
                cmd += ["--n-gpu-layers", "99"]
                if exe.parent.name == "cuda":
                    env["CUDA_VISIBLE_DEVICES"] = gpu
            else:
                cmd += ["--no-mmproj-offload"]
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            log = open(LOG_FILE, "ab")
            logger.info("Starting vision server: %s", " ".join(cmd))
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            self._proc = subprocess.Popen(cmd, stdout=log, stderr=log, env=env, creationflags=flags)
            PID_FILE.parent.mkdir(parents=True, exist_ok=True)
            PID_FILE.write_text(str(self._proc.pid))
            self._signature = signature
            deadline = time.time() + timeout
            while time.time() < deadline:
                if self._proc.poll() is not None:
                    self._proc = None
                    raise RuntimeError(f"Vision server exited early (see {LOG_FILE.name}).")
                if self._healthy():
                    self._touch()
                    return
                time.sleep(1.0)
            self.stop()
            raise RuntimeError("Vision server did not become ready in time.")

    def _touch(self):
        minutes = int(cfg("vision_idle_minutes", 10) or 0)
        if self._idle_timer:
            self._idle_timer.cancel()
            self._idle_timer = None
        if minutes > 0:
            self._idle_timer = threading.Timer(minutes * 60, self.stop)
            self._idle_timer.daemon = True
            self._idle_timer.start()

    def stop(self):
        with self._lock:
            if self._idle_timer:
                self._idle_timer.cancel()
                self._idle_timer = None
            proc, self._proc = self._proc, None
            self._signature = None
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=8)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass
        PID_FILE.unlink(missing_ok=True)


server = _VisionServer()
atexit.register(server.stop)


# ----------------------------------------------------------------- captions
def _load_cache() -> dict:
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(cache: dict) -> None:
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        if len(cache) > 400:
            cache = dict(list(cache.items())[-300:])
        CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def _key_for_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def cached_caption_for_file(path: str | os.PathLike) -> str:
    """Caption of an image file if it was described before (no inference)."""
    try:
        raw = Path(path).read_bytes()
        return _load_cache().get(_key_for_bytes(raw + build_prompt().encode("utf-8")), "")
    except OSError:
        return ""


def _prepare_jpeg_b64(raw: bytes) -> str:
    from PIL import Image
    max_px = int(cfg("vision_max_image_px", 1024) or 1024)
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if max(img.size) > max_px:
        img.thumbnail((max_px, max_px), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode()


def describe_bytes(raw: bytes, prompt: str | None = None, use_cache: bool = True) -> str:
    """Blocking: describe an image (any common format). Raises RuntimeError on failure."""
    full_prompt = build_prompt(prompt)
    key = _key_for_bytes(raw + full_prompt.encode("utf-8"))  # new prompt/language => new description
    cache = _load_cache()
    if use_cache and key in cache:
        return cache[key]
    b64 = _prepare_jpeg_b64(raw)
    remote = remote_url()
    if not remote:
        server.ensure_running()
    payload = {
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": full_prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ],
        }],
        "max_tokens": 400,
        "temperature": 0.2,
    }
    import time as _time
    _t0 = _time.time()
    if remote:
        resp = requests.post(f"{remote}/v1/chat/completions", json=payload, headers=_remote_headers(), timeout=300)
    else:
        resp = requests.post(f"http://127.0.0.1:{SERVER_PORT}/v1/chat/completions", json=payload, timeout=300)
    try:
        from app.utils.runtime_stats import stats as _stats
        _usage = (resp.json().get("usage") or {}) if resp.status_code == 200 else {}
        _stats.record_vision(int(_usage.get("prompt_tokens") or 0), int(_usage.get("completion_tokens") or 0),
                             _time.time() - _t0, ok=resp.status_code == 200)
    except Exception:
        pass
    if resp.status_code != 200:
        raise RuntimeError(f"Vision server error {resp.status_code}: {resp.text[:200]}")
    text = (resp.json()["choices"][0]["message"].get("content") or "").strip()
    if not text:
        raise RuntimeError("Vision model returned no description.")
    if not remote:
        server._touch()
    cache[key] = text
    _save_cache(cache)
    return text


def describe_file(path: str | os.PathLike, prompt: str | None = None) -> str:
    return describe_bytes(Path(path).read_bytes(), prompt)


def describe_b64(b64: str, prompt: str | None = None) -> str:
    return describe_bytes(base64.b64decode(b64), prompt)


class DescribeWorker(QtCore.QThread):
    """Runs one description in the background (used by the settings test button)."""

    done = QtCore.pyqtSignal(str)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, path: str):
        super().__init__()
        self.path = path

    def run(self):
        try:
            started = time.time()
            text = describe_bytes(Path(self.path).read_bytes(), use_cache=False)
            self.done.emit(f"{text}\n\n({time.time() - started:.1f} s)")
        except Exception as exc:
            self.failed.emit(str(exc))
