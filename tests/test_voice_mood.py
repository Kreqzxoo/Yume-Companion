"""Voice mood from loudness / pitch / tempo with synthetic 'speech' (offline). Temporary baseline file."""
import sys, os, tempfile, io, wave
sys.path.insert(0, '.')
import numpy as np
from pathlib import Path
from app.utils import voice_mood as vm, mood
tmp = Path(tempfile.mkdtemp())
vm.FILE = tmp / "base.json"; mood.LOG = tmp / "mood.json"
ok = True
def check(name, cond):
    global ok
    ok &= bool(cond); print(("ok  " if cond else "BAD ") + name)
rng = np.random.default_rng(1)
def speech(level=0.12, f0=150.0, wobble=0.08, rate=4.0, seconds=3.0):
    """harmonic 'voice' with a syllable rhythm: level = RMS, wobble = pitch movement, rate = syllables per second"""
    t = np.arange(int(vm.RATE * seconds)) / vm.RATE
    f = f0 * (1 + wobble * np.sin(2 * np.pi * 0.9 * t))
    phase = 2 * np.pi * np.cumsum(f) / vm.RATE
    sig = sum(np.sin(h * phase) / h for h in range(1, 6))
    env = 0.5 * (1 - np.cos(2 * np.pi * rate * t))                      # syllable bursts
    x = sig * env + 0.003 * rng.standard_normal(len(t))
    x *= level / max(np.sqrt((x[env > 0.3] ** 2).mean()), 1e-6)
    return (np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes()
f = vm.analyze(speech())
check("features: pitch near 150 Hz", f is not None and 120 < f["pitch"] < 185)
check("features: tempo grows with the speaking rate", vm.analyze(speech(rate=2.8))["rate"] < vm.analyze(speech(rate=5.6))["rate"])
check("too short / silent -> None", vm.analyze(speech(seconds=0.5)) is None and vm.analyze(np.zeros(48000, dtype=np.int16).tobytes()) is None)
# the usual voice: ten normal sentences with small variation
for i in range(10):
    check_label = vm.observe(speech(level=0.12 * (1 + 0.05 * (i % 3 - 1)), f0=150 * (1 + 0.02 * (i % 3 - 1)), wobble=0.08, rate=4.0))
check("no judgement while learning the baseline", check_label == "")
check("a normal sentence is neutral", vm.observe(speech()) == "")
check("quiet + slow + lower -> tired", vm.observe(speech(level=0.06, f0=140, wobble=0.08, rate=2.8)) == "tired")
check("loud + higher + faster -> stressed", vm.observe(speech(level=0.22, f0=180, wobble=0.08, rate=5.6)) == "stressed")
check("flat pitch + quieter -> sad", vm.observe(speech(level=0.09, f0=150, wobble=0.012, rate=4.0)) == "sad")
check("lively pitch + louder -> happy", vm.observe(speech(level=0.15, f0=150, wobble=0.22, rate=4.0)) == "happy")
# wav helper and the mood hint
buf = io.BytesIO()
with wave.open(buf, "wb") as w:
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(speech())
check("pcm_from_wav", len(vm.pcm_from_wav(buf.getvalue())) == len(speech()))
mood._state.update(mood="", t=0)
mood.from_voice("tired")
check("voice mood becomes a hint (and is counted)", "tired" in mood.hint_block("Was gibt es zu essen?").lower() or "tired" in mood.HINTS["tired"].lower() and mood.detect("Was gibt es zu essen?") == "tired")
print("ALL OK" if ok else "FAILED")
