"""Lightweight, thread-safe runtime statistics (LLM / TTS / STT / Vision / context) for the dashboard.

Token counts for chat models are estimates (characters / ~3.8) because the providers only stream text; vision uses the
real numbers reported by the vision server.
"""
from __future__ import annotations

import collections
import threading
import time

_WINDOW = 30


def est_tokens(text) -> int:
    if not text:
        return 0
    return max(1, int(round(len(str(text)) / 3.8)))


def messages_chars(messages) -> int:
    total = 0
    try:
        for m in messages or []:
            content = m.get("content") if isinstance(m, dict) else None
            if isinstance(content, str):
                total += len(content)
            elif isinstance(content, list):
                for part in content:
                    if isinstance(part, dict) and isinstance(part.get("text"), str):
                        total += len(part["text"])
    except Exception:
        pass
    return total


class _Series:
    def __init__(self):
        self.items = collections.deque(maxlen=_WINDOW)
        self.count = 0
        self.errors = 0
        self.last = None

    def add(self, item: dict, ok: bool = True):
        self.items.append(item)
        self.last = item
        self.count += 1
        if not ok:
            self.errors += 1

    def avg(self, key):
        vals = [i[key] for i in self.items if i.get(key) is not None]
        return (sum(vals) / len(vals)) if vals else None


class RuntimeStats:
    def __init__(self):
        self._lock = threading.Lock()
        self.started = time.time()
        self.llm, self.tts, self.stt, self.vision = _Series(), _Series(), _Series(), _Series()
        self.llm_in = self.llm_out = 0
        self.vision_in = self.vision_out = 0
        self.tts_chars = 0
        self.tts_audio_s = 0.0
        self.stt_audio_s = 0.0
        self.llm_active = 0
        self.llm_info = {"method": "", "model": ""}
        self.context = {"used": 0, "max": 0, "breakdown": {}, "character": "", "t": 0}

    # ------------------------------------------------------------------ recording
    def llm_begin(self):
        with self._lock:
            self.llm_active += 1

    def llm_end(self, method, model, prompt_tokens, out_tokens, ttft, duration, ok=True, real=None):
        """``real``: usage/timings reported by the server (exact numbers) - replaces the estimates."""
        decode = max(duration - (ttft or 0), 0.001)
        tps = (out_tokens / decode) if out_tokens else None
        prefill = (prompt_tokens / ttft) if ttft and prompt_tokens else None
        exact = False
        if real:
            if real.get("prompt_tokens"):
                prompt_tokens, exact = int(real["prompt_tokens"]), True
            if real.get("completion_tokens"):
                out_tokens, exact = int(real["completion_tokens"]), True
                tps = out_tokens / decode if decode > 0.05 else tps
            if real.get("predicted_per_second"):
                tps, exact = float(real["predicted_per_second"]), True
            if real.get("prompt_per_second"):
                prefill = float(real["prompt_per_second"])
        item = {
            "t": time.time(), "in": prompt_tokens, "out": out_tokens, "ttft": ttft, "dur": duration,
            "tps": tps, "prefill_tps": prefill, "exact": exact,
        }
        with self._lock:
            self.llm_active = max(0, self.llm_active - 1)
            self.llm_in += prompt_tokens
            self.llm_out += out_tokens
            self.llm_info = {"method": method or "", "model": model or ""}
            self.llm.add(item, ok)

    def record_tts(self, engine, chars, gen_s, audio_s, ok=True):
        item = {
            "t": time.time(), "engine": engine, "chars": chars, "gen": gen_s, "audio": audio_s,
            "rtf": (gen_s / audio_s) if audio_s else None,
        }
        with self._lock:
            self.tts_chars += chars
            self.tts_audio_s += float(audio_s or 0.0)
            self.tts.add(item, ok)

    def record_stt(self, audio_s, proc_s, chars, ok=True):
        item = {"t": time.time(), "audio": audio_s, "proc": proc_s, "chars": chars,
                "rtf": (proc_s / audio_s) if audio_s else None}
        with self._lock:
            self.stt_audio_s += audio_s
            self.stt.add(item, ok)

    def record_vision(self, prompt_tokens, out_tokens, seconds, ok=True):
        item = {"t": time.time(), "in": prompt_tokens, "out": out_tokens, "dur": seconds,
                "tps": (out_tokens / seconds) if out_tokens and seconds else None}
        with self._lock:
            self.vision_in += prompt_tokens or 0
            self.vision_out += out_tokens or 0
            self.vision.add(item, ok)

    # exact usage captured from OpenAI-compatible streams (see install_openai_hook)
    pending_usage: dict = {}

    def take_usage(self) -> dict:
        with self._lock:
            data, self.pending_usage = dict(self.pending_usage), {}
        return data

    def put_usage(self, data: dict):
        with self._lock:
            self.pending_usage.update({k: v for k, v in data.items() if v is not None})

    def set_context(self, used, maximum, breakdown, character=""):
        with self._lock:
            self.context = {"used": int(used), "max": int(maximum), "breakdown": dict(breakdown or {}),
                            "character": character, "t": time.time()}

    # ------------------------------------------------------------------ reading
    def snapshot(self) -> dict:
        with self._lock:
            def pack(series, keys):
                return {
                    "count": series.count, "errors": series.errors, "last": series.last,
                    "avg": {k: series.avg(k) for k in keys},
                }
            return {
                "uptime": int(time.time() - self.started),
                "llm": {**pack(self.llm, ("tps", "ttft", "dur", "prefill_tps", "out", "in")),
                        "hist": [i["tps"] for i in self.llm.items if i.get("tps") is not None],
                        "total_in": self.llm_in, "total_out": self.llm_out, "active": self.llm_active,
                        **self.llm_info},
                "tts": {**pack(self.tts, ("gen", "audio", "rtf", "chars")), "total_chars": self.tts_chars, "total_audio": round(self.tts_audio_s, 1)},
                "stt": {**pack(self.stt, ("proc", "audio", "rtf")), "total_audio": self.stt_audio_s},
                "vision": {**pack(self.vision, ("tps", "dur", "in", "out")),
                           "total_in": self.vision_in, "total_out": self.vision_out},
                "context": dict(self.context),
            }


stats = RuntimeStats()


def _inspect_chunk(chunk):
    """Pulls usage / llama.cpp timings out of a streamed chunk or a full response (never raises)."""
    try:
        found = {}
        usage = getattr(chunk, "usage", None)
        if usage is not None:
            found["prompt_tokens"] = getattr(usage, "prompt_tokens", None)
            found["completion_tokens"] = getattr(usage, "completion_tokens", None)
        extra = getattr(chunk, "model_extra", None) or {}
        timings = extra.get("timings") if isinstance(extra, dict) else None
        if isinstance(timings, dict):
            found["predicted_per_second"] = timings.get("predicted_per_second")
            found["prompt_per_second"] = timings.get("prompt_per_second")
            found.setdefault("prompt_tokens", timings.get("prompt_n"))
            found.setdefault("completion_tokens", timings.get("predicted_n"))
        if any(v for v in found.values()):
            stats.put_usage(found)
    except Exception:
        pass


class _UsageTap:
    """Async-iterable proxy around an OpenAI AsyncStream that records usage/timings."""

    def __init__(self, inner):
        self._inner = inner

    def __getattr__(self, name):
        return getattr(self._inner, name)

    def __aiter__(self):
        return self._gen()

    async def _gen(self):
        async for chunk in self._inner:
            _inspect_chunk(chunk)
            yield chunk

    async def __aenter__(self):
        await self._inner.__aenter__()
        return self

    async def __aexit__(self, *exc):
        return await self._inner.__aexit__(*exc)


def install_openai_hook():
    """Hooks chat.completions.create once: exact usage for every OpenAI-SDK based provider (local llama.cpp,
    OpenAI, OpenRouter, DeepSeek, Grok, Qwen, Z.AI ...). Local servers also get stream_options.include_usage."""
    try:
        from openai.resources.chat.completions import AsyncCompletions
    except Exception:
        return
    if getattr(AsyncCompletions.create, "_yume_hooked", False):
        return
    original = AsyncCompletions.create

    async def create(self, *args, **kwargs):
        streaming = bool(kwargs.get("stream"))
        try:
            base = str(getattr(getattr(self, "_client", None), "base_url", "") or "")
            if streaming and ("127.0.0.1" in base or "localhost" in base) and "stream_options" not in kwargs:
                kwargs["stream_options"] = {"include_usage": True}
        except Exception:
            pass
        result = await original(self, *args, **kwargs)
        if streaming:
            return _UsageTap(result)
        _inspect_chunk(result)
        return result

    create._yume_hooked = True
    AsyncCompletions.create = create
