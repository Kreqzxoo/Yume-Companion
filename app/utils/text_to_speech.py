import os
import io
import re
import uuid
import queue
import time
import shutil
import torch
import asyncio
import logging
import edge_tts
import threading
import contextlib
import numpy as np
import soundfile as sf
import sounddevice as sd
from typing import Optional

from TTS.api import TTS
from kokoro import KPipeline
from pydub import AudioSegment
from elevenlabs.client import AsyncElevenLabs
from qwen_tts import Qwen3TTSModel

from PyQt6.QtCore import QThread, pyqtSignal

from app.configuration import configuration
from app.utils.voice_runtime import (
    load_main_settings, set_audio_playback_active, start_audio_playback, finish_audio_playback,
)
from rvc_python.infer import RVCInference

import torch.serialization
try:
    from fairseq.data.dictionary import Dictionary
    torch.serialization.add_safe_globals([Dictionary])
except ImportError:
    pass

logger = logging.getLogger("Text-To-Speech Module")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
CACHE_DIR = os.path.join(BASE_DIR, "app", "models", "hf_cache")

os.environ["HF_HOME"] = CACHE_DIR
os.environ["HUGGINGFACE_HUB_CACHE"] = CACHE_DIR

os.makedirs(CACHE_DIR, exist_ok=True)

def fix_rvc_sample_rate(file_path, base_file_path=None, target_sr=48000):
    if not file_path or not os.path.exists(file_path):
        return file_path
    try:
        data, sr = sf.read(file_path, dtype='float32')

        if sr != target_sr:
            if base_file_path and os.path.exists(base_file_path):
                data_base, sr_base = sf.read(base_file_path, dtype='float32')
                dur_base = len(data_base) / sr_base
                if dur_base > 0:
                    target_sr = int(round(len(data) / dur_base))

            sf.write(file_path, data, target_sr)
            logger.info(f"[RVC Fix] Corrected header from {sr} Hz to {target_sr} Hz")
    except Exception as e:
        logger.warning(f"Failed to fix RVC sample rate: {e}")
    return file_path

class ElevenLabs:
    def __init__(self):
        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_api = configuration.ConfigurationAPI()
        self.configuration_characters = configuration.ConfigurationCharacters()

        self.audio_cache = AudioSegment.empty()
        self.device_index = self.configuration_settings.get_main_setting("output_device_real_index")
        self.output_dir = "app/voices/elevenlabs_audio"
        os.makedirs(self.output_dir, exist_ok=True)

    async def generate_speech_with_elevenlabs(self, text, voice_id):
        try:
            self.eleven_labs_api = self.configuration_api.get_token("ELEVENLABS_API_TOKEN")
            self.eleven = AsyncElevenLabs(api_key=self.eleven_labs_api)

            audio_stream = await self.eleven.generate(
                text=text,
                voice=voice_id,
                model="eleven_multilingual_v2",
                stream=True
            )
            audio_data = b""
            async for chunk in audio_stream:
                audio_data += chunk

            audio_stream_io = io.BytesIO(audio_data)
            new_audio = await asyncio.to_thread(AudioSegment.from_file, audio_stream_io, format="mp3")
            self.audio_cache += new_audio
            await self.play_audio(new_audio)
        except Exception as e:
            logger.error(f"Error: {e}")

    async def generate_speech_with_elevenlabs_sow_system(self, text, voice_id):
        try:
            self.eleven_labs_api = self.configuration_api.get_token("ELEVENLABS_API_TOKEN")
            self.eleven = AsyncElevenLabs(api_key=self.eleven_labs_api)

            audio_stream = await self.eleven.generate(
                text=text,
                voice=voice_id,
                model="eleven_multilingual_v2",
                stream=True
            )
            audio_data = b""
            async for chunk in audio_stream:
                audio_data += chunk

            audio_stream_io = io.BytesIO(audio_data)
            new_audio = await asyncio.to_thread(AudioSegment.from_file, audio_stream_io, format="mp3")

            unique_id = uuid.uuid4().hex
            output_file = os.path.join(self.output_dir, f"output_{unique_id}.wav")
            await asyncio.to_thread(new_audio.export, output_file, format="wav")
            return output_file
        except Exception as e:
            logger.error(f"ElevenLabs Error: {e}")
            return None

    async def play_audio(self, audio):
        try:
            samples = np.asarray(audio.get_array_of_samples(), dtype=np.float32)
            peak = float(2 ** (8 * int(audio.sample_width) - 1))
            samples = samples / peak
            if int(getattr(audio, "channels", 1) or 1) > 1:
                samples = samples.reshape((-1, int(audio.channels)))
            sample_rate = audio.frame_rate
            def _play():
                handle = start_audio_playback(samples, sample_rate, self.device_index)
                finish_audio_playback(handle, timeout=max(5.0, len(samples) / float(sample_rate) + 3.0))
            await asyncio.to_thread(_play)
        except Exception as e:
            logger.error(f"Error: {e}")

    def clear_audio_cache(self):
        self.audio_cache = AudioSegment.empty()


class XTTSv2_SOW_System:
    def __init__(self):
        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_api = configuration.ConfigurationAPI()
        self.configuration_characters = configuration.ConfigurationCharacters()

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tts = None
        self.tts_loaded = False
        self.rvc = None
        self.rvc_loaded = False

    def _load_tts_sync(self):
        if not self.tts_loaded:
            try:
                self.tts = TTS(model_name='tts_models/multilingual/multi-dataset/xtts_v2', progress_bar=True).to(self.device)
                self.tts_loaded = True
            except Exception as e:
                raise RuntimeError(f"Failed to load TTS model: {e}")

    async def _load_rvc(self, f0up_key, index_rate, protect):
        if not self.rvc_loaded:
            logger.info("Loading RVC model...")
            try:
                def _init():
                    return RVCInference(
                        models_dir="assets/rvc_models",
                        device="cuda:0" if torch.cuda.is_available() else "cpu:0",
                        f0up_key=f0up_key, index_rate=index_rate, protect=protect
                    )
                self.rvc = await asyncio.to_thread(_init)
                self.rvc_loaded = True
                logger.info("RVC model loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading RVC model: {e}")
                raise RuntimeError("Failed to load RVC model.")

    async def generate_speech_with_xttsv2_sow_system(self, text=None, language=None, character_name=None):
        await asyncio.to_thread(self._load_tts_sync)

        configuration_data = self.configuration_characters.load_configuration()
        char_config = configuration_data["character_list"][character_name]

        xttsv2_voice_type = char_config["voice_type"]
        xttsv2_rvc_enabled = char_config["rvc_enabled"]
        xttsv2_rvc_file = char_config["rvc_file"]

        speaker_wav_map = {
            "Female Calm": "app/voices/calm_female.wav",
            "Female": "app/voices/female.wav",
            "Male": "app/voices/male.wav"
        }
        speaker_wav = speaker_wav_map.get(xttsv2_voice_type)
        if not speaker_wav:
            raise ValueError(f"Unknown voice type: {xttsv2_voice_type}")

        os.makedirs("app/voices/xttsv2_audio", exist_ok=True)
        unique_id = uuid.uuid4().hex
        base_output_file = f"app/voices/xttsv2_audio/output_{unique_id}.wav"

        await asyncio.to_thread(
            self.tts.tts_to_file,
            text=text,
            speaker_wav=speaker_wav,
            language=language,
            file_path=base_output_file
        )

        if xttsv2_rvc_enabled and xttsv2_rvc_file:
            f0up_key   = char_config.get("rvc_f0up_key",   0)
            index_rate = char_config.get("rvc_index_rate", 0.75)
            protect    = char_config.get("rvc_protect",    0.5)

            await self._load_rvc(f0up_key, index_rate, protect)

            model_name = os.path.splitext(os.path.basename(xttsv2_rvc_file))[0]
            rvc_output_file = f"app/voices/xttsv2_audio/output_rvc_{unique_id}.wav"

            rvc_params = (model_name, f0up_key, index_rate, protect)
            if getattr(self, "_current_rvc_params", None) != rvc_params:
                await asyncio.to_thread(self.rvc.load_model, model_name)
                self._current_rvc_params = rvc_params

            await asyncio.to_thread(self.rvc.infer_file, base_output_file, rvc_output_file)

            fix_rvc_sample_rate(rvc_output_file, base_output_file)

            try:
                await asyncio.to_thread(os.remove, base_output_file)
            except OSError as e:
                logger.warning(f"Could not remove temp file {base_output_file}: {e}")

            return rvc_output_file

        return base_output_file


class EdgeTTS:
    def __init__(self):
        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_api = configuration.ConfigurationAPI()
        self.configuration_characters = configuration.ConfigurationCharacters()

        self.rvc = None
        self.rvc_loaded = False
        self.output_dir = "app/voices/edge_tts_audio"
        os.makedirs(self.output_dir, exist_ok=True)
        self.device_index = self.configuration_settings.get_main_setting("output_device_real_index")

    async def _load_rvc(self, f0up_key, index_rate, protect):
        if not self.rvc_loaded:
            logger.info("Loading RVC model...")
            try:
                def _init():
                    return RVCInference(
                        models_dir="assets/rvc_models",
                        device="cuda:0" if torch.cuda.is_available() else "cpu:0",
                        f0up_key=f0up_key, index_rate=index_rate, protect=protect
                    )
                self.rvc = await asyncio.to_thread(_init)
                self.rvc_loaded = True
                logger.info("RVC model loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading RVC model: {e}")
                raise RuntimeError("Failed to load RVC model.")

    async def _convert_mp3_to_wav(self, mp3_file, wav_file):
        def _convert():
            audio = AudioSegment.from_mp3(mp3_file)
            audio.export(wav_file, format="wav")
        await asyncio.to_thread(_convert)

    async def _generate_base(self, text, character_name):
        configuration_data = self.configuration_characters.load_configuration()
        char_config = configuration_data["character_list"][character_name]

        voice_type = char_config["voice_type"]
        rvc_enabled = char_config["rvc_enabled"]
        rvc_file = char_config["rvc_file"]

        unique_id = uuid.uuid4().hex
        audio_file = os.path.join(self.output_dir, f"output_{unique_id}.mp3")
        wav_file = os.path.join(self.output_dir, f"output_{unique_id}.wav")

        try:
            communicate = edge_tts.Communicate(text, voice_type)
            await communicate.save(audio_file)
        except Exception as e:
            logger.error(f"Error when generating EdgeTTS audio: {e}")
            return None

        try:
            await self._convert_mp3_to_wav(audio_file, wav_file)
            await asyncio.to_thread(os.remove, audio_file)
        except Exception as e:
            logger.error(f"Error when converting MP3 to WAV: {e}")
            return None

        if rvc_enabled and rvc_file:
            f0up_key   = char_config.get("rvc_f0up_key",   0)
            index_rate = char_config.get("rvc_index_rate", 0.75)
            protect    = char_config.get("rvc_protect",    0.5)

            await self._load_rvc(f0up_key, index_rate, protect)
            model_name = os.path.splitext(os.path.basename(rvc_file))[0]
            rvc_output_file = os.path.join(self.output_dir, f"output_rvc_{unique_id}.wav")

            rvc_params = (model_name, f0up_key, index_rate, protect)
            if getattr(self, "_current_rvc_params", None) != rvc_params:
                await asyncio.to_thread(self.rvc.load_model, model_name)
                self._current_rvc_params = rvc_params

            await asyncio.to_thread(self.rvc.infer_file, wav_file, rvc_output_file)

            fix_rvc_sample_rate(rvc_output_file, wav_file)

            try:
                await asyncio.to_thread(os.remove, wav_file)
            except OSError as e:
                logger.warning(f"Could not remove temp file {wav_file}: {e}")

            return rvc_output_file

        return wav_file

    async def generate_speech_with_edge_tts(self, text, character_name):
        output_file = await self._generate_base(text, character_name)
        if output_file:
            await self.play_audio(file_path=output_file)

    async def generate_speech_with_edge_tts_sow_system(self, text, character_name):
        return await self._generate_base(text, character_name)

    async def play_audio(self, file_path):
        def _play():
            try:
                data, samplerate = sf.read(file_path, dtype='float32')
                handle = start_audio_playback(data, samplerate, self.device_index)
                finish_audio_playback(handle, timeout=max(5.0, len(data) / float(samplerate) + 3.0))
            except Exception as e:
                logger.error(f"Error: {e}")
        await asyncio.to_thread(_play)

    def stop_audio(self):
        sd.stop()


class KokoroTTS_SOW_System:
    def __init__(self):
        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_api = configuration.ConfigurationAPI()
        self.configuration_characters = configuration.ConfigurationCharacters()

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipeline = None
        self.tts_loaded = False
        self.rvc = None
        self.rvc_loaded = False

    async def _load_tts(self):
        if not self.tts_loaded:
            try:
                def _init():
                    return KPipeline(lang_code='a')
                self.pipeline = await asyncio.to_thread(_init)
                self.tts_loaded = True
            except Exception as e:
                raise RuntimeError(f"Failed to load TTS model: {e}")

    async def _load_rvc(self, f0up_key, index_rate, protect):
        if not self.rvc_loaded:
            logger.info("Loading RVC model...")
            try:
                def _init():
                    return RVCInference(
                        models_dir="assets/rvc_models",
                        device="cuda:0" if torch.cuda.is_available() else "cpu:0",
                        f0up_key=f0up_key, index_rate=index_rate, protect=protect
                    )
                self.rvc = await asyncio.to_thread(_init)
                self.rvc_loaded = True
                logger.info("RVC model loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading RVC model: {e}")
                raise RuntimeError("Failed to load RVC model.")

    async def generate_speech_with_kokoro(self, text, character_name):
        await self._load_tts()

        configuration_data = self.configuration_characters.load_configuration()
        char_config = configuration_data["character_list"][character_name]
        kokoro_voice_name = char_config["voice_type"]
        kokoro_rvc_enabled = char_config["rvc_enabled"]
        kokoro_rvc_file = char_config["rvc_file"]

        def _generate():
            generator = self.pipeline(text, voice=kokoro_voice_name)
            chunks = []
            for _, _, audio in generator:
                chunks.append(audio)
            return chunks

        all_audio = await asyncio.to_thread(_generate)

        if not all_audio:
            logger.warning("Kokoro generated empty audio for this chunk. Skipping.")
            return None

        full_audio = np.concatenate(all_audio)
        os.makedirs("app/voices/kokoro_audio", exist_ok=True)
        unique_id = uuid.uuid4().hex
        base_output_file = f"app/voices/kokoro_audio/kokoro_output_{unique_id}.wav"
        await asyncio.to_thread(sf.write, base_output_file, full_audio, 24000)

        if kokoro_rvc_enabled and kokoro_rvc_file:
            f0up_key   = char_config.get("rvc_f0up_key",   0)
            index_rate = char_config.get("rvc_index_rate", 0.75)
            protect    = char_config.get("rvc_protect",    0.5)

            await self._load_rvc(f0up_key, index_rate, protect)
            model_name = os.path.splitext(os.path.basename(kokoro_rvc_file))[0]
            rvc_output_file = f"app/voices/kokoro_audio/output_rvc_{unique_id}.wav"

            rvc_params = (model_name, f0up_key, index_rate, protect)
            if getattr(self, "_current_rvc_params", None) != rvc_params:
                await asyncio.to_thread(self.rvc.load_model, model_name)
                self._current_rvc_params = rvc_params

            await asyncio.to_thread(self.rvc.infer_file, base_output_file, rvc_output_file)

            fix_rvc_sample_rate(rvc_output_file, base_output_file)

            try:
                await asyncio.to_thread(os.remove, base_output_file)
            except OSError as e:
                logger.warning(f"Could not remove temp file {base_output_file}: {e}")

            return rvc_output_file

        return base_output_file


class SileroTTS_SOW_System:
    def __init__(self):
        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_api = configuration.ConfigurationAPI()
        self.configuration_characters = configuration.ConfigurationCharacters()

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = None
        self.tts_loaded = False
        self.rvc = None
        self.rvc_loaded = False

    async def _load_tts(self):
        if not self.tts_loaded:
            try:
                self.model, _ = await asyncio.to_thread(
                    torch.hub.load,
                    repo_or_dir='snakers4/silero-models',
                    model='silero_tts',
                    language='ru',
                    speaker='v5_3_ru',
                    trust_repo=True,
                    force_reload=False,
                    verbose=True
                )
                self.model.to(self.device)
                self.tts_loaded = True
                logger.info("Silero TTS loaded successfully")
            except Exception as e:
                raise RuntimeError(f"Failed to load Silero TTS: {e}")

    async def _load_rvc(self, f0up_key, index_rate, protect):
        if not self.rvc_loaded:
            logger.info("Loading RVC model...")
            try:
                def _init():
                    return RVCInference(
                        models_dir="assets/rvc_models",
                        device="cuda:0" if torch.cuda.is_available() else "cpu:0",
                        f0up_key=f0up_key, index_rate=index_rate, protect=protect
                    )
                self.rvc = await asyncio.to_thread(_init)
                self.rvc_loaded = True
                logger.info("RVC model loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading RVC model: {e}")
                raise RuntimeError("Failed to load RVC model.")

    async def generate_speech_with_silero(self, text, character_name):
        await self._load_tts()

        configuration_data = self.configuration_characters.load_configuration()
        char_config = configuration_data["character_list"][character_name]

        silero_voice = char_config.get("voice_type", "xenia")
        silero_rvc_enabled = char_config.get("rvc_enabled", False)
        silero_rvc_file = char_config.get("rvc_file")

        os.makedirs("app/voices/silero_audio", exist_ok=True)
        unique_id = uuid.uuid4().hex
        base_output_file = f"app/voices/silero_audio/silero_output_{unique_id}.wav"

        audio = await asyncio.to_thread(
            self.model.apply_tts,
            text=text,
            speaker=silero_voice,
            sample_rate=48000
        )
        await asyncio.to_thread(sf.write, base_output_file, audio.cpu().numpy(), 48000)

        if silero_rvc_enabled and silero_rvc_file:
            f0up_key   = char_config.get("rvc_f0up_key",   0)
            index_rate = char_config.get("rvc_index_rate", 0.75)
            protect    = char_config.get("rvc_protect",    0.5)

            await self._load_rvc(f0up_key, index_rate, protect)
            model_name = os.path.splitext(os.path.basename(silero_rvc_file))[0]
            rvc_output_file = f"app/voices/silero_audio/output_rvc_{unique_id}.wav"

            rvc_params = (model_name, f0up_key, index_rate, protect)
            if getattr(self, "_current_rvc_params", None) != rvc_params:
                await asyncio.to_thread(self.rvc.load_model, model_name)
                self._current_rvc_params = rvc_params
            
            await asyncio.to_thread(self.rvc.infer_file, base_output_file, rvc_output_file)

            fix_rvc_sample_rate(rvc_output_file, base_output_file)

            try:
                await asyncio.to_thread(os.remove, base_output_file)
            except OSError as e:
                logger.warning(f"Could not remove temp file {base_output_file}: {e}")

            return rvc_output_file

        return base_output_file

# Engines whose per-call overhead is large enough that several short sentences
# are cheaper to synthesise together than one by one.
_MERGE_BACKLOG_METHODS = {"Qwen-3 TTS", "XTTSv2"}


# Every kind of quotation mark toggles "inside a quotation". Direction-free on purpose: German „text“ closes with the mark that is the
# OPENING one in English (“), so a directional rule gets German typography backwards.
_QUOTE_MARKS = '"\u201c\u201d\u201e\u00ab\u00bb'
_QUOTE_SPLIT = re.compile("([" + re.escape(_QUOTE_MARKS) + "])")


def clean_for_speech(owner, text: str) -> str:
    """What the voice reads. `owner` carries tts_mode / tts_custom_regex and the streaming state (_in_tts_quote, _in_asterisk,
    _bracket_depth), because a quotation or an *action* can start in one chunk and end in the next.
    Modes: 0 everything, 1 only quotes, 2 ignore *asterisks*, 3 everything outside quotes, 4 custom regex."""
    if not text:
        return ""

    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"https?://\S+|www\.\S+", "", text)

    mode = owner.tts_mode
    regex = owner.tts_custom_regex

    if mode in (1, 2, 3):
        text = owner._strip_bracketed(text)          # [bracketed] stage directions are never spoken in the selective modes

    plain = lambda s: re.sub(r"[*_~`#]", "", re.sub(r"(?<=\w)_(?=\w)", " ", s)).strip()      # snake_case is read as two words

    if mode == 0:
        return plain(text)

    if mode in (1, 3):
        want_inside = (mode == 1)
        result = []
        paragraphs = text.split("\n\n")
        for n, paragraph in enumerate(paragraphs):
            if n > 0:
                owner._in_tts_quote = False          # a quotation never runs across a blank line: a stray mark must not flip the rest
                result.append(" ")
            for part in _QUOTE_SPLIT.split(paragraph):
                if len(part) == 1 and part in _QUOTE_MARKS:
                    owner._in_tts_quote = not owner._in_tts_quote
                    result.append(" ")
                    continue
                if owner._in_tts_quote == want_inside:
                    result.append(part)
        cleaned = plain(re.sub(r"\s{2,}", " ", "".join(result)))
        if mode == 1 and not cleaned and not any(q in text for q in _QUOTE_MARKS):
            # nobody put the speech in quotation marks: read the text without the *actions*
            no_actions = re.sub(r"\*[^*]+\*", "", text)
            no_actions = re.sub(r"(?<!\w)_[^_]+_(?!\w)", "", no_actions)
            cleaned = plain(no_actions)
        return cleaned

    if mode == 2:
        result = []
        for part in re.split(r"(\*|(?<!\w)_|_(?!\w))", text):         # _ only counts as an italic mark at a word border (snake_case stays)
            if part in ("*", "_"):
                owner._in_asterisk = not owner._in_asterisk
                if not owner._in_asterisk:
                    result.append(" ")
                continue
            if not owner._in_asterisk:
                result.append(part)
        return plain("".join(result))

    if mode == 4:
        if not regex:
            return plain(text)
        try:
            matches = re.findall(regex, text)
            if matches:
                extracted = []
                for m in matches:
                    extracted.append(next((g for g in m if g), "") if isinstance(m, tuple) else m)
                return " ".join(extracted).strip()
            return ""
        except re.error:
            return plain(text)

    return text.strip()


def _merge_queue_backlog(q, text, message_id, max_chars, mark_done=False):
    """Append directly following queued sentences of the same message to `text`.

    Only items that are already waiting are merged, so the first sentence of a
    response is never delayed. When generation is slower than the LLM, the
    backlog shrinks into fewer, longer calls instead of many tiny ones.
    """
    merged = 0
    while len(text) < max_chars:
        with q.mutex:
            nxt = q.queue[0] if q.queue else None
        if not isinstance(nxt, tuple) or len(nxt) != 2:
            break
        nxt_text, nxt_id = nxt
        if not nxt_text or nxt_id != message_id or len(text) + 1 + len(nxt_text) > max_chars:
            break
        try:
            q.get_nowait()
        except queue.Empty:
            break
        if mark_done:
            q.task_done()
        text = f"{text} {nxt_text}"
        merged += 1
    if merged:
        logger.info("TTS: merged %d queued sentence(s) into one call (%d chars)", merged, len(text))
    return text


class Qwen3TTS_SOW_System:
    def __init__(self):
        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_api = configuration.ConfigurationAPI()
        self.configuration_characters = configuration.ConfigurationCharacters()

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.pipeline = None
        self.tts_loaded = False
        self.rvc = None
        self.rvc_loaded = False
        self.model_id = None
        self._load_guard = threading.Lock()
        self._warned_no_ref_text = set()
        self._clone_prompt_cache = None

    @staticmethod
    def _pick_attn_implementation(use_cuda: bool, dtype) -> str:
        """FlashAttention-2 when the flash_attn package works with this GPU/dtype, else PyTorch SDPA."""
        if use_cuda and dtype in (torch.bfloat16, torch.float16):
            try:
                import flash_attn  # noqa: F401
                logger.info(f"Qwen3-TTS: using FlashAttention-2 (flash_attn {getattr(flash_attn, '__version__', '?')})")
                return "flash_attention_2"
            except Exception:
                pass
        return "sdpa"

    async def _load_tts(self, character_name: str):
        if not self.tts_loaded:
            try:
                configuration_data = self.configuration_characters.load_configuration()
                char_config = configuration_data["character_list"].get(character_name, {})

                model_size = char_config.get("qwen_model_size", "1.7B")
                qwen_mode = char_config.get("qwen_mode", "presets")
                qwen_device = char_config.get("qwen_device", "default")
                if qwen_device in ("default", "", None):
                    # "Standardgerät aus den KI-Diensteinstellungen": it used to fall through to the CPU (45 s for one sentence)
                    default_setting = str(self.configuration_settings.get_main_setting("tts_device") or "auto").lower()
                    qwen_device = "cuda" if default_setting in ("auto", "cuda") and torch.cuda.is_available() else "cpu"
                try:
                    qwen_gpu_index = max(0, int(char_config.get(
                        "qwen_gpu_index", self.configuration_settings.get_main_setting("qwen_gpu_index") or 0)))
                except (TypeError, ValueError):
                    qwen_gpu_index = 0

                if qwen_device == "cuda" and torch.cuda.is_available():
                    # several GPUs selected in AI services: a TTS model lives on one GPU, so take the one with the most free memory
                    if "qwen_gpu_index" not in char_config:
                        try:
                            from app.gui.gpu_select import setting_indices, freest_gpu
                            picked = [int(x) for x in setting_indices(self.configuration_settings, "tts_gpu_indices", "tts_gpu_index").split(",") if x.isdigit()]
                            best = freest_gpu(picked) if len(picked) > 1 else None
                            if best is not None:
                                qwen_gpu_index = best
                        except Exception:
                            pass
                    qwen_gpu_index = min(qwen_gpu_index, max(0, torch.cuda.device_count() - 1))
                    self.device = f"cuda:{qwen_gpu_index}"
                    target_dtype = torch.bfloat16 if torch.cuda.is_bf16_supported() else torch.float16
                    # Do not use device_map="auto": it can spill onto every GPU
                    # and compete with Whisper/other models. Pin Qwen to one GPU.
                    target_device_map = {"": self.device}
                else:
                    self.device = "cpu"
                    target_dtype = torch.float32
                    target_device_map = None

                if qwen_mode == "prompt":
                    variant = "VoiceDesign"
                elif qwen_mode == "cloning":
                    variant = "Base"
                else:
                    variant = "CustomVoice"

                if variant == "VoiceDesign" and model_size != "1.7B":
                    logger.warning(
                        f"Qwen3-TTS: VoiceDesign is only available as 1.7B, "
                        f"got model_size='{model_size}'. Falling back to 1.7B."
                    )
                    model_size = "1.7B"

                model_name = f"Qwen/Qwen3-TTS-12Hz-{model_size}-{variant}"

                attn_impl = self._pick_attn_implementation(target_device_map is not None, target_dtype)

                def _init():
                    try:
                        model = Qwen3TTSModel.from_pretrained(
                            model_name,
                            dtype=target_dtype,
                            device_map=target_device_map,
                            attn_implementation=attn_impl,
                        )
                    except Exception as attn_error:
                        if attn_impl == "sdpa":
                            raise
                        logger.warning(f"Qwen3-TTS: '{attn_impl}' failed ({attn_error}); falling back to sdpa.")
                        model = Qwen3TTSModel.from_pretrained(
                            model_name,
                            dtype=target_dtype,
                            device_map=target_device_map,
                            attn_implementation="sdpa",
                        )
                    
                    if target_dtype == torch.float32:
                        def clean_and_cast_to_float32(obj, visited=None):
                            if visited is None:
                                visited = set()
                            
                            obj_id = id(obj)
                            if obj_id in visited:
                                return
                            visited.add(obj_id)

                            if isinstance(obj, torch.nn.Module):
                                if hasattr(obj, "_hf_hook"):
                                    try:
                                        delattr(obj, "_hf_hook")
                                    except Exception:
                                        pass
                                try:
                                    obj.to(torch.float32)
                                except Exception:
                                    pass
                                for child in obj.children():
                                    clean_and_cast_to_float32(child, visited)
                            
                            elif hasattr(obj, "__dict__"):
                                for attr_name, attr_val in list(obj.__dict__.items()):
                                    if attr_name.startswith("__"):
                                        continue
                                    clean_and_cast_to_float32(attr_val, visited)
                            
                            elif isinstance(obj, (list, tuple)):
                                for item in obj:
                                    clean_and_cast_to_float32(item, visited)
                                    
                            elif isinstance(obj, dict):
                                for value in obj.values():
                                    clean_and_cast_to_float32(value, visited)

                        clean_and_cast_to_float32(model)
                            
                    return model

                self.model = await asyncio.to_thread(_init)
                self.model_id = model_name
                self._clone_prompt_cache = None
                self.tts_loaded = True
                
                logger.info(f"Qwen3-TTS {model_size}-{variant} loaded on {self.device.upper()} for '{character_name}'")

            except Exception as e:
                logger.error(f"Failed to load Qwen3-TTS for {character_name}: {e}")
                raise RuntimeError(f"Failed to load Qwen3-TTS: {e}")

    def _get_clone_prompt(self, character_name, ref_path, ref_text):
        """Build (or reuse) the voice-clone prompt for a reference recording."""
        try:
            mtime = os.path.getmtime(ref_path)
        except OSError:
            mtime = 0
        key = (str(self.model_id), ref_path, ref_text or "", mtime)
        cache = getattr(self, "_clone_prompt_cache", None)
        if cache is not None and cache[0] == key:
            return cache[1]
        if not ref_text and character_name not in self._warned_no_ref_text:
            self._warned_no_ref_text.add(character_name)
            logger.warning(
                f"Qwen3-TTS: no 'qwen_cloning_ref_text' set for "
                f"'{character_name}'; using x_vector_only_mode "
                f"(cloning quality may be reduced)."
            )
        prompt = self.model.create_voice_clone_prompt(
            ref_audio=ref_path,
            ref_text=ref_text or None,
            x_vector_only_mode=not bool(ref_text),
        )
        self._clone_prompt_cache = (key, prompt)
        return prompt

    def start_warm_up(self, character_name: str):
        """Preload in a background thread so stopping the worker never blocks on it.

        The guard lock is taken here and released by the thread; generation waits
        for it, so the model can not be loaded twice.
        """
        if not self._load_guard.acquire(blocking=False):
            return  # a warm-up is already running

        def _run():
            try:
                asyncio.run(self.warm_up(character_name))
            finally:
                self._load_guard.release()

        threading.Thread(target=_run, daemon=True, name="qwen-tts-warmup").start()

    def _wait_for_warm_up(self):
        with self._load_guard:
            pass

    def _dummy_generation(self, cfg, character_name):
        """One tiny synthesis (and RVC pass) so CUDA kernels and RVC sub-models
        are initialised before the first real sentence. Nothing is kept."""
        params = {"text": "Hi.", "language": cfg.get("qwen_language", "English"), "max_new_tokens": 24}
        mode = cfg.get("qwen_mode", "presets")
        try:
            with torch.no_grad():
                if mode == "cloning" and self._clone_prompt_cache:
                    wavs, sr = self.model.generate_voice_clone(voice_clone_prompt=self._clone_prompt_cache[1], **params)
                elif mode == "prompt" and cfg.get("qwen_prompt"):
                    wavs, sr = self.model.generate_voice_design(instruct=cfg["qwen_prompt"], **params)
                elif mode not in ("cloning", "prompt"):
                    wavs, sr = self.model.generate_custom_voice(
                        speaker=cfg.get("voice_type", "Serena"),
                        instruct=cfg.get("qwen_style_instruct", ""), **params)
                else:
                    return
        except Exception as e:
            logger.debug("Qwen3-TTS dummy generation skipped: %s", e)
            return

        if self.rvc is not None and cfg.get("rvc_enabled") and cfg.get("rvc_file"):
            os.makedirs("app/voices/qwen_audio", exist_ok=True)
            tag = uuid.uuid4().hex
            src = f"app/voices/qwen_audio/_warmup_{tag}.wav"
            dst = f"app/voices/qwen_audio/_warmup_{tag}_rvc.wav"
            try:
                audio = wavs[0]
                if isinstance(audio, torch.Tensor):
                    audio = audio.detach().cpu().to(torch.float32).numpy()
                sf.write(src, audio, sr)
                self.rvc.infer_file(src, dst)
            except Exception as e:
                logger.debug("RVC dummy pass skipped: %s", e)
            finally:
                for p in (src, dst):
                    try:
                        os.remove(p)
                    except OSError:
                        pass

    async def warm_up(self, character_name: str):
        """Load model, RVC voice and clone prompt ahead of the first sentence."""
        started = time.perf_counter()
        try:
            await self._load_tts(character_name)
            cfg = self.configuration_characters.load_configuration()["character_list"].get(character_name, {})
            if cfg.get("rvc_enabled") and cfg.get("rvc_file"):
                f0up_key = cfg.get("rvc_f0up_key", 0)
                index_rate = cfg.get("rvc_index_rate", 0.75)
                protect = cfg.get("rvc_protect", 0.5)
                await self._load_rvc(f0up_key, index_rate, protect)
                model_name = os.path.splitext(os.path.basename(cfg["rvc_file"]))[0]
                rvc_params = (model_name, f0up_key, index_rate, protect)
                if getattr(self, "_current_rvc_params", None) != rvc_params:
                    await asyncio.to_thread(self.rvc.load_model, model_name)
                    self._current_rvc_params = rvc_params
            ref_path = cfg.get("qwen_cloning_ref_path", "")
            if cfg.get("qwen_mode") == "cloning" and ref_path and os.path.exists(ref_path):
                await asyncio.to_thread(self._get_clone_prompt, character_name, ref_path,
                                        cfg.get("qwen_cloning_ref_text", ""))
            await asyncio.to_thread(self._dummy_generation, cfg, character_name)
            logger.info("Qwen3-TTS warm-up finished in %.1fs", time.perf_counter() - started)
        except Exception as e:
            logger.warning("Qwen3-TTS warm-up failed (will load on first sentence instead): %s", e)

    async def _load_rvc(self, f0up_key, index_rate, protect):
        if not self.rvc_loaded:
            logger.info("Loading RVC model for Qwen 3...")
            try:
                def _init():
                    selected_device = self.device if str(self.device).startswith("cuda") else "cpu:0"
                    return RVCInference(
                        models_dir="assets/rvc_models",
                        device=selected_device,
                        f0up_key=f0up_key, index_rate=index_rate, protect=protect
                    )
                self.rvc = await asyncio.to_thread(_init)
                self.rvc_loaded = True
                logger.info("RVC model loaded successfully.")
            except Exception as e:
                logger.error(f"Error loading RVC model: {e}")
                raise RuntimeError("Failed to load RVC model.")

    async def generate_speech_with_qwen3(self, text: str, character_name: str, overrides: dict = None):
        await asyncio.to_thread(self._wait_for_warm_up)
        await self._load_tts(character_name)

        configuration_data = self.configuration_characters.load_configuration()
        char_config = configuration_data["character_list"][character_name]

        qwen_mode = char_config.get("qwen_mode", "presets")
        voice_type = char_config.get("voice_type", "Serena")
        qwen_prompt = char_config.get("qwen_prompt", "")
        qwen_instruct = char_config.get("qwen_style_instruct", "")
        qwen_ref_path = char_config.get("qwen_cloning_ref_path", "")
        qwen_ref_text = char_config.get("qwen_cloning_ref_text", "")
        language = char_config.get("qwen_language", "English")

        qwen_rvc_enabled = char_config.get("rvc_enabled", False)
        qwen_rvc_file = char_config.get("rvc_file")
        if qwen_rvc_enabled and (not qwen_rvc_file or not os.path.exists(str(qwen_rvc_file))):
            logger.warning("Qwen TTS: RVC is enabled for %s but the model file is missing (%s) - RVC is skipped.", character_name, qwen_rvc_file)
            qwen_rvc_enabled = False
        logger.info("Qwen TTS voice for '%s': mode=%s, preset=%s, clone_ref=%s, rvc=%s",
                    character_name, qwen_mode, voice_type, qwen_ref_path or "-",
                    os.path.basename(str(qwen_rvc_file)) if qwen_rvc_enabled else "off")
        runtime_settings = load_main_settings()
        try:
            qwen_max_new_tokens = max(128, min(4096, int(char_config.get("qwen_max_new_tokens", 1500))))
        except (TypeError, ValueError):
            qwen_max_new_tokens = 1500
        try:
            qwen_temperature = max(0.05, min(1.5, float(char_config.get("qwen_temperature", 0.7))))
        except (TypeError, ValueError):
            qwen_temperature = 0.7
        try:
            qwen_top_p = max(0.1, min(1.0, float(char_config.get("qwen_top_p", 0.9))))
        except (TypeError, ValueError):
            qwen_top_p = 0.9
        end_silence_ms = max(0, min(int(char_config.get("qwen_end_silence_ms", 100)), 1000))
        if overrides:                                   # e.g. the stored wake word answers: best settings instead of the live-chat compromise
            qwen_temperature = min(qwen_temperature, float(overrides.get("temperature", qwen_temperature)))
            qwen_top_p = min(qwen_top_p, float(overrides.get("top_p", qwen_top_p)))
            qwen_max_new_tokens = max(qwen_max_new_tokens, int(overrides.get("max_new_tokens", qwen_max_new_tokens)))
            end_silence_ms = max(end_silence_ms, int(overrides.get("end_silence_ms", end_silence_ms)))

        os.makedirs("app/voices/qwen_audio", exist_ok=True)
        unique_id = uuid.uuid4().hex
        base_output_file = f"app/voices/qwen_audio/qwen_output_{unique_id}.wav"

        def _generate():
            try:
                generation_params = {
                    "text": text,
                    "language": language,
                    "max_new_tokens": qwen_max_new_tokens,
                    "temperature": qwen_temperature,
                    "top_p": qwen_top_p,
                }

                with torch.no_grad():
                    if self.device == "cpu":
                        autocast_ctx = torch.amp.autocast(device_type="cpu", enabled=False)
                    else:
                        autocast_ctx = contextlib.nullcontext()

                    with autocast_ctx:
                        if qwen_mode == "cloning" and qwen_ref_path and os.path.exists(qwen_ref_path):
                            # Voice Cloning. The reference-voice prompt is computed once
                            # per (file, text) and reused for every following sentence.
                            clone_prompt = self._get_clone_prompt(
                                character_name, qwen_ref_path, qwen_ref_text)
                            wavs, sr = self.model.generate_voice_clone(
                                voice_clone_prompt=clone_prompt,
                                **generation_params
                            )

                        elif qwen_mode == "prompt" and qwen_prompt:
                            # Voice Design
                            wavs, sr = self.model.generate_voice_design(
                                instruct=qwen_prompt,
                                **generation_params
                            )

                        else:
                            # Preset Voices (CustomVoice)
                            wavs, sr = self.model.generate_custom_voice(
                                speaker=voice_type, instruct=qwen_instruct,
                                **generation_params
                            )

                audio_data = wavs[0]
                if isinstance(audio_data, torch.Tensor):
                    audio_data = audio_data.detach().cpu().to(torch.float32).numpy()
                elif isinstance(audio_data, np.ndarray):
                    audio_data = audio_data.astype(np.float32)

                # A tiny tail of digital silence helps avoid the perception of
                # a clipped final phoneme when adjacent generated chunks meet.
                if end_silence_ms > 0 and isinstance(audio_data, np.ndarray) and audio_data.size:
                    pad_shape = (max(1, int(sr * end_silence_ms / 1000)),) + audio_data.shape[1:]
                    audio_data = np.concatenate((audio_data, np.zeros(pad_shape, dtype=audio_data.dtype)), axis=0)
                sf.write(base_output_file, audio_data, sr)
                return base_output_file

            except Exception as e:
                logger.error(f"Qwen3 TTS generation error: {e}")
                raise

        _t_start = time.perf_counter()
        await asyncio.to_thread(_generate)
        _t_gen = time.perf_counter() - _t_start

        if qwen_rvc_enabled and qwen_rvc_file:
            f0up_key = char_config.get("rvc_f0up_key", 0)
            index_rate = char_config.get("rvc_index_rate", 0.75)
            protect = char_config.get("rvc_protect", 0.5)

            await self._load_rvc(f0up_key, index_rate, protect)

            model_name = os.path.splitext(os.path.basename(qwen_rvc_file))[0]
            rvc_output_file = f"app/voices/qwen_audio/output_rvc_{unique_id}.wav"

            rvc_params = (model_name, f0up_key, index_rate, protect)
            if getattr(self, "_current_rvc_params", None) != rvc_params:
                await asyncio.to_thread(self.rvc.load_model, model_name)
                self._current_rvc_params = rvc_params

            await asyncio.to_thread(self.rvc.infer_file, base_output_file, rvc_output_file)

            fix_rvc_sample_rate(rvc_output_file, base_output_file)

            try:
                os.remove(base_output_file)
            except OSError:
                pass

            logger.info("Qwen3-TTS timing: generate=%.1fs rvc=%.1fs (%d chars)",
                        _t_gen, time.perf_counter() - _t_start - _t_gen, len(text))
            return rvc_output_file

        logger.info("Qwen3-TTS timing: generate=%.1fs (%d chars)", _t_gen, len(text))
        return base_output_file

_REMOTE_AUDIO_ONLY = False


def set_remote_audio_only(flag: bool):
    """True while a phone call is running: the speech goes to the phone (WebSocket) and the PC speakers stay silent."""
    global _REMOTE_AUDIO_ONLY
    _REMOTE_AUDIO_ONLY = bool(flag)


class AudioPlaybackWorker(QThread):
    queue_empty_signal = pyqtSignal()
    lipsync_signal = pyqtSignal(float)

    def __init__(self, device_index):
        super().__init__()
        self.queue = queue.Queue()
        self.is_running = True
        self.device_index = device_index
        self.interrupt_flag = False
        self.lipsync_smoothing = bool(load_main_settings().get("lipsync_smoothing", True))

    def add_audio_file(self, file_path, persist=False):
        self.interrupt_flag = False
        self.queue.put((file_path, persist))

    def clear_queue(self):
        self.interrupt_flag = True
        with self.queue.mutex:
            for item in list(self.queue.queue):
                file_path, persist = item if isinstance(item, tuple) else (item, False)
                if persist:
                    continue
                try:
                    if file_path and os.path.exists(file_path):
                        os.remove(file_path)
                except Exception:
                    pass
            self.queue.queue.clear()

    def run(self):
        logger.info("Audio Playback Worker Started")
        while self.is_running:
            try:
                item = self.queue.get(timeout=0.1)

                if item is None:
                    self.queue.task_done()
                    continue

                file_path, persist = item if isinstance(item, tuple) else (item, False)

                if _REMOTE_AUDIO_ONLY and not persist:
                    try:
                        if os.path.exists(file_path):
                            os.remove(file_path)
                    except Exception:
                        pass
                    self.queue.task_done()
                    continue

                if self.interrupt_flag:
                    if not persist:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception:
                            pass
                    self.queue.task_done()
                    continue

                playback_handle = None
                audio_started = False
                try:
                    data, samplerate = sf.read(file_path, dtype='float32')
                    playback_handle = start_audio_playback(data, samplerate, self.device_index)
                    audio_started = True
                    playback_interrupted = False

                    duration = len(data) / samplerate
                    chunk_size = int(samplerate * 0.05)
                    slept = 0

                    smoothed_mouth_open = 0.0
                    while slept < duration:
                        if self.interrupt_flag:
                            playback_interrupted = True
                            self.lipsync_signal.emit(0.0)
                            break

                        start_idx = int(slept * samplerate)
                        end_idx = min(start_idx + chunk_size, len(data))
                        current_chunk = data[start_idx:end_idx]

                        if len(current_chunk) > 0:
                            rms = np.sqrt(np.mean(current_chunk ** 2))
                            target_mouth_open = min(float(rms) * 5.0, 1.0)
                            if self.lipsync_smoothing:
                                alpha = 0.62 if target_mouth_open > smoothed_mouth_open else 0.24
                                smoothed_mouth_open += alpha * (target_mouth_open - smoothed_mouth_open)
                                mouth_open = smoothed_mouth_open
                            else:
                                mouth_open = target_mouth_open
                            self.lipsync_signal.emit(float(mouth_open))

                        time.sleep(0.05)
                        slept += 0.05

                    finish_audio_playback(
                        playback_handle,
                        interrupted=playback_interrupted or self.interrupt_flag,
                        timeout=max(5.0, duration + 3.0),
                    )
                    playback_handle = None
                    audio_started = False
                    self.lipsync_signal.emit(0.0)

                except Exception as e:
                    logger.error(f"Playback error: {e}")

                finally:
                    if audio_started:
                        finish_audio_playback(playback_handle, interrupted=True)
                    if not persist:
                        try:
                            if os.path.exists(file_path):
                                os.remove(file_path)
                        except Exception:
                            pass

                self.queue.task_done()

                if self.queue.empty() and not self.interrupt_flag:
                    self.queue_empty_signal.emit()

            except queue.Empty:
                continue

    def stop(self):
        self.is_running = False
        self.interrupt_flag = True
        set_audio_playback_active(False)
        try:
            sd.stop()
        except Exception:
            pass
        self.queue.put(None)
        self.quit()
        self.wait()


def _record_tts_stats(method, text, started, path):
    """Feed the dashboard (runtime_stats) with one finished speech generation."""
    try:
        import time as _time
        from app.utils.runtime_stats import stats as _stats
        audio_s = None
        if path and str(path).lower().endswith(".wav"):
            try:
                import wave
                with wave.open(str(path), "rb") as _w:
                    audio_s = _w.getnframes() / float(_w.getframerate())
            except Exception:
                audio_s = None
        _stats.record_tts(str(method), len(text or ""), _time.time() - started, audio_s, ok=bool(path))
    except Exception:
        pass


class _RenderJob:
    """A sentence that is only synthesized (not played): the phone downloads it, e.g. the answer to its wake word."""
    def __init__(self, text, overrides=None):
        import concurrent.futures
        self.text = text
        self.overrides = overrides or {}
        self.future = concurrent.futures.Future()


class TTSWorker(QThread):
    audio_ready_signal = pyqtSignal(str)
    segment_saved_signal = pyqtSignal(str, str)

    # settings for sentences that are kept: calmer sampling, room for the whole sentence, a little silence at the end
    HIGH_QUALITY = {"temperature": 0.6, "top_p": 0.9, "max_new_tokens": 3000, "end_silence_ms": 300}

    def render_to_bytes(self, text, timeout=300, high_quality=False):
        """Synthesizes [text] with the voice of this character (RVC included) and returns the audio file's bytes. Blocking: call from a thread."""
        job = _RenderJob(text, dict(self.HIGH_QUALITY) if high_quality else {})
        self.queue.put(job)
        return job.future.result(timeout)

    def _do_render(self, loop, job):
        output_file = None
        try:
            text = job.text
            if self.tts_method == "XTTSv2":
                output_file = loop.run_until_complete(self.xtts.generate_speech_with_xttsv2_sow_system(text, self.language, self.character_name))
            elif self.tts_method == "Edge TTS":
                output_file = loop.run_until_complete(self.edge.generate_speech_with_edge_tts_sow_system(text, self.character_name))
            elif self.tts_method == "Kokoro":
                output_file = loop.run_until_complete(self.kokoro.generate_speech_with_kokoro(text, self.character_name))
            elif self.tts_method == "Silero":
                output_file = loop.run_until_complete(self.silero.generate_speech_with_silero(text, self.character_name))
            elif self.tts_method == "Qwen-3 TTS":
                output_file = loop.run_until_complete(self.qwen.generate_speech_with_qwen3(text, self.character_name, job.overrides))
            elif self.tts_method == "ElevenLabs":
                output_file = loop.run_until_complete(self.eleven.generate_speech_with_elevenlabs_sow_system(text, self.voice_id))
            if not output_file or not os.path.exists(output_file):
                raise RuntimeError("no audio was produced")
            if str(output_file).lower().endswith(".mp3"):
                wav_path = str(output_file) + ".wav"
                AudioSegment.from_mp3(output_file).export(wav_path, format="wav")
                with open(wav_path, "rb") as f:
                    data = f.read()
                os.remove(wav_path)
            else:
                with open(output_file, "rb") as f:
                    data = f.read()
            job.future.set_result(data)
        except Exception as exc:
            job.future.set_exception(exc)
        finally:
            try:
                if output_file and os.path.exists(output_file):
                    os.remove(output_file)
            except Exception:
                pass

    def __init__(self, tts_method, character_name, voice_id=None, language="en"):
        super().__init__()
        self.queue = queue.Queue()
        self.is_running = True
        self.discard_current = False

        self.tts_method = tts_method
        self.character_name = character_name
        self.voice_id = voice_id
        self.language = language

        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_api = configuration.ConfigurationAPI()
        self.configuration_characters = configuration.ConfigurationCharacters()

        self.device_index = self.configuration_settings.get_main_setting("output_device_real_index")
        runtime_voice_settings = load_main_settings()
        character_config = self.configuration_characters.load_configuration().get("character_list", {}).get(character_name, {})
        try:
            self.chunk_max_chars = max(120, min(500, int(character_config.get("tts_chunk_max_chars", runtime_voice_settings.get("tts_chunk_max_chars", 280)))))
        except (TypeError, ValueError):
            self.chunk_max_chars = 280
        try:
            self.chunk_pause_ms = max(0, min(1000, int(character_config.get("tts_chunk_pause_ms", runtime_voice_settings.get("tts_chunk_pause_ms", 140)))))
        except (TypeError, ValueError):
            self.chunk_pause_ms = 140
        self.lipsync_smoothing = bool(runtime_voice_settings.get("lipsync_smoothing", True))

        self.tts_mode = self.configuration_settings.get_main_setting("tts_voicing_mode") or 0
        self.tts_custom_regex = self.configuration_settings.get_main_setting("tts_custom_regex") or ""

        self._in_tts_quote = False
        self._in_asterisk = False

        self.xtts = XTTSv2_SOW_System()
        self.edge = EdgeTTS()
        self.kokoro = KokoroTTS_SOW_System()
        self.silero = SileroTTS_SOW_System()
        self.qwen = Qwen3TTS_SOW_System()
        self.eleven = ElevenLabs()

        self.playback_worker = AudioPlaybackWorker(self.device_index)
        self.playback_worker.start()

    def add_text(self, text, message_id=None):
        if not text:
            return
            
        text = self.clean_text_for_speech(text)
        if not text:
            return

        raw_sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = ""
        max_chunk_len = 450 
        
        def _enqueue(chunk_text):
            if chunk_text:
                self.queue.put((chunk_text, message_id))

        for sentence in raw_sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(sentence) > max_chunk_len:
                if current_chunk:
                    _enqueue(current_chunk)
                    current_chunk = ""
                
                sub_chunks = re.split(r'(?<=[,;])\s', sentence)
                for sub in sub_chunks:
                    sub = sub.strip()
                    if len(sub) > max_chunk_len:
                        for i in range(0, len(sub), max_chunk_len):
                            _enqueue(sub[i:i+max_chunk_len])
                    else:
                        _enqueue(sub)
            else:
                if len(current_chunk) + len(sentence) + 1 > max_chunk_len:
                    _enqueue(current_chunk)
                    current_chunk = sentence
                else:
                    if current_chunk:
                        current_chunk += " " + sentence
                    else:
                        current_chunk = sentence
        
        if current_chunk:
            _enqueue(current_chunk)

    def _persist_segment_for_replay(self, source_file, message_id):
        if not source_file or not os.path.exists(source_file):
            return None

        segment_dir = os.path.join(
            os.getcwd(), "app", "data", ".soul", self.character_name, "tts_audio", message_id
        )
        os.makedirs(segment_dir, exist_ok=True)

        existing = [f for f in os.listdir(segment_dir) if f.lower().endswith((".wav", ".mp3"))]
        next_index = len(existing) + 1
        ext = os.path.splitext(source_file)[1] or ".wav"
        segment_filename = f"seg_{next_index:04d}{ext}"
        destination = os.path.join(segment_dir, segment_filename)

        shutil.copyfile(source_file, destination)

        return f"tts_audio/{message_id}/{segment_filename}"

    def _strip_bracketed(self, text: str) -> str:
        """Remove [bracketed] stage directions, also when they span chunks."""
        out = []
        depth = getattr(self, "_bracket_depth", 0)
        for ch in text:
            if ch == "[":
                depth += 1
            elif ch == "]":
                if depth > 0:
                    depth -= 1
            elif depth == 0:
                out.append(ch)
        self._bracket_depth = depth
        return "".join(out)

    def clean_text_for_speech(self, text: str) -> str:
        return clean_for_speech(self, text)

    def clear_queue(self):
        with self.queue.mutex:
            self.queue.queue.clear()
        self.discard_current = True
        self._in_tts_quote = False
        self._in_asterisk = False
        self._bracket_depth = 0
        if hasattr(self, 'playback_worker'):
            self.playback_worker.clear_queue()

    def run(self):
        logger.info(f"TTS Worker Started ({self.tts_method})")

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        if self.tts_method == "Qwen-3 TTS":
            # Runs in the background while the LLM generates the first sentence.
            self.qwen.start_warm_up(self.character_name)

        while self.is_running:
            try:
                item = self.queue.get(timeout=0.5)

                if item is None:
                    self.queue.task_done()
                    continue

                if isinstance(item, _RenderJob):
                    self._do_render(loop, item)
                    self.queue.task_done()
                    continue

                text, message_id = item if isinstance(item, tuple) else (item, None)

                if text and self.tts_method in _MERGE_BACKLOG_METHODS:
                    text = _merge_queue_backlog(self.queue, text, message_id,
                                                min(self.chunk_max_chars, 300), mark_done=True)

                if text:
                    self.discard_current = False
                    logger.info(f"Generating Audio for: {text[:30]}...")
                    output_file = None
                    _tts_started = time.time()

                    if self.tts_method == "XTTSv2":
                        output_file = loop.run_until_complete(
                            self.xtts.generate_speech_with_xttsv2_sow_system(text, self.language, self.character_name)
                        )
                    elif self.tts_method == "Edge TTS":
                        output_file = loop.run_until_complete(
                            self.edge.generate_speech_with_edge_tts_sow_system(text, self.character_name)
                        )
                    elif self.tts_method == "Kokoro":
                        output_file = loop.run_until_complete(
                            self.kokoro.generate_speech_with_kokoro(text, self.character_name)
                        )
                    elif self.tts_method == "Silero":
                        output_file = loop.run_until_complete(
                            self.silero.generate_speech_with_silero(text, self.character_name)
                        )
                    elif self.tts_method == "Qwen-3 TTS":
                        output_file = loop.run_until_complete(
                            self.qwen.generate_speech_with_qwen3(text, self.character_name)
                        )
                    elif self.tts_method == "ElevenLabs":
                        output_file = loop.run_until_complete(
                            self.eleven.generate_speech_with_elevenlabs_sow_system(text, self.voice_id)
                        )

                    _record_tts_stats(self.tts_method, text, _tts_started, output_file)

                    if self.discard_current:
                        logger.info("TTS finished, but was interrupted. Discarding audio.")
                        if output_file and os.path.exists(output_file):
                            try:
                                os.remove(output_file)
                            except Exception:
                                pass
                        self.queue.task_done()
                        continue

                    if output_file:
                        try:
                            import base64
                            with open(output_file, "rb") as f:
                                b64_audio = base64.b64encode(f.read()).decode("utf-8")
                            self.audio_ready_signal.emit(b64_audio)
                        except Exception as e:
                            logger.error(f"Error encoding audio for web client: {e}")
                        
                        if message_id:
                            try:
                                relative_path = self._persist_segment_for_replay(output_file, message_id)
                                if relative_path:
                                    self.segment_saved_signal.emit(message_id, relative_path)
                            except Exception as e:
                                logger.error(f"Failed to persist TTS segment for replay: {e}")

                        self.playback_worker.add_audio_file(output_file)

                    self.queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                logger.error(f"TTS Error: {e}")

    def stop(self):
        self.is_running = False
        self.discard_current = True
        self.queue.put(None)
        if hasattr(self, 'playback_worker'):
            self.playback_worker.stop()
        self.quit()
        self.wait()

class _AudioChunk:
    __slots__ = ("file_path", "text", "message_id", "persist", "is_poison")

    def __init__(self, file_path: Optional[str] = None, text: str = "",
                 message_id: Optional[str] = None, persist: bool = False,
                 is_poison: bool = False):
        self.file_path = file_path
        self.text = text
        self.message_id = message_id
        self.persist = persist
        self.is_poison = is_poison

class PipelinedTTSWorker(QThread):
    audio_ready_signal = pyqtSignal(str)
    segment_saved_signal = pyqtSignal(str, str)
    lipsync_signal = pyqtSignal(float)
    queue_empty_signal = pyqtSignal()

    AUDIO_BUFFER_SIZE = 2
    LIPSYNC_POLL_SEC = 0.05
    TTS_TIMEOUT_SEC = 30

    def __init__(self, tts_method, character_name, voice_id=None, language="en"):
        super().__init__()

        self.text_queue = queue.Queue()

        self.is_running = True
        self.discard_current = False
        self._interrupt_flag = threading.Event()

        self.tts_method = tts_method
        self.character_name = character_name
        self.voice_id = voice_id
        self.language = language

        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_api = configuration.ConfigurationAPI()
        self.configuration_characters = configuration.ConfigurationCharacters()

        self.device_index = self.configuration_settings.get_main_setting("output_device_real_index")
        runtime_voice_settings = load_main_settings()
        character_config = self.configuration_characters.load_configuration().get("character_list", {}).get(character_name, {})
        try:
            self.chunk_max_chars = max(120, min(500, int(character_config.get("tts_chunk_max_chars", runtime_voice_settings.get("tts_chunk_max_chars", 280)))))
        except (TypeError, ValueError):
            self.chunk_max_chars = 280
        try:
            self.chunk_pause_ms = max(0, min(1000, int(character_config.get("tts_chunk_pause_ms", runtime_voice_settings.get("tts_chunk_pause_ms", 140)))))
        except (TypeError, ValueError):
            self.chunk_pause_ms = 140
        self.lipsync_smoothing = bool(runtime_voice_settings.get("lipsync_smoothing", True))

        self.tts_mode = self.configuration_settings.get_main_setting("tts_voicing_mode") or 0
        self.tts_custom_regex = self.configuration_settings.get_main_setting("tts_custom_regex") or ""

        self._in_tts_quote = False
        self._in_asterisk = False

        self._tts_engines_initialized = False
        self.xtts = None
        self.edge = None
        self.kokoro = None
        self.silero = None
        self.qwen = None
        self.eleven = None

        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._audio_buffer: Optional[asyncio.Queue] = None
        self._producer_task: Optional[asyncio.Task] = None
        self._player_task: Optional[asyncio.Task] = None
        # Keep the voice indicator alive while the LLM is still streaming text,
        # even when the audio buffer is briefly empty between sentences.
        self._response_stream_open = False
        self._producer_busy = False
        self._player_busy = False
        self._queue_empty_announced = True

    def begin_response_stream(self):
        """Tell the TTS pipeline that more text may arrive for the current LLM response."""
        self._response_stream_open = True
        self._queue_empty_announced = False

    def finish_response_stream(self):
        """Mark the response complete; queue-empty is emitted only after audio drains."""
        self._response_stream_open = False
        loop = self._loop
        if loop and loop.is_running():
            loop.call_soon_threadsafe(self._try_emit_queue_empty)
        else:
            self._try_emit_queue_empty()

    def _try_emit_queue_empty(self):
        if self._response_stream_open or self._producer_busy or self._player_busy:
            return
        if not self.text_queue.empty():
            return
        if self._audio_buffer is not None and not self._audio_buffer.empty():
            return
        if not self._queue_empty_announced:
            self._queue_empty_announced = True
            try:
                self.queue_empty_signal.emit()
            except Exception:
                pass

    def _ensure_tts_engines(self):
        if self._tts_engines_initialized:
            return
        from app.utils.text_to_speech import (
            XTTSv2_SOW_System, EdgeTTS, KokoroTTS_SOW_System,
            SileroTTS_SOW_System, Qwen3TTS_SOW_System, ElevenLabs
        )
        self.xtts = XTTSv2_SOW_System()
        self.edge = EdgeTTS()
        self.kokoro = KokoroTTS_SOW_System()
        self.silero = SileroTTS_SOW_System()
        self.qwen = Qwen3TTS_SOW_System()
        self.eleven = ElevenLabs()
        self._tts_engines_initialized = True
        logger.info(f"[PipelinedTTS] engines initialized for method='{self.tts_method}'")

    def add_text(self, text, message_id=None):
        if not text:
            return

        self.discard_current = False
        self._interrupt_flag.clear()
        self._queue_empty_announced = False

        text = self.clean_text_for_speech(text)
        if not text:
            return

        raw_sentences = re.split(r'(?<=[.!?])\s+', text)
        current_chunk = ""
        max_chunk_len = self.chunk_max_chars

        def _enqueue(chunk_text):
            cleaned = chunk_text.strip()
            if cleaned:
                self.text_queue.put((cleaned, message_id))
                self._queue_empty_announced = False

        def _split_by_words(long_text):
            """Greedily split at whitespace without cutting words in half."""
            output, buffer = [], ""
            for word in re.findall(r"\S+", long_text):
                if not buffer:
                    buffer = word
                elif len(buffer) + 1 + len(word) <= max_chunk_len:
                    buffer += " " + word
                else:
                    output.append(buffer)
                    buffer = word
            if buffer:
                output.append(buffer)
            # An unusually long URL/code token has already been cleaned where
            # possible; only split a single oversized token as a last resort.
            final = []
            for part in output:
                if len(part) <= max_chunk_len:
                    final.append(part)
                else:
                    final.extend(part[i:i + max_chunk_len] for i in range(0, len(part), max_chunk_len))
            return final

        for sentence in raw_sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            if len(sentence) > max_chunk_len:
                if current_chunk:
                    _enqueue(current_chunk)
                    current_chunk = ""
                # Prefer pauses at commas/semicolons/colons; only then use a
                # word-aware split. This keeps spoken phrasing more natural.
                clauses = re.split(r'(?<=[,;:])\s+', sentence)
                for clause in clauses:
                    if not clause:
                        continue
                    if len(clause) <= max_chunk_len:
                        _enqueue(clause)
                    else:
                        _enqueue_parts = _split_by_words(clause)
                        for part in _enqueue_parts:
                            _enqueue(part)
            else:
                if current_chunk and len(current_chunk) + len(sentence) + 1 > max_chunk_len:
                    _enqueue(current_chunk)
                    current_chunk = sentence
                else:
                    current_chunk = (current_chunk + " " + sentence).strip()

        if current_chunk:
            _enqueue(current_chunk)

    def _strip_bracketed(self, text: str) -> str:
        """Remove [bracketed] stage directions, also when they span chunks."""
        out = []
        depth = getattr(self, "_bracket_depth", 0)
        for ch in text:
            if ch == "[":
                depth += 1
            elif ch == "]":
                if depth > 0:
                    depth -= 1
            elif depth == 0:
                out.append(ch)
        self._bracket_depth = depth
        return "".join(out)

    def clean_text_for_speech(self, text: str) -> str:
        return clean_for_speech(self, text)

    def clear_queue(self):
        with self.text_queue.mutex:
            self.text_queue.queue.clear()
        self.discard_current = True
        self._interrupt_flag.set()
        self._in_tts_quote = False
        self._in_asterisk = False
        self._bracket_depth = 0
        if self._loop and self._audio_buffer and self._loop.is_running():
            def _drain():
                while not self._audio_buffer.empty():
                    try:
                        self._audio_buffer.get_nowait()
                    except asyncio.QueueEmpty:
                        break
            self._loop.call_soon_threadsafe(_drain)
        try:
            self.lipsync_signal.emit(0.0)
        except Exception:
            pass
        logger.info("[PipelinedTTS] queue cleared, playback interrupted")

    def stop(self):
        self.is_running = False
        self.discard_current = True
        self._interrupt_flag.set()
        self._response_stream_open = False
        set_audio_playback_active(False)
        self.text_queue.put(None)

        if self._loop and self._loop.is_running():
            for task in (self._producer_task, self._player_task):
                if task and not task.done():
                    self._loop.call_soon_threadsafe(task.cancel)

        try:
            sd.stop()
        except Exception:
            pass

        self.quit()
        self.wait()
        logger.info("[PipelinedTTS] worker stopped")

    def run(self):
        logger.info(f"PipelinedTTSWorker started (method={self.tts_method}, "
                    f"buffer={self.AUDIO_BUFFER_SIZE})")

        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        self._audio_buffer = asyncio.Queue(maxsize=self.AUDIO_BUFFER_SIZE)

        self.discard_current = False
        self._interrupt_flag.clear()
        self._producer_busy = False
        self._player_busy = False
        self._response_stream_open = False

        self._producer_task = self._loop.create_task(self._producer_loop())
        self._player_task = self._loop.create_task(self._player_loop())

        try:
            self._loop.run_until_complete(
                asyncio.gather(self._producer_task, self._player_task,
                               return_exceptions=True)
            )
        except Exception as e:
            logger.error(f"[PipelinedTTS] run() error: {e}", exc_info=True)
        finally:
            try:
                self._loop.close()
            except Exception:
                pass
            logger.info("[PipelinedTTS] run() exited")

    async def _producer_loop(self):
        logger.info("[PipelinedTTS] producer loop started")

        if self.tts_method == "Qwen-3 TTS":
            try:
                self._ensure_tts_engines()
                self.qwen.start_warm_up(self.character_name)
            except Exception as e:
                logger.warning("[PipelinedTTS] warm-up failed: %s", e)

        while self.is_running:
            try:
                item = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self.text_queue.get(timeout=0.5)
                )
            except queue.Empty:
                continue
            except asyncio.CancelledError:
                logger.info("[PipelinedTTS] producer cancelled while waiting for text")
                break
            except Exception as e:
                logger.error("[PipelinedTTS] producer get error: %s", e)
                continue

            if item is None:
                logger.info("[PipelinedTTS] producer received poison pill")
                await self._audio_buffer.put(_AudioChunk(is_poison=True))
                break

            text, message_id = item
            if not text:
                continue
            if self.tts_method in _MERGE_BACKLOG_METHODS:
                text = _merge_queue_backlog(self.text_queue, text, message_id,
                                            min(self.chunk_max_chars, 300))

            self._producer_busy = True
            try:
                self.discard_current = False
                self._interrupt_flag.clear()
                logger.info("[PipelinedTTS] producer: generating '%s...'", text[:40])

                try:
                    self._ensure_tts_engines()
                except Exception as e:
                    logger.error("[PipelinedTTS] engine init failed: %s", e, exc_info=True)
                    continue

                output_file = None
                try:
                    output_file = await asyncio.wait_for(
                        self._generate_wav(text),
                        timeout=max(self.TTS_TIMEOUT_SEC, 15 + 0.6 * len(text))
                    )
                except asyncio.TimeoutError:
                    logger.error("[PipelinedTTS] TTS timed out for: '%s...'", text[:40])
                    continue
                except asyncio.CancelledError:
                    logger.info("[PipelinedTTS] producer cancelled during generation")
                    break
                except Exception as e:
                    logger.error("[PipelinedTTS] TTS generation error: %s", e, exc_info=True)
                    continue

                if self.discard_current:
                    logger.info("[PipelinedTTS] discarding generated segment (interrupted)")
                    try:
                        if output_file and os.path.exists(output_file):
                            os.remove(output_file)
                    except Exception:
                        pass
                    continue

                if not output_file or not os.path.exists(output_file):
                    logger.warning("[PipelinedTTS] no output file for '%s...'", text[:40])
                    continue

                try:
                    import base64
                    with open(output_file, "rb") as audio_file:
                        b64_audio = await asyncio.get_event_loop().run_in_executor(
                            None, lambda raw=audio_file.read(): base64.b64encode(raw).decode("utf-8")
                        )
                    self.audio_ready_signal.emit(b64_audio)
                except Exception as e:
                    logger.error("[PipelinedTTS] base64 encoding error: %s", e)

                if message_id:
                    try:
                        relative_path = await asyncio.get_event_loop().run_in_executor(
                            None, self._persist_segment_for_replay, output_file, message_id
                        )
                        if relative_path:
                            self.segment_saved_signal.emit(message_id, relative_path)
                    except Exception as e:
                        logger.error("[PipelinedTTS] persist error: %s", e)

                chunk = _AudioChunk(file_path=output_file, text=text, message_id=message_id, persist=False)
                await self._audio_buffer.put(chunk)
                logger.info("[PipelinedTTS] producer: enqueued '%s...' (buffer=%s)",
                            text[:40], self._audio_buffer.qsize())
            except asyncio.CancelledError:
                logger.info("[PipelinedTTS] producer task cancelled")
                break
            except Exception as e:
                logger.error("[PipelinedTTS] unexpected producer error: %s", e, exc_info=True)
            finally:
                self._producer_busy = False
                self._try_emit_queue_empty()

        logger.info("[PipelinedTTS] producer loop ended")

    async def _player_loop(self):
        logger.info("[PipelinedTTS] player loop started")

        while self.is_running:
            try:
                chunk = await self._audio_buffer.get()
            except asyncio.CancelledError:
                logger.info("[PipelinedTTS] player cancelled")
                break
            except Exception as e:
                logger.error(f"[PipelinedTTS] player get error: {e}")
                continue

            if chunk is None or chunk.is_poison:
                logger.info("[PipelinedTTS] player received poison pill")
                break

            # Mark busy immediately after dequeue. This closes a small race where
            # the producer could otherwise announce the queue empty before audio
            # playback had actually started.
            self._player_busy = True
            try:
                if not chunk.file_path or not os.path.exists(chunk.file_path):
                    logger.warning(f"[PipelinedTTS] player: missing file '{chunk.file_path}'")
                    continue

                if self._interrupt_flag.is_set():
                    logger.info(f"[PipelinedTTS] player: skipping '{chunk.text[:40]}...' (interrupted)")
                    try:
                        if not chunk.persist and os.path.exists(chunk.file_path):
                            os.remove(chunk.file_path)
                    except Exception:
                        pass
                    continue

                logger.info(f"[PipelinedTTS] player: playing '{chunk.text[:40]}...'")
                await self._play_audio_with_lipsync(chunk.file_path, chunk.persist)

                has_more_audio = (
                    not self._audio_buffer.empty()
                    or not self.text_queue.empty()
                    or self._producer_busy
                    or self._response_stream_open
                )
                if has_more_audio and self.chunk_pause_ms > 0 and not self._interrupt_flag.is_set():
                    await asyncio.sleep(self.chunk_pause_ms / 1000.0)
            except asyncio.CancelledError:
                logger.info("[PipelinedTTS] player cancelled while handling an audio chunk")
                raise
            except Exception as e:
                logger.error("[PipelinedTTS] player error while handling chunk: %s", e, exc_info=True)
            finally:
                self._player_busy = False
                self._try_emit_queue_empty()

        try:
            self.lipsync_signal.emit(0.0)
        except Exception:
            pass

        logger.info("[PipelinedTTS] player loop ended")

    async def _play_audio_with_lipsync(self, file_path: str, persist: bool):
        try:
            data, samplerate = await asyncio.get_event_loop().run_in_executor(
                None, lambda: sf.read(file_path, dtype='float32')
            )
        except Exception as e:
            logger.error(f"[PipelinedTTS] read error: {e}")
            try:
                if not persist and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            return

        if data is None or len(data) == 0:
            logger.warning(f"[PipelinedTTS] empty audio data for '{file_path}'")
            try:
                if not persist and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            return

        playback_handle = None
        playback_started = False
        playback_interrupted = False
        try:
            playback_handle = start_audio_playback(data, samplerate, self.device_index)
            playback_started = True
        except Exception as e:
            set_audio_playback_active(False)
            logger.error(f"[PipelinedTTS] audio playback start error: {e}")
            try:
                if not persist and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass
            return

        duration = len(data) / samplerate
        chunk_size = max(1, int(samplerate * self.LIPSYNC_POLL_SEC))
        total_samples = len(data)

        is_stereo = data.ndim > 1
        if is_stereo:
            data_mono = data.mean(axis=1)
        else:
            data_mono = data

        slept = 0.0
        sample_idx = 0
        smoothed_mouth_open = 0.0
        try:
            while slept < duration:
                if self._interrupt_flag.is_set():
                    playback_interrupted = True
                    self.lipsync_signal.emit(0.0)
                    logger.info(f"[PipelinedTTS] player: interrupted at {slept:.2f}/{duration:.2f}s")
                    break

                end_idx = min(sample_idx + chunk_size, total_samples)
                current_chunk = data_mono[sample_idx:end_idx]
                if len(current_chunk) > 0:
                    rms = float(np.sqrt(np.mean(current_chunk ** 2)))
                    target_mouth_open = min(rms * 5.0, 1.0)
                    if self.lipsync_smoothing:
                        # Faster attack, softer release prevents mouth jitter.
                        alpha = 0.62 if target_mouth_open > smoothed_mouth_open else 0.24
                        smoothed_mouth_open += alpha * (target_mouth_open - smoothed_mouth_open)
                        mouth_open = smoothed_mouth_open
                    else:
                        mouth_open = target_mouth_open
                    try:
                        self.lipsync_signal.emit(float(mouth_open))
                    except Exception:
                        pass

                await asyncio.sleep(self.LIPSYNC_POLL_SEC)
                slept += self.LIPSYNC_POLL_SEC
                sample_idx += chunk_size

        except asyncio.CancelledError:
            playback_interrupted = True
            try:
                self.lipsync_signal.emit(0.0)
            except Exception:
                pass
            raise
        except Exception as e:
            logger.error(f"[PipelinedTTS] lipsync loop error: {e}")
        finally:

            try:
                self.lipsync_signal.emit(0.0)
            except Exception:
                pass

            if playback_started:
                try:
                    interrupted_now = playback_interrupted or self._interrupt_flag.is_set()
                    await asyncio.get_event_loop().run_in_executor(
                        None,
                        lambda: finish_audio_playback(
                            playback_handle,
                            interrupted=interrupted_now,
                            timeout=max(5.0, duration + 3.0),
                        ),
                    )
                except Exception:
                    logger.debug("Error finalizing pipelined playback", exc_info=True)
            else:
                set_audio_playback_active(False)

            try:
                if not persist and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

    async def _generate_wav(self, text: str) -> Optional[str]:
        import time as _time
        started = _time.time()
        path = None
        try:
            path = await self._generate_wav_impl(text)
            return path
        finally:
            try:
                from app.utils.runtime_stats import stats as _stats
                audio_s = None
                if path and str(path).lower().endswith(".wav"):
                    try:
                        import wave
                        with wave.open(str(path), "rb") as _w:
                            audio_s = _w.getnframes() / float(_w.getframerate())
                    except Exception:
                        audio_s = None
                _stats.record_tts(str(self.tts_method), len(text or ""), _time.time() - started, audio_s, ok=bool(path))
            except Exception:
                pass

    async def _generate_wav_impl(self, text: str) -> Optional[str]:
        method = self.tts_method
        if method == "XTTSv2":
            return await self.xtts.generate_speech_with_xttsv2_sow_system(
                text, self.language, self.character_name)
        elif method == "Edge TTS":
            return await self.edge.generate_speech_with_edge_tts_sow_system(
                text, self.character_name)
        elif method == "Kokoro":
            return await self.kokoro.generate_speech_with_kokoro(
                text, self.character_name)
        elif method == "Silero":
            return await self.silero.generate_speech_with_silero(
                text, self.character_name)
        elif method == "Qwen-3 TTS":
            return await self.qwen.generate_speech_with_qwen3(
                text, self.character_name)
        elif method == "ElevenLabs":
            return await self.eleven.generate_speech_with_elevenlabs_sow_system(
                text, self.voice_id)
        else:
            logger.error(f"[PipelinedTTS] unknown TTS method: {method}")
            return None

    def _persist_segment_for_replay(self, source_file, message_id):
        if not source_file or not os.path.exists(source_file):
            return None

        segment_dir = os.path.join(
            os.getcwd(), "app", "data", ".soul",
            self.character_name, "tts_audio", message_id
        )
        os.makedirs(segment_dir, exist_ok=True)

        existing = [f for f in os.listdir(segment_dir)
                    if f.lower().endswith((".wav", ".mp3"))]
        next_index = len(existing) + 1
        ext = os.path.splitext(source_file)[1] or ".wav"
        segment_filename = f"seg_{next_index:04d}{ext}"
        destination = os.path.join(segment_dir, segment_filename)

        shutil.copyfile(source_file, destination)
        return f"tts_audio/{message_id}/{segment_filename}"
