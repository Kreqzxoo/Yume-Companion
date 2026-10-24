"""Voice runtime for WebRTC AEC3, reference-aligned playback, and wake-word gating.

When pywebrtc-audio is available and AEC is selected, output audio is played
through a reference-aware PortAudio stream and aligned reference samples are
passed to AudioProcessor for microphone cleanup. If AEC is unavailable or
initialization fails, callers should use the half-duplex fallback.
"""
from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger("Voice Runtime")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SETTINGS_PATH = PROJECT_ROOT / "app" / "configuration" / "settings.json"
_PLAYBACK_ACTIVE = threading.Event()
_AEC_REFERENCE_READY = threading.Event()
_LAST_PLAYBACK_END = 0.0
_PLAYBACK_LOCK = threading.RLock()
_REFERENCE_AUDIO_16K: np.ndarray | None = None
_REFERENCE_START_MONOTONIC: float | None = None

DEFAULTS = {
    "anti_echo_mode": "half_duplex",
    "anti_echo_tail_ms": 700,
    "aec_stream_delay_ms": 60,
    "aec_noise_suppression": True,
    "wake_word_enabled": False,
    "wake_word": "Yume",
    "wake_word_timeout_sec": 30,
    "voice_silence_ms": 760,
    "voice_preroll_ms": 192,
    "whisper_device": "cuda",
    "whisper_gpu_index": 0,
    "llm_cuda_gpu_indices": "0",
    "tts_chunk_max_chars": 280,
    "tts_chunk_pause_ms": 140,
    "lipsync_smoothing": True,
}


def load_main_settings() -> dict:
    """Read settings without failing startup if settings.json is malformed."""
    try:
        with SETTINGS_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
        main = data.get("main_settings", {}) if isinstance(data, dict) else {}
        result = dict(DEFAULTS)
        result.update({k: v for k, v in main.items() if k in DEFAULTS})
        return result
    except Exception as exc:
        logger.debug("Using voice defaults because settings could not be read: %s", exc)
        return dict(DEFAULTS)


def _mono_resampled_reference(data: Any, sample_rate: int) -> np.ndarray:
    """Convert output audio to mono float32 at 16kHz for AEC reference use."""
    audio = np.asarray(data, dtype=np.float32)
    if audio.ndim > 1:
        audio = np.mean(audio, axis=1, dtype=np.float32)
    audio = np.nan_to_num(audio.reshape(-1), copy=False)
    if not audio.size or sample_rate <= 0:
        return np.zeros(0, dtype=np.float32)
    if int(sample_rate) == 16000:
        return np.ascontiguousarray(audio, dtype=np.float32)
    try:
        from scipy.signal import resample_poly
        from math import gcd
        divisor = gcd(int(sample_rate), 16000)
        converted = resample_poly(audio, 16000 // divisor, int(sample_rate) // divisor)
        return np.ascontiguousarray(converted, dtype=np.float32)
    except Exception:
        # Rare fallback if SciPy is absent: linear interpolation. The source is
        # prepared before opening the output stream, never inside its callback.
        old_times = np.arange(audio.size, dtype=np.float64) / float(sample_rate)
        new_count = max(1, int(round(audio.size * 16000.0 / float(sample_rate))))
        new_times = np.arange(new_count, dtype=np.float64) / 16000.0
        return np.ascontiguousarray(np.interp(new_times, old_times, audio), dtype=np.float32)


def _prepare_playback_reference(data: Any, sample_rate: int) -> None:
    global _REFERENCE_AUDIO_16K, _REFERENCE_START_MONOTONIC
    audio_ref = _mono_resampled_reference(data, int(sample_rate))
    with _PLAYBACK_LOCK:
        _REFERENCE_AUDIO_16K = audio_ref
        _REFERENCE_START_MONOTONIC = None
        _AEC_REFERENCE_READY.clear()


def _set_reference_start(start_monotonic: float) -> None:
    global _REFERENCE_START_MONOTONIC
    with _PLAYBACK_LOCK:
        _REFERENCE_START_MONOTONIC = float(start_monotonic)
        _AEC_REFERENCE_READY.set()


def get_playback_reference(capture_start_monotonic: float, frame_count: int) -> np.ndarray:
    """Return the speaker-reference samples corresponding to a mic time window.

    Output is always mono float32, 16kHz, exactly ``frame_count`` samples long.
    Samples outside the active playback interval are zero-filled. The AEC's
    configurable stream-delay hint handles acoustic/device delay beyond this
    wall-clock alignment.
    """
    result = np.zeros(max(0, int(frame_count)), dtype=np.float32)
    if not result.size:
        return result
    with _PLAYBACK_LOCK:
        reference = _REFERENCE_AUDIO_16K
        start_time = _REFERENCE_START_MONOTONIC
        if reference is None or start_time is None or not reference.size:
            return result
        start_index = int(round((float(capture_start_monotonic) - start_time) * 16000.0))
        end_index = start_index + result.size
        src_start = max(0, start_index)
        src_end = min(reference.size, end_index)
        if src_end <= src_start:
            return result
        dst_start = src_start - start_index
        dst_end = dst_start + (src_end - src_start)
        result[dst_start:dst_end] = reference[src_start:src_end]
    return result


def aec_library_available() -> bool:
    """Return whether the optional WebRTC AEC extension can be imported."""
    try:
        from pywebrtc_audio import AudioProcessor  # noqa: F401
        return True
    except Exception:
        return False


def set_audio_playback_active(active: bool) -> None:
    """Mark known application playback for half-duplex/fallback behavior."""
    global _LAST_PLAYBACK_END
    if active:
        _PLAYBACK_ACTIVE.set()
        _AEC_REFERENCE_READY.clear()
    else:
        _PLAYBACK_ACTIVE.clear()
        _AEC_REFERENCE_READY.clear()
        with _PLAYBACK_LOCK:
            _LAST_PLAYBACK_END = time.monotonic()


def should_suppress_microphone(mode: str | None = None, tail_ms: int | None = None) -> bool:
    """Return whether microphone audio should be gated while app audio plays.

    In AEC mode, the mic stays open once the matching output-reference stream is
    ready. While that reference is not ready (first audio callback / failed
    output stream), gate the mic briefly to avoid an unreferenced feedback loop.
    """
    settings = load_main_settings() if mode is None or tail_ms is None else None
    mode = (mode if mode is not None else settings["anti_echo_mode"]) or "off"
    normalized = mode.lower()
    if normalized in AEC_MODES:
        if aec_library_available():
            # Only gate during the short startup window before the speaker-reference
            # stream starts. During playback, cleaned microphone frames go through AEC3.
            return _PLAYBACK_ACTIVE.is_set() and not _AEC_REFERENCE_READY.is_set()
        # Package/runtime unavailable: preserve safety with the real half-duplex fallback.
        normalized = "half_duplex"
    if normalized not in {"half_duplex", "half-duplex", "speaker_guard"}:
        return False
    if _PLAYBACK_ACTIVE.is_set():
        return True
    if tail_ms is None:
        tail_ms = settings["anti_echo_tail_ms"]
    try:
        tail_seconds = max(0, min(int(tail_ms), 3000)) / 1000.0
    except (TypeError, ValueError):
        tail_seconds = 0.7
    with _PLAYBACK_LOCK:
        ended_at = _LAST_PLAYBACK_END
    return ended_at > 0 and (time.monotonic() - ended_at) < tail_seconds


class ReferencedAudioPlayback:
    """Play audio through PortAudio and expose its actual samples as AEC far-end.

    The reference clock is anchored to PortAudio's outputBufferDacTime when
    available, rather than to TTS generation time (which can be much earlier).
    """
    def __init__(self, data: Any, sample_rate: int, device: int | None = None):
        import sounddevice as sd

        self.sd = sd
        self.data = np.asarray(data, dtype=np.float32)
        if self.data.ndim == 1:
            self.channels = 1
        elif self.data.ndim == 2:
            self.channels = int(self.data.shape[1])
        else:
            raise ValueError("Audio playback data must be mono or multi-channel samples")
        if self.data.shape[0] == 0:
            raise ValueError("Audio playback data is empty")
        self.sample_rate = int(sample_rate)
        self.device = device
        self.position = 0
        self.started = False
        self.finished = threading.Event()
        # Clear readiness from a previous segment before publishing this new
        # segment's reference. Readiness is set by the first actual output frame.
        set_audio_playback_active(True)
        _prepare_playback_reference(self.data, self.sample_rate)
        self.stream = sd.OutputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype="float32",
            device=self.device,
            callback=self._callback,
            finished_callback=self._finished_callback,
        )
        try:
            self.stream.start()
        except Exception:
            try:
                self.stream.close()
            finally:
                set_audio_playback_active(False)
            raise

    def _callback(self, outdata, frames, time_info, status):
        if status:
            logger.debug("Audio output callback status: %s", status)
        outdata.fill(0)
        available = max(0, self.data.shape[0] - self.position)
        copied = min(int(frames), available)
        if copied:
            chunk = self.data[self.position:self.position + copied]
            if self.channels == 1 and chunk.ndim == 1:
                # sounddevice callback output buffers are always (frames, channels),
                # while sf.read commonly returns mono audio as (frames,).
                outdata[:copied, 0] = chunk
            else:
                outdata[:copied] = chunk
            if not self.started:
                self.started = True
                start = time.monotonic()
                try:
                    dac = float(time_info.outputBufferDacTime)
                    current = float(time_info.currentTime)
                    start += dac - current
                except Exception:
                    # The callback timestamp is a fallback; stream delay remains
                    # configurable and can be calibrated by the user.
                    pass
                _set_reference_start(start)
            self.position += copied
        if self.position >= self.data.shape[0]:
            # Do not signal completion here: these samples have only been handed
            # to PortAudio. The device may still have buffered audio to play.
            raise self.sd.CallbackStop

    def _finished_callback(self):
        # PortAudio calls this after the output stream has drained. Waiting on
        # this event (not on the last callback) prevents the final phoneme from
        # being cut off when the caller closes/stops the stream.
        set_audio_playback_active(False)
        self.finished.set()

    def wait(self, timeout: float | None = None) -> bool:
        """Wait until PortAudio has finished the audio stream."""
        completed = self.finished.wait(timeout)
        if completed:
            # Give PortAudio a moment to deliver its finished callback.
            time.sleep(0.01)
        return completed

    def stop(self) -> None:
        try:
            if self.stream.active:
                self.stream.stop()
        except Exception:
            pass
        try:
            self.stream.close()
        except Exception:
            pass
        self.finished.set()
        set_audio_playback_active(False)


def start_referenced_playback(data: Any, sample_rate: int, device: int | None = None) -> ReferencedAudioPlayback:
    """Start app audio playback and reference it for the WebRTC AEC pipeline."""
    return ReferencedAudioPlayback(data, sample_rate, device)


class WakeWordGate:
    """Transcript-level configurable wake-word gate with a short active window.

    This runs after Whisper transcription, so it works without a separate
    always-on wake-word model. The configured phrase is removed from the text
    before the assistant receives it.
    """
    def __init__(self, settings: dict | None = None):
        self.settings = dict(DEFAULTS)
        self.settings.update(settings or load_main_settings())
        self._awake_until = 0.0
        words = str(self.settings.get("wake_word", "Yume") or "Yume")
        self._words = [w.strip() for w in re.split(r"[,;]", words) if w.strip()]
        self._pattern = re.compile(
            r"(?<![\w])(?:" + "|".join(re.escape(w) for w in sorted(self._words, key=len, reverse=True)) + r")(?![\w])",
            re.IGNORECASE,
        ) if self._words else None

    def process(self, transcript: str) -> str | None:
        text = (transcript or "").strip()
        if not text:
            return None
        if not bool(self.settings.get("wake_word_enabled", False)):
            return text

        now = time.monotonic()
        timeout = self.settings.get("wake_word_timeout_sec", 30)
        try:
            timeout = max(5, min(int(timeout), 600))
        except (TypeError, ValueError):
            timeout = 30

        match = self._pattern.search(text) if self._pattern else None
        if now < self._awake_until:
            self._awake_until = now + timeout
            return text
        if not match:
            return None

        self._awake_until = now + timeout
        cleaned = self._pattern.sub(" ", text, count=1)
        cleaned = re.sub(r"^[\s,.:;—–-]+", "", cleaned).strip()
        logger.info("Wake phrase detected; assistant active for %s seconds", timeout)
        return cleaned or None


AEC_MODES = {"aec", "webrtc_aec", "full_duplex_aec"}


def start_audio_playback(data: Any, sample_rate: int, device: int | None = None):
    """Start audio output; in AEC mode expose the actual output as far-end reference.

    Returns a ReferencedAudioPlayback handle when AEC reference playback is active,
    otherwise None and uses sounddevice.play as the compatibility path.
    """
    import sounddevice as sd

    settings = load_main_settings()
    mode = str(settings.get("anti_echo_mode", "half_duplex") or "half_duplex").lower()
    if mode in AEC_MODES and aec_library_available():
        try:
            arr = np.asarray(data)
            # ReferenceAudioPlayback outputs float32 through its OutputStream; normalize
            # integer PCM first so the emitted waveform and reference share one scale.
            if np.issubdtype(arr.dtype, np.integer):
                peak = float(np.iinfo(arr.dtype).max) or 32767.0
                arr = arr.astype(np.float32) / peak
            else:
                arr = arr.astype(np.float32, copy=False)
            return start_referenced_playback(arr, int(sample_rate), device)
        except Exception:
            logger.exception("Could not start reference-aware AEC playback; using half-duplex-safe output")
    try:
        set_audio_playback_active(True)
        sd.play(data, samplerate=int(sample_rate), device=device)
        return None
    except Exception:
        set_audio_playback_active(False)
        raise


def finish_audio_playback(reference_handle=None, *, interrupted: bool = False, timeout: float = 5.0) -> None:
    """Finish managed audio playback, restoring the playback marker reliably."""
    import sounddevice as sd

    if reference_handle is not None:
        try:
            if interrupted:
                reference_handle.stop()
            else:
                reference_handle.wait(timeout=max(0.1, float(timeout)))
                reference_handle.stop()
        except Exception:
            logger.debug("Error closing reference-aware playback", exc_info=True)
        finally:
            set_audio_playback_active(False)
        return

    try:
        if interrupted:
            sd.stop()
        else:
            sd.wait()
    except Exception:
        logger.debug("Error finishing sounddevice playback", exc_info=True)
    finally:
        set_audio_playback_active(False)
