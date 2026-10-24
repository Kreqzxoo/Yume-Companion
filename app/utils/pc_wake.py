"""'Hey Yume' on the PC: always listening in the background (also with the chat closed), a small overlay with the 3D character appears, you talk, she answers.

Built from the program's own parts: the microphone worker with voice activity detection and echo guard, and Whisper. Everything that is heard is checked
for the wake phrase first; nothing is stored or sent anywhere. The overlay is a small always-on-top card (VRM model of the character, state, what was heard).
"""
from __future__ import annotations

import asyncio
import difflib
import logging
import os
import re
import time

from PyQt6 import QtCore, QtGui, QtWidgets

logger = logging.getLogger("PcWake")

GREETINGS = {"hey", "hallo", "hi", "ok", "okay", "he", "hej", "na"}
END_WORDS = {"tschüss", "tschüs", "ende", "stopp", "stop", "abbrechen", "danke das wars", "das wars", "das wär's", "bis später", "schluss"}


def _norm(text: str) -> str:
    return " ".join(re.sub(r"[^\w\säöüß]", " ", (text or "").lower()).split())


def match_wake(text: str, phrases: list[str]) -> tuple[bool, str]:
    """(heard the wake phrase at the start, the rest of the sentence). 'Hey Yume wie spät ist es' -> (True, 'wie spät ist es')."""
    words = _norm(text).split()
    if not words:
        return False, ""
    for phrase in phrases:
        core = [w for w in _norm(phrase).split() if w not in GREETINGS]
        if not core:
            continue
        core_s = " ".join(core)
        start = 1 if words[0] in GREETINGS and len(words) > 1 else 0
        for skip in sorted({0, start}):
            for n in range(max(1, len(core) - 1), len(core) + 2):      # the name may be one word more or less ("yume" / "yume")
                if skip + n > len(words):
                    continue
                heard = " ".join(words[skip:skip + n])
                if heard == core_s or difflib.SequenceMatcher(None, heard.replace(" ", ""), core_s.replace(" ", "")).ratio() >= 0.74:
                    return True, " ".join(words[skip + n:])
    return False, ""


class PcWakeOverlay(QtWidgets.QWidget):
    """Small always-on-top card in the lower right corner. Never takes the focus away from what you are doing."""

    def __init__(self, view_url: str = "", avatar_path: str = ""):
        flags = (QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint | QtCore.Qt.WindowType.Tool
                 | QtCore.Qt.WindowType.WindowDoesNotAcceptFocus)
        super().__init__(None, flags)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedSize(300, 410 if view_url else 190)
        self.web = None
        card = QtWidgets.QFrame(self)
        card.setObjectName("card")
        card.setStyleSheet("#card { background: rgba(22, 14, 34, 235); border: 1px solid rgba(255, 143, 199, 120); border-radius: 22px; } QLabel { background: transparent; border: none; }")
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(card)
        lay = QtWidgets.QVBoxLayout(card)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(6)
        if view_url:
            try:
                from PyQt6.QtWebEngineWidgets import QWebEngineView
                self.web = QWebEngineView()
                self.web.setFixedSize(272, 230)
                self.web.page().setBackgroundColor(QtGui.QColor(0, 0, 0, 0))
                self.web.setStyleSheet("background: transparent;")
                self.web.load(QtCore.QUrl(view_url))
                lay.addWidget(self.web, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
            except Exception:
                logger.debug("overlay: web view not available", exc_info=True)
                self.web = None
        if self.web is None and avatar_path and os.path.isfile(avatar_path):
            pic = QtWidgets.QLabel()
            pix = QtGui.QPixmap(avatar_path).scaled(72, 72, QtCore.Qt.AspectRatioMode.KeepAspectRatioByExpanding, QtCore.Qt.TransformationMode.SmoothTransformation)
            pic.setPixmap(pix)
            pic.setFixedSize(72, 72)
            lay.addWidget(pic, alignment=QtCore.Qt.AlignmentFlag.AlignHCenter)
        self.state = QtWidgets.QLabel("Ich höre zu …")
        self.state.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.state.setStyleSheet("color: #ff8fc7; font-size: 15px; font-weight: bold;")
        self.heard = QtWidgets.QLabel("")
        self.heard.setWordWrap(True)
        self.heard.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.heard.setStyleSheet("color: rgba(255,255,255,0.8); font-size: 12px;")
        self.level = QtWidgets.QProgressBar()
        self.level.setRange(0, 100)
        self.level.setTextVisible(False)
        self.level.setFixedHeight(5)
        self.level.setStyleSheet("QProgressBar { background: rgba(255,255,255,0.1); border: none; border-radius: 2px; } QProgressBar::chunk { background: #b69cff; border-radius: 2px; }")
        lay.addWidget(self.state)
        lay.addWidget(self.heard)
        lay.addWidget(self.level)
        self._hide_timer = QtCore.QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

    def present(self):
        self._hide_timer.stop()
        screen = QtGui.QGuiApplication.primaryScreen().availableGeometry()
        self.move(screen.right() - self.width() - 24, screen.bottom() - self.height() - 24)
        self.show()
        self.raise_()

    def hide_later(self, ms: int = 2500):
        self._hide_timer.start(ms)

    def set_state(self, text: str):
        self.state.setText(text)

    def set_heard(self, text: str):
        self.heard.setText(text[:180])

    def set_level(self, value: float):
        self.level.setValue(int(max(0.0, min(1.0, value)) * 100))

    def run_js(self, code: str):
        if self.web is not None:
            try:
                self.web.page().runJavaScript(code)
            except Exception:
                pass


class PcWake(QtCore.QObject):
    """Owns the microphone / Whisper workers, the wake-phrase logic and the overlay."""

    def __init__(self, signals):
        super().__init__()
        self.signals = signals
        self.audio = None
        self.stt = None
        self.overlay: PcWakeOverlay | None = None
        self.active_until = 0.0
        self.busy_until = 0.0
        self.running = False
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(1000)
        self.timer.timeout.connect(self._tick)

    # ------------------------------------------------------------------ settings
    def _setting(self, key, default=None):
        try:
            value = self.signals.configuration_settings.get_main_setting(key)
            return default if value is None else value
        except Exception:
            return default

    def phrases(self) -> list[str]:
        out = [str(self._setting("pcwake_phrase", "Hey Yume") or "Hey Yume")]
        name = str(getattr(self.signals, "current_active_character", "") or "")
        if name:
            out.append(name)
        return out

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> bool:
        if self.running:
            return True
        try:
            from app.utils.speech_to_text import AudioInputWorker, STTWorker, load_main_settings
            from app.utils.voice_runtime import WakeWordGate
        except Exception:
            logger.warning("Hey Yume: speech modules not available", exc_info=True)
            return False
        device = str(self._setting("whisper_device", "cpu") or "cpu").lower()
        dev_arg = "cuda:0" if device == "cuda" else "cpu"
        self.stt = STTWorker(model_size="small", device=dev_arg, compute_type="float16" if dev_arg.startswith("cuda") else "int8")
        self.stt.voice_settings = {**load_main_settings(), "wake_word_enabled": False}       # the wake phrase is handled here, not by the chat's gate
        self.stt.wake_word_gate = WakeWordGate(self.stt.voice_settings)
        self.stt.text_ready_signal.connect(self.on_text)
        self.stt.start()
        index = self._setting("input_device_index", None)
        try:
            index = int(index) if index not in (None, "") else None
        except (TypeError, ValueError):
            index = None
        self.audio = AudioInputWorker(input_device_index=index)
        self.audio.audio_packet_ready.connect(self.stt.add_audio)
        self.audio.audio_packet_ready.connect(self._voice_mood)
        self.audio.volume_signal.connect(self._on_level)
        self.audio.start()
        self.running = True
        self.timer.start()
        wb = getattr(self.signals, "web_bridge", None)
        if wb is not None and self._on_bridge_event not in wb.listeners:
            wb.listeners.append(self._on_bridge_event)
        logger.info("Hey Yume is listening (phrases: %s)", ", ".join(self.phrases()))
        return True

    def _voice_mood(self, pcm: bytes):
        if not bool(self._setting("voice_mood", False)):
            return
        try:
            from app.utils import voice_mood, mood
            label = voice_mood.observe(pcm)
            if label:
                mood.from_voice(label)
        except Exception:
            logger.debug("voice mood failed", exc_info=True)

    def _on_bridge_event(self, kind: str):
        """Follows the chat stream: the overlay shows 'schreibt' / 'spricht' and the microphone ignores her own voice while she talks."""
        if self.overlay is None or not self.overlay.isVisible():
            return
        now = time.time()
        if kind == "chunk":
            self.overlay.set_state("schreibt …")
            self.busy_until = max(self.busy_until, now + 3)
        elif kind == "audio":
            self.overlay.set_state("spricht …")
            self.busy_until = max(self.busy_until, now + 4)
        elif kind == "message_end":
            self.busy_until = now + 3                           # the voice may still play for a moment
            QtCore.QTimer.singleShot(3200, lambda: self.overlay is not None and self.overlay.isVisible() and self.overlay.set_state("Ich höre zu …"))

    def stop(self):
        self.timer.stop()
        wb = getattr(self.signals, "web_bridge", None)
        if wb is not None and self._on_bridge_event in wb.listeners:
            wb.listeners.remove(self._on_bridge_event)
        for w in (self.audio, self.stt):
            try:
                if w is not None:
                    w.stop()
            except Exception:
                pass
        self.audio = self.stt = None
        self.running = False
        if self.overlay is not None:
            self.overlay.hide()

    # ------------------------------------------------------------------ overlay
    def _make_overlay(self):
        url, avatar = "", ""
        try:
            chars = self.signals.configuration_characters.load_configuration().get("character_list", {})
            name = getattr(self.signals, "current_active_character", None) or next(iter(chars), "")
            info = chars.get(name, {})
            avatar = str(info.get("character_avatar") or "")
            vrm = str(info.get("vrm_model_file") or "")
            if bool(self._setting("pcwake_vrm", True)) and vrm and os.path.isfile(vrm):
                from app.utils.vrm_server import VRMServerThread
                server = getattr(self.signals, "server_thread", None)
                if server is None or not server.is_alive():
                    server = VRMServerThread(preferred_port=8001)
                    server.start()
                    self.signals.server_thread = server
                root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
                rel = os.path.relpath(vrm, root).replace("\\", "/")
                url = f"http://127.0.0.1:{server.port}/app/utils/emotions/vrm_module.html?model=/{rel}"
        except Exception:
            logger.debug("overlay: no VRM", exc_info=True)
        self.overlay = PcWakeOverlay(url, avatar)

    def _show(self, state: str):
        if self.overlay is None:
            self._make_overlay()
        self.overlay.set_state(state)
        self.overlay.present()

    def _on_level(self, value: float):
        if self.overlay is not None and self.overlay.isVisible():
            self.overlay.set_level(value)
            now = time.time()
            if now - getattr(self, "_last_js", 0) > 0.08:                 # the mouth moves with your voice, not more often than 12 times a second
                self._last_js = now
                self.overlay.run_js(f"if (window.setMouthOpen) setMouthOpen({max(0.0, min(1.0, value)):.2f})")

    # ------------------------------------------------------------------ logic
    def _paused(self) -> bool:
        try:
            if str(getattr(self.signals, "interaction_state", "STOPPED") or "STOPPED") != "STOPPED":
                return True
            wb = getattr(self.signals, "web_bridge", None)
            return bool(wb is not None and any(m.get("call") for m in wb.manager.meta.values()))
        except Exception:
            return False

    @property
    def awake(self) -> bool:
        return time.time() < self.active_until

    def on_text(self, text: str):
        if not self.running or self._paused():
            return
        now = time.time()
        if now < self.busy_until:                                   # she is speaking: what the microphone hears is probably her own voice
            return
        seconds = float(self._setting("pcwake_seconds", 25) or 25)
        if not self.awake:
            ok, rest = match_wake(text, self.phrases())
            if not ok:
                return
            if bool(self._setting("pcwake_chime", True)):
                QtWidgets.QApplication.beep()
            self.active_until = now + seconds
            self._show("Ich höre zu …")
            if rest.strip():
                self._send(rest.strip())
            return
        norm = _norm(text)
        if norm in END_WORDS or any(norm.startswith(w + " ") and len(norm.split()) <= 4 for w in ("tschüss", "stopp", "ende")):
            try:
                self.signals.stop_generation()
            except Exception:
                pass
            self.active_until = 0.0
            if self.overlay is not None:
                self.overlay.set_state("Bis später!")
                self.overlay.hide_later(1500)
            return
        self.active_until = now + seconds
        self._send(text.strip())

    def _send(self, text: str):
        if self.overlay is not None:
            self.overlay.set_heard("„" + text + "“")
            self.overlay.set_state("denkt nach …")
        self.busy_until = time.time() + 120                          # until the reply is over (message_end releases it earlier)
        asyncio.ensure_future(self._turn(text))

    async def _turn(self, text: str):
        try:
            chars = (await asyncio.to_thread(self.signals.configuration_characters.load_configuration)).get("character_list", {})
            name = str(getattr(self.signals, "current_active_character", "") or "") or next(iter(chars), "")
            if not name or name not in chars:
                return
            wb = getattr(self.signals, "web_bridge", None)
            if str(getattr(self.signals, "current_active_character", "")) != name:
                if wb is not None:
                    await wb._open_chat_quietly(name)
                else:
                    await self.signals.open_chat(name)
            await self.signals.handle_user_message(name, chars[name].get("conversation_method", "Local LLM"), external_text=text)
        except Exception:
            logger.warning("Hey Yume: the message could not be handled", exc_info=True)
        finally:
            self.busy_until = time.time() + 1.5
            self.active_until = time.time() + float(self._setting("pcwake_seconds", 25) or 25)
            if self.overlay is not None and self.overlay.isVisible():
                self.overlay.set_state("Ich höre zu …")

    def _tick(self):
        if self.overlay is not None and self.overlay.isVisible() and not self.awake and time.time() >= self.busy_until:
            self.overlay.hide_later(300)
