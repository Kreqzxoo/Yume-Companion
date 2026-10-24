"""Mood from the VOICE (experimental): loudness, pitch, pitch movement and speaking tempo of a sentence, compared with the user's own usual values.

* Only a handful of numbers per sentence are used; no recording is stored and nothing leaves the PC.
* The baseline ("how you usually sound") is learned from the user's own sentences (running average); judging starts after 10 sentences.
* It is a rough guess like a human noticing "you sound tired": it only colours the tone of the answers (via the mood hint) and is wrong sometimes.
"""
from __future__ import annotations

import json
import os
import threading
import wave
import io
from pathlib import Path

import numpy as np

FILE = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "YumeCompanion" / "voice_baseline.json"
_lock = threading.Lock()
RATE = 16000
MIN_SENTENCES = 10


def pcm_from_wav(data: bytes) -> bytes:
    """int16 mono 16 kHz PCM out of a WAV file (or the bytes themselves when it is raw PCM)."""
    if data[:4] == b"RIFF":
        try:
            with wave.open(io.BytesIO(data)) as w:
                frames = w.readframes(w.getnframes())
                if w.getnchannels() == 2:
                    arr = np.frombuffer(frames, dtype=np.int16).reshape(-1, 2).mean(axis=1).astype(np.int16)
                    frames = arr.tobytes()
                return frames
        except Exception:
            return b""
    return data


def analyze(pcm: bytes) -> dict | None:
    """{'rms', 'pitch', 'pitch_std', 'rate'} of the voiced part, or None when there is too little speech (< 1 s)."""
    x = np.frombuffer(pcm, dtype=np.int16).astype(np.float32) / 32768.0
    if len(x) < RATE:
        return None
    frame, hop = 480, 240
    n = (len(x) - frame) // hop
    if n < 20:
        return None
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    frames = x[idx]
    rms = np.sqrt((frames ** 2).mean(axis=1))
    thr = max(0.02, 0.3 * float(np.percentile(rms, 90)))
    voiced = rms > thr
    if voiced.sum() < 20:
        return None
    pitches = []
    lo, hi = RATE // 400, RATE // 70                     # 70 - 400 Hz
    for f in frames[voiced][::2]:
        f = f - f.mean()
        ac = np.correlate(f, f, mode="full")[len(f) - 1:]
        if ac[0] <= 0:
            continue
        seg = ac[lo:hi]
        k = int(np.argmax(seg))
        if seg[k] / ac[0] > 0.35:                        # clearly periodic = voiced speech
            pitches.append(RATE / (lo + k))
    if len(pitches) < 10:
        return None
    semitones = 12 * np.log2(np.array(pitches) / 100.0)
    env = np.convolve(rms, np.ones(5) / 5, mode="same")
    peaks = int(((env[1:-1] > env[:-2]) & (env[1:-1] >= env[2:]) & (env[1:-1] > thr * 1.3)).sum())
    seconds_voiced = float(voiced.sum()) * hop / RATE
    return {"rms": float(rms[voiced].mean()), "pitch": float(np.median(pitches)), "pitch_std": float(semitones.std()), "rate": peaks / max(0.5, seconds_voiced)}


def _load() -> dict:
    try:
        return json.loads(FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _save(d: dict):
    try:
        FILE.parent.mkdir(parents=True, exist_ok=True)
        FILE.write_text(json.dumps(d), encoding="utf-8")
    except OSError:
        pass


def classify(f: dict, base: dict) -> str:
    """'tired' | 'stressed' | 'sad' | 'happy' | '' relative to the user's usual voice."""
    r = f["rms"] / max(base["rms"], 1e-6)
    p = f["pitch"] / max(base["pitch"], 1e-6)
    ps = f["pitch_std"] / max(base["pitch_std"], 1e-6)
    t = f["rate"] / max(base["rate"], 1e-6)
    if r > 1.35 and (p > 1.1 or t > 1.2):
        return "stressed"
    if r < 0.7 and t < 0.85 and p < 1.03:
        return "tired"
    if ps < 0.7 and r < 0.85:
        return "sad"
    if ps > 1.4 and r > 1.1:
        return "happy"
    return ""


def observe(pcm: bytes) -> str:
    """Looks at one sentence, updates the user's usual values and returns the mood when it is clear ('' otherwise)."""
    f = analyze(pcm)
    if f is None:
        return ""
    with _lock:
        d = _load()
        n = int(d.get("n", 0))
        label = classify(f, d["base"]) if n >= MIN_SENTENCES and "base" in d else ""
        # the usual values move slowly (running average); extreme sentences count less so one bad day does not become "normal"
        w = 1.0 / min(n + 1, 60)
        if label:
            w *= 0.4
        base = d.get("base", dict(f))
        for k in ("rms", "pitch", "pitch_std", "rate"):
            base[k] = base.get(k, f[k]) * (1 - w) + f[k] * w
        _save({"n": n + 1, "base": base})
    return label


def reset():
    try:
        FILE.unlink()
    except OSError:
        pass
