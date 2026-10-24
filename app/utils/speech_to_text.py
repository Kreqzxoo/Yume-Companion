import os
import sys
import torch
import time
import pyaudio
import logging
import queue
import re
from collections import deque
import numpy as np

from app.utils.voice_runtime import (
    load_main_settings, should_suppress_microphone, WakeWordGate,
    aec_library_available, get_playback_reference,
)

from PyQt6.QtCore import QThread, pyqtSignal
from faster_whisper import WhisperModel

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

logger = logging.getLogger("Speech-To-Text Module")

# Phrases Whisper invents on silence / noise (subtitle credits, "thanks for watching", sound descriptions ...).
# Distinctive ones are removed wherever they appear; the short generic ones only when they ARE the whole utterance - otherwise a real
# sentence that merely contains "Thank you." or "перевод" would be thrown away.
HALLUCINATION_PHRASES = [
    # Russian (original list)
    "субтитры создавал", "редактор субтитров", "спасибо за просмотр", "подписывайтесь на канал", "продолжение следует",
    "субтитры", "а. семенов", "перевод", "озвучка", "thank you.", "веселая музыка", "спокойная музыка", "грустная мелодия",
    "лирическая музыка", "динамичная музыка", "таинственная музыка", "торжественная музыка", "интригующая музыка",
    "напряженная музыка", "печальная музыка", "тревожная музыка", "музыкальная заставка", "перестрелка", "гудок поезда",
    "рев мотора", "шум двигателя", "сигнал автомобиля", "лай собак", "пес лает", "кашель", "выстрелы", "шум дождя", "песня",
    "по громкоговорителю", "взрыв", "шум мотора", "плеск воды", "гудок автомобиля", "лай собаки", "по тв.", "аплодисменты",
    "городской шум", "полиция", "городской гудок", "сигнал машины", "смех", "стук в дверь", "полицейская сирена",
    "звонок в дверь", "спасибо за субтитры!", "субтитры добавил dimatorzok", "субтитры подогнал",
    "смотрите продолжение во второй части видео", "смотрите продолжение в следующей части", "продолжение следует...",
    "подпишись на канал", "подпишись!", "подпишись", "девушки отдыхают...",
    # German
    "untertitel der amara.org", "untertitel im auftrag des zdf", "untertitelung des zdf", "untertitel von", "untertitelung",
    "vielen dank fürs zuschauen", "vielen dank für's zuschauen", "danke fürs zuschauen", "bis zum nächsten mal", "swr 2020",
    "amara.org", "musik", "applaus", "gelächter", "vielen dank.", "danke schön.",
    # English
    "thanks for watching", "thank you for watching", "please subscribe", "like and subscribe", "subtitles by", "subtitled by",
    "transcription by", "www.", "you", "bye.", "bye-bye.", "♪", "[music]", "(music)", "[applause]", "(applause)",
]
_MIN_SUBSTRING = 14      # phrases at least this long are matched anywhere in the text, shorter ones only as the whole utterance


def _norm_phrase(s: str) -> str:
    return re.sub(r"[\s.!?,;:…\-\"'“”„«»()\[\]♪]+", " ", str(s).casefold()).strip()


def looks_like_hallucination(text: str, confidence: float = None) -> bool:
    """`confidence` = best segment's no-speech-free score (1 = sure it was speech); None when unknown.
    Generic short phrases ("Thank you", "Vielen Dank") are real speech sometimes, so they are only dropped when Whisper itself was unsure."""
    low = str(text).casefold()
    whole = _norm_phrase(text)
    for phrase in HALLUCINATION_PHRASES:
        if len(phrase) >= _MIN_SUBSTRING:
            if phrase in low:
                return True
        elif whole and whole == _norm_phrase(phrase):
            return confidence is None or confidence < 0.55
    return False


def usable_segments(segments):
    """Drops what Whisper itself marks as probably not speech or as a repetition loop; returns (text, confidence 0..1)."""
    kept, scores = [], []
    for s in segments:
        no_speech = float(getattr(s, "no_speech_prob", 0.0) or 0.0)
        logprob = float(getattr(s, "avg_logprob", 0.0) or 0.0)
        ratio = float(getattr(s, "compression_ratio", 1.0) or 1.0)
        if (no_speech > 0.6 and logprob < -0.8) or ratio > 2.4:
            continue
        kept.append(s.text)
        scores.append(max(0.0, min(1.0, (1.0 - no_speech) * min(1.0, max(0.0, 1.0 + logprob)))))
    return "".join(kept).strip(), (max(scores) if scores else 0.0)


class AudioInputWorker(QThread):
    voice_detected_signal = pyqtSignal()
    volume_signal = pyqtSignal(float)
    silence_detected_signal = pyqtSignal()
    audio_packet_ready = pyqtSignal(bytes)

    def __init__(self, input_device_index=None):
        super().__init__()
        self.input_device_index = input_device_index
        self.is_running = True
        
        self.SAMPLE_RATE = 16000
        self.CHUNK_SIZE = 512
        
        logger.info("Loading Silero VAD model...")
        try:
            silero_local_path = os.path.join(os.getcwd(), "app", "utils", "speech-to-text", "silero-vad")

            if os.path.exists(silero_local_path):
                self.model, utils = torch.hub.load(repo_or_dir=silero_local_path,
                                                   model='silero_vad',
                                                   source='local',
                                                   force_reload=False)
            else:
                self.model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad',
                                                   model='silero_vad',
                                                   force_reload=False,
                                                   trust_repo=True)
            self.get_speech_timestamps, _, _, _, _ = utils
            logger.info("Silero VAD Loaded successfully!")
        except Exception as e:
            logger.error(f"Error loading Silero VAD: {e}")
            self.model = None

        voice_settings = load_main_settings()
        self.echo_mode = str(voice_settings.get("anti_echo_mode", "half_duplex") or "half_duplex").lower()
        self.echo_tail_ms = int(voice_settings.get("anti_echo_tail_ms", 700))
        self.aec_processor = None
        if self.echo_mode in {"aec", "webrtc_aec", "full_duplex_aec"}:
            try:
                if not aec_library_available():
                    raise ImportError("pywebrtc-audio is not installed in the active SoW environment")
                from pywebrtc_audio import AudioProcessor
                self.aec_processor = AudioProcessor(
                    sample_rate=self.SAMPLE_RATE,
                    num_channels=1,
                    echo_cancellation=True,
                    noise_suppression=bool(voice_settings.get("aec_noise_suppression", True)),
                    auto_gain_control=False,
                    stream_delay_ms=max(0, min(250, int(voice_settings.get("aec_stream_delay_ms", 60) or 0))),
                )
                logger.info("WebRTC AEC3 microphone processor initialized; full-duplex reference audio is enabled.")
            except Exception as exc:
                self.aec_processor = None
                self.echo_mode = "half_duplex"
                logger.warning("AEC3 unavailable; using half-duplex echo guard: %s", exc)
        self.silence_ms = max(200, min(int(voice_settings.get("voice_silence_ms", 760)), 2500))
        self.preroll_ms = max(0, min(int(voice_settings.get("voice_preroll_ms", 192)), 500))
        chunk_ms = self.CHUNK_SIZE / self.SAMPLE_RATE * 1000.0
        self.silence_threshold = max(1, int(self.silence_ms / chunk_ms))
        self.preroll_chunks = max(0, int(self.preroll_ms / chunk_ms))
        self.frames = []
        # WebRTC AEC3 works in continuous 10 ms frames (160 samples at 16 kHz).
        # Keep near/far buffers aligned across PyAudio's 512-sample reads so each
        # AEC processor call advances DSP state by exactly the consumed time.
        self._aec_near_pending = np.zeros(0, dtype=np.float32)
        self._aec_far_pending = np.zeros(0, dtype=np.float32)
        self._aec_cleaned_pending = np.zeros(0, dtype=np.float32)
        self.voice_threshold = 0.5

    def run(self):
        logger.info("Audio Worker Thread Started")
        p = pyaudio.PyAudio()

        numdevices = p.get_device_count()
        logger.info(f"Found {numdevices} audio devices total:")
        found_device = False
        
        for i in range(0, numdevices):
            try:
                device_info = p.get_device_info_by_index(i)
                if device_info.get('maxInputChannels') > 0:
                    name = device_info.get('name')
                    logger.info(f"   Device ID {i}: {name}")
                    if self.input_device_index == i:
                        found_device = True
            except Exception:
                continue

        if self.input_device_index is not None and not found_device:
            logger.warning(f"Device ID {self.input_device_index} not found. Using Default.")
            self.input_device_index = None

        stream = None
        try:
            stream = p.open(format=pyaudio.paInt16,
                            channels=1,
                            rate=self.SAMPLE_RATE,
                            input=True,
                            input_device_index=self.input_device_index,
                            frames_per_buffer=self.CHUNK_SIZE)
            logger.info(f"Microphone stream opened successfully! (Device ID: {self.input_device_index if self.input_device_index is not None else 'Default'})")
        except Exception as e:
            logger.error(f"Failed to open microphone: {e}")
            p.terminate()
            return

        speaking = False
        silence_chunks = 0
        pre_roll = deque(maxlen=max(1, self.preroll_chunks))

        while self.is_running:
            try:
                data = stream.read(self.CHUNK_SIZE, exception_on_overflow=False)

                audio_int16 = np.frombuffer(data, np.int16)
                # With AEC3 active, capture stays continuous while reference samples
                # are paired with each mic block. Process exact 10 ms frames (160 samples)
                # and rebuild the 512-sample Silero VAD frame from cleaned output.
                if self.aec_processor is not None:
                    if should_suppress_microphone(self.echo_mode, self.echo_tail_ms):
                        speaking = False
                        silence_chunks = 0
                        self.frames.clear()
                        pre_roll.clear()
                        self._aec_near_pending = np.zeros(0, dtype=np.float32)
                        self._aec_far_pending = np.zeros(0, dtype=np.float32)
                        self._aec_cleaned_pending = np.zeros(0, dtype=np.float32)
                        try:
                            self.aec_processor.reset()
                        except Exception:
                            pass
                        continue
                    try:
                        capture_start = time.monotonic() - (len(audio_int16) / float(self.SAMPLE_RATE))
                        near_float = audio_int16.astype(np.float32) / 32768.0
                        far_float = get_playback_reference(capture_start, len(audio_int16))
                        self._aec_near_pending = np.concatenate((self._aec_near_pending, near_float))
                        self._aec_far_pending = np.concatenate((self._aec_far_pending, far_float))
                        frame_samples = self.SAMPLE_RATE // 100  # 10 ms at 16 kHz = 160 samples
                        while self._aec_near_pending.size >= frame_samples and self._aec_far_pending.size >= frame_samples:
                            near_frame = self._aec_near_pending[:frame_samples]
                            far_frame = self._aec_far_pending[:frame_samples]
                            cleaned_frame = self.aec_processor.process(near_frame, far_frame)
                            self._aec_cleaned_pending = np.concatenate((self._aec_cleaned_pending, np.asarray(cleaned_frame, dtype=np.float32)))
                            self._aec_near_pending = self._aec_near_pending[frame_samples:]
                            self._aec_far_pending = self._aec_far_pending[frame_samples:]
                        # Silero VAD is configured for 512-sample frames; keep reading
                        # until enough continuous AEC-cleaned samples are available.
                        if self._aec_cleaned_pending.size < self.CHUNK_SIZE:
                            continue
                        audio_float32 = self._aec_cleaned_pending[:self.CHUNK_SIZE].copy()
                        self._aec_cleaned_pending = self._aec_cleaned_pending[self.CHUNK_SIZE:]
                        audio_int16 = np.clip(audio_float32 * 32768.0, -32768, 32767).astype(np.int16)
                    except Exception as exc:
                        logger.exception("AEC3 processing failed; switching microphone capture to half-duplex fallback: %s", exc)
                        self.aec_processor = None
                        self.echo_mode = "half_duplex"
                        self._aec_near_pending = np.zeros(0, dtype=np.float32)
                        self._aec_far_pending = np.zeros(0, dtype=np.float32)
                        self._aec_cleaned_pending = np.zeros(0, dtype=np.float32)
                        speaking = False
                        silence_chunks = 0
                        self.frames.clear()
                        pre_roll.clear()
                        continue
                else:
                    if should_suppress_microphone(self.echo_mode, self.echo_tail_ms):
                        speaking = False
                        silence_chunks = 0
                        self.frames.clear()
                        pre_roll.clear()
                        continue
                    audio_float32 = audio_int16.astype(np.float32) / 32768.0

                # audio_float32 is either the raw normalized mic frame or the AEC3 output.
                audio_int16 = np.clip(audio_float32 * 32768.0, -32768, 32767).astype(np.int16)
                data = audio_int16.tobytes()
                tensor = torch.from_numpy(audio_float32)
                speech_prob = self.model(tensor, self.SAMPLE_RATE).item() if self.model else 0.0
                rms = float(np.sqrt(np.mean(audio_float32 ** 2)))
                volume = min(1.0, rms * 22.0)
                self.volume_signal.emit(volume)

                # A short pre-roll reduces clipped initial consonants because
                # VAD normally confirms speech only after the first audio frame.
                pre_roll.append(data)
                if speech_prob > self.voice_threshold:
                    if not speaking:
                        speaking = True
                        self.frames = list(pre_roll)
                        self.voice_detected_signal.emit()
                        logger.debug("User started speaking (VAD probability %.2f)", speech_prob)
                    else:
                        self.frames.append(data)
                    silence_chunks = 0
                elif speaking:
                    self.frames.append(data)
                    silence_chunks += 1
                    if silence_chunks >= self.silence_threshold:
                        speaking = False
                        self.silence_detected_signal.emit()
                        logger.info("User stopped. Sending %s audio frames.", len(self.frames))
                        full_audio = b"".join(self.frames)
                        self.audio_packet_ready.emit(full_audio)
                        self.frames = []
                        silence_chunks = 0
                        pre_roll.clear()

            except Exception as e:
                logger.error(f"Error in audio loop: {e}")
                break

        logger.info("Stopping Audio Stream...")
        if stream:
            stream.stop_stream()
            stream.close()
        p.terminate()
        logger.info("Audio Worker Stopped cleanly")

    def stop(self):
        self.is_running = False
        self.wait()

class STTWorker(QThread):
    text_ready_signal = pyqtSignal(str)
    status_signal = pyqtSignal(str)

    def __init__(self, model_size="small", device="cuda", compute_type="float16"):
        super().__init__()
        self.queue = queue.Queue()
        self.is_running = True
        
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        
        self.model = None
        self.voice_settings = load_main_settings()
        self.wake_word_gate = WakeWordGate(self.voice_settings)

    def load_model(self):
        if self.model is None:
            requested_device = str(self.device or "cuda").lower()
            device_index = 0
            backend = requested_device
            if requested_device.startswith("cuda:"):
                backend, _, raw_index = requested_device.partition(":")
                try:
                    ids = [max(0, int(x)) for x in raw_index.split(",") if x.strip().isdigit()]
                    # several GPUs -> CTranslate2 replicas (parallel transcription); a single one stays an int
                    device_index = ids if len(ids) > 1 else (ids[0] if ids else 0)
                except ValueError:
                    device_index = 0
            elif requested_device.isdigit():
                backend, device_index = "cuda", int(requested_device)

            logger.info("Loading Faster-Whisper (%s) on %s%s...", self.model_size, backend,
                        f" device_index={device_index}" if backend == "cuda" else "")
            try:
                kwargs = {"device": backend, "compute_type": self.compute_type}
                if backend == "cuda":
                    kwargs["device_index"] = device_index
                self.model = WhisperModel(self.model_size, **kwargs)
                logger.info("Faster-Whisper loaded successfully.")
                self.status_signal.emit("Model Loaded")
            except Exception as e:
                logger.error("Error loading Whisper on %s (switching to CPU): %s", requested_device, e)
                self.device = "cpu"
                self.compute_type = "int8"
                self.model = WhisperModel(self.model_size, device="cpu", compute_type="int8")
                logger.info("Faster-Whisper loaded on CPU.")

    def add_audio(self, audio_bytes):
        if audio_bytes:
            try:
                self.queue.put_nowait(audio_bytes)
            except queue.Full:
                logger.warning("Whisper queue is full; dropping one audio packet.")

    def run(self):
        self.load_model()
        logger.info("STT Loop Started")
        hallucinations = HALLUCINATION_PHRASES

        while self.is_running:
            try:
                audio_bytes = self.queue.get(timeout=0.2)
            except queue.Empty:
                continue
            try:
                if not audio_bytes:
                    continue
                audio_np = np.frombuffer(audio_bytes, np.int16).flatten().astype(np.float32) / 32768.0
                import time as _time
                _t0 = _time.time()
                language = str(load_main_settings().get("stt_language", "auto") or "auto").strip().lower()
                segments, info = self.model.transcribe(audio_np, beam_size=5, language=None if language in ("", "auto") else language)
                full_text, confidence = usable_segments(segments)
                try:
                    from app.utils.runtime_stats import stats as _stats
                    _stats.record_stt(len(audio_np) / 16000.0, _time.time() - _t0, len(full_text))
                except Exception:
                    pass
                low = full_text.casefold()
                is_hallucination = bool(full_text) and looks_like_hallucination(full_text, confidence)
                if full_text and not is_hallucination and len(full_text) > 2:
                    gated_text = self.wake_word_gate.process(full_text)
                    if gated_text:
                        logger.info("Text Recognized: %s", gated_text)
                        self.text_ready_signal.emit(gated_text)
                    elif self.voice_settings.get("wake_word_enabled", False):
                        logger.debug("Speech ignored because the wake phrase was not detected.")
                else:
                    logger.debug("Empty audio fragment or likely hallucination ignored.")
            except Exception as e:
                logger.error("STT Error: %s", e, exc_info=True)
            finally:
                try:
                    self.queue.task_done()
                except Exception:
                    pass

        logger.info("STT Worker Stopped")

    def stop(self):
        logger.info("Signaling Whisper worker to stop...")
        self.is_running = False
        try:
            self.queue.put_nowait(b"")
        except Exception:
            pass
        self.quit()
        self.wait(4000)
