import io
import os
import re
import json
import time
import uuid
import base64
import shutil
import asyncio
import logging
import datetime
import threading
from pathlib import Path

from PIL import Image
from PyQt6 import QtCore

import discord
from discord import app_commands
from discord.ext import commands

from app.configuration.configuration import ConfigurationAPI, ConfigurationCharacters

logger = logging.getLogger(__name__)

DISCORD_MAX_MESSAGE_LENGTH = 2000
DISCORD_STREAM_PREVIEW_LIMIT = 1900
DISCORD_STREAM_EDIT_INTERVAL = 1.5
DISCORD_USER_COOLDOWN_SECONDS = 5
DISCORD_MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024
DISCORD_QUEUE_SIZE = 16
DISCORD_BUSY_WAIT_TIMEOUT = 600

BUSY_NOTICE_TEXT = "*The character is still responding — your message was queued.*"
GENERIC_ERROR_TEXT = "*Internal bot error. Check the application logs for details.*"
EMPTY_MESSAGE_HINT = (
    "*I received your message but couldn't see any text in it. "
    "If this keeps happening with normal messages, enable the "
    "'Message Content Intent' toggle for this bot in the Discord Developer Portal.*"
)
UNREADABLE_ATTACHMENT_TEXT = "*I can't read that file type — send text or an image instead.*"

BINDINGS_PATH = Path("app/configuration/discord_bindings.json")
KNOWN_USERS_PATH = Path("app/configuration/discord_users.json")

IMAGE_EXTENSIONS = ('.png', '.jpg', '.jpeg', '.webp', '.bmp', '.gif')


def split_message(text: str, limit: int = DISCORD_MAX_MESSAGE_LENGTH) -> list[str]:
    text = text or ""
    if len(text) <= limit:
        return [text] if text else []

    def _cut(chunk: str) -> list[str]:
        pieces = []
        remaining = chunk
        while len(remaining) > limit:
            window = remaining[:limit]
            cut = max(
                window.rfind("\n\n"),
                window.rfind("\n"),
                window.rfind(". "),
                window.rfind("! "),
                window.rfind("? "),
                window.rfind(" "),
            )
            if cut < int(limit * 0.3):
                cut = limit
            head, tail = remaining[:cut].rstrip(), remaining[cut:].lstrip("\n")
            if head:
                pieces.append(head)
            remaining = tail
        if remaining:
            pieces.append(remaining)
        return pieces

    parts = _cut(text)

    fenced = any(p.count("```") % 2 == 1 for p in parts)
    if not fenced:
        return parts

    fixed = []
    fence_open = False
    for part in parts:
        body = part
        if fence_open:
            body = "```\n" + body
            fence_open = False
        if body.count("```") % 2 == 1:
            body = body.rstrip("` \n").rstrip() + "\n```"
            fence_open = True
        fixed.append(body)
    return fixed


def strip_text_for_speech(text: str, max_chars: int = 700) -> str:
    text = text or ""
    text = re.sub(r"```.*?```", " (code snippet) ", text, flags=re.DOTALL)
    text = re.sub(r"`([^`]*)`", r"\1", text)
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"\*\*([^*]*)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]*)\*", r"\1", text)
    text = re.sub(r"^>\s?", "", text, flags=re.MULTILINE)
    text = re.sub(r":[a-z_]+:", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        cut = text.rfind(". ", 0, max_chars)
        text = text[: cut + 1 if cut > max_chars // 2 else max_chars]
    return text


class DiscordStreamSession:
    def __init__(self, anchor_message: discord.Message):
        self._anchor = anchor_message
        self._target: discord.Message | None = None
        self._lock = asyncio.Lock()
        self._last_edit: float = 0.0
        self._finished = False
        self._cancelled = False
        self.active = False
        self.final_text: str = ""

    async def update(self, partial_text: str):
        if self._finished or self._cancelled or not self._anchor:
            return
        async with self._lock:
            if self._finished or self._cancelled:
                return
            now = time.monotonic()
            if self._target is not None and (now - self._last_edit) < DISCORD_STREAM_EDIT_INTERVAL:
                return

            content = (partial_text or "").strip()
            if not content:
                return
            if len(content) > DISCORD_STREAM_PREVIEW_LIMIT:
                content = content[:DISCORD_STREAM_PREVIEW_LIMIT].rstrip() + " …"

            try:
                if self._target is None:
                    self._target = await self._anchor.reply(content)
                    self.active = True
                else:
                    await self._target.edit(content=content)
                self._last_edit = time.monotonic()
            except Exception as e:
                logger.debug(f"[stream-preview] edit failed: {e}")

    async def finish(self, final_text: str) -> bool:
        if self._cancelled or not self._anchor:
            return False
        async with self._lock:
            self._finished = True
            final_text = (final_text or "").strip()
            self.final_text = final_text

            if not self.active or self._target is None:
                return False

            if 0 < len(final_text) <= DISCORD_MAX_MESSAGE_LENGTH:
                try:
                    await self._target.edit(content=final_text)
                    return True
                except Exception as e:
                    logger.debug(f"[stream-preview] final edit failed: {e}")
                    return False

            try:
                await self._target.delete()
            except Exception:
                pass
            return False

    async def cancel(self):
        async with self._lock:
            self._finished = True
            self._cancelled = True


class _JsonStore:
    def __init__(self, path: Path, default: dict):
        self.path = path
        self.default = default
        self._lock = threading.Lock()
        self._data: dict | None = None

    def _load(self) -> dict:
        if self._data is not None:
            return self._data
        try:
            if self.path.exists():
                self._data = json.loads(self.path.read_text(encoding="utf-8"))
            else:
                self._data = dict(self.default)
        except Exception as e:
            logger.warning(f"Could not load {self.path}: {e}")
            self._data = dict(self.default)
        return self._data

    def get(self) -> dict:
        with self._lock:
            return self._load()

    def mutate(self, fn) -> dict:
        with self._lock:
            data = self._load()
            fn(data)
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                tmp = self.path.with_suffix(".tmp")
                tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
                os.replace(tmp, self.path)
            except Exception as e:
                logger.error(f"Could not save {self.path}: {e}")
            return data


def _find_ffmpeg() -> str | None:
    local = Path("app/ffmpeg/bin/ffmpeg.exe")
    if local.exists():
        return str(local)
    return shutil.which("ffmpeg")


async def _fallback_tts(text: str) -> str | None:
    try:
        import edge_tts
        has_cyrillic = any("\u0400" <= ch <= "\u04FF" for ch in text)
        voice = "ru-RU-SvetlanaNeural" if has_cyrillic else "en-US-AriaNeural"
        out = Path("app/voices/edge_tts_audio") / f"vc_fallback_{uuid.uuid4().hex}.mp3"
        out.parent.mkdir(parents=True, exist_ok=True)
        await edge_tts.Communicate(text, voice).save(str(out))
        return str(out)
    except Exception as e:
        logger.warning(f"Fallback TTS failed: {e}")
        return None


class DiscordBotManager(QtCore.QObject):
    state_changed = QtCore.pyqtSignal(str)

    STATES = {"starting", "running", "stopped", "error"}

    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.is_running = False
        self.connection_state = "stopped"
        self._bot_task = None
        self.token = ""

        self.bot = None
        self._tree_synced = False
        self._init_bot()

        self.chat_lock = asyncio.Lock()
        self._msg_queue: asyncio.Queue = asyncio.Queue(maxsize=DISCORD_QUEUE_SIZE)
        self._worker_task: asyncio.Task | None = None
        self._cooldowns: dict[int, float] = {}

        self.bindings = _JsonStore(BINDINGS_PATH, {})
        self.known_users = _JsonStore(KNOWN_USERS_PATH, {})

        self._vc_tts_engines: dict[str, object] = {}

        self._config_cache: dict = {}
        self._config_dirty: bool = True
        self._config_loaded_at: float = 0.0

    def _set_state(self, state: str, detail: str = ""):
        if state not in self.STATES:
            return
        self.connection_state = state
        self.is_running = state in ("starting", "running")
        logger.info(f"[Discord] state -> {state} {detail}".rstrip())
        try:
            self.state_changed.emit(state if state != "error" else f"error:{detail[:200]}")
        except Exception:
            pass

    def _init_bot(self):
        intents = discord.Intents.default()
        intents.message_content = True
        self.bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)
        self._register_app_commands()
        self._register_prefix_commands()
        self._register_events()

    def invalidate_config_cache(self):
        self._config_dirty = True

    def _get_char_config(self, char_name: str) -> dict:
        if self._config_dirty or (time.monotonic() - self._config_loaded_at) > 5.0:
            try:
                char_config_api = ConfigurationCharacters()
                all_chars = char_config_api.load_configuration()
                self._config_cache = all_chars.get("character_list", {})
            except Exception as e:
                logger.error(f"Could not refresh character config cache: {e}")
                if self._config_dirty:
                    self._config_cache = {}
            self._config_dirty = False
            self._config_loaded_at = time.monotonic()
        return self._config_cache.get(char_name, {})

    def start_bot(self):
        if self.is_running:
            return

        config_api = ConfigurationAPI()
        self.token = config_api.get_token("DISCORD_BOT_TOKEN")

        if not self.token:
            logger.warning("No Discord token found.")
            self._set_state("error", "No Discord bot token configured.")
            return

        try:
            self._init_bot()
            self._tree_synced = False
            self._ensure_worker()

            loop = asyncio.get_running_loop()
            self._set_state("starting")
            self._bot_task = loop.create_task(self.bot.start(self.token))
            self._bot_task.add_done_callback(self._on_bot_task_done)
            logger.info("Discord Bot task started.")
        except Exception as e:
            self._set_state("error", str(e))
            logger.error(f"Failed to start Discord Bot: {e}")

    def _on_bot_task_done(self, task: asyncio.Task):
        if task.cancelled():
            self._set_state("stopped")
            logger.info("Discord Bot task was cancelled.")
            return
        exc = task.exception()
        if exc:
            self._set_state("error", f"{type(exc).__name__}: {exc}")
            logger.error("Discord Bot task crashed.", exc_info=exc)
        else:
            self._set_state("stopped")

    async def stop_bot(self):
        if not self.is_running and not (self._bot_task and not self._bot_task.done()):
            self._set_state("stopped")
            return

        logger.info("Stopping Discord Bot...")
        self._set_state("stopped")

        if self.bot:
            try:
                await self.bot.close()
            except Exception as e:
                logger.warning(f"Error while closing bot: {e}")

        if self._worker_task and not self._worker_task.done():
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None

        if self._bot_task and not self._bot_task.done():
            self._bot_task.cancel()
            try:
                await self._bot_task
            except asyncio.CancelledError:
                pass

        logger.info("Discord Bot stopped.")

    def _allowed_ids(self, key: str) -> set[str]:
        raw = ConfigurationAPI().get_token(key) or ""
        return {part.strip() for part in re.split(r"[,\s;]+", str(raw)) if part.strip().isdigit()}

    def _is_allowed(self, message: discord.Message) -> tuple[bool, str]:
        user_ids = self._allowed_ids("DISCORD_ALLOWED_USER_IDS")
        guild_ids = self._allowed_ids("DISCORD_ALLOWED_GUILD_IDS")
        channel_ids = self._allowed_ids("DISCORD_ALLOWED_CHANNEL_IDS")

        if user_ids and str(message.author.id) not in user_ids:
            return False, "user is not whitelisted"
        if guild_ids and (message.guild is None or str(message.guild.id) not in guild_ids):
            return False, "guild is not whitelisted"
        if channel_ids:
            if isinstance(message.channel, discord.DMChannel):
                return False, "channel whitelist set but this is a DM"
            if str(message.channel.id) not in channel_ids:
                return False, "channel is not whitelisted"
        return True, ""

    def _resolve_character(self, channel_id: int | None) -> str | None:
        if channel_id is not None:
            bound = self.bindings.get().get(str(channel_id))
            if bound:
                available = self._get_char_config(bound) or bound in self._config_cache
                if available:
                    return bound
                logger.warning(f"[Discord] bound character '{bound}' no longer exists — falling back")
        return getattr(self.main_window.interface_signals, "current_active_character", None)

    def describe_known_users(self, exclude_user_id: str | None = None, limit: int = 12) -> str:
        users = self.known_users.get()
        lines = []
        for uid, info in sorted(
            users.items(),
            key=lambda kv: kv[1].get("last_seen", ""),
            reverse=True,
        ):
            if exclude_user_id and uid == str(exclude_user_id):
                continue
            name = info.get("display_name") or f"user {uid}"
            count = info.get("message_count", 0)
            notes = (info.get("notes") or "").strip()
            line = f"- {name} (id {uid}, ~{count} messages)"
            if notes:
                line += f": {notes}"
            lines.append(line)
            if len(lines) >= limit:
                break
        if not lines:
            return ""
        return "People you have already met on Discord:\n" + "\n".join(lines)

    def _record_user(self, user: discord.abc.User):
        def _update(data: dict):
            entry = data.setdefault(str(user.id), {
                "display_name": getattr(user, "display_name", None) or user.name,
                "first_seen": time.strftime("%Y-%m-%d"),
                "last_seen": "",
                "message_count": 0,
                "notes": "",
            })
            entry["display_name"] = getattr(user, "display_name", None) or user.name
            entry["last_seen"] = time.strftime("%Y-%m-%d %H:%M")
            entry["message_count"] = int(entry.get("message_count", 0)) + 1

        try:
            self.known_users.mutate(_update)
        except Exception as e:
            logger.debug(f"Could not record user stats: {e}")

    def _check_cooldown(self, user_id: int) -> bool:
        admins = self._allowed_ids("DISCORD_ALLOWED_USER_IDS")
        if str(user_id) in admins:
            return True
        now = time.monotonic()
        last = self._cooldowns.get(user_id, 0.0)
        if now - last < DISCORD_USER_COOLDOWN_SECONDS:
            return False
        self._cooldowns[user_id] = now
        return True

    def _register_events(self):
        @self.bot.event
        async def on_ready():
            logger.info(f"Discord bot logged in as {self.bot.user}")
            self._set_state("running")

            ui = getattr(self.main_window, "ui", None)
            toast = getattr(ui, "toast_notification", None) if ui else None
            if toast:
                toast.show_toast(f"Discord Bot online: {self.bot.user}", "app/gui/icons/discord.png")

            if not self._tree_synced:
                self._tree_synced = True
                try:
                    await self.bot.tree.sync()
                    for guild in list(self.bot.guilds)[:25]:
                        try:
                            await self.bot.tree.sync(guild=guild)
                        except Exception:
                            pass
                    logger.info("Slash commands synced.")
                except Exception as e:
                    logger.warning(f"Slash command sync failed: {e}")

        @self.bot.event
        async def on_message(message: discord.Message):
            try:
                if message.author == self.bot.user or message.author.bot:
                    return

                allowed, reason = self._is_allowed(message)
                if not allowed:
                    logger.debug(f"on_message: dropped ({reason}): {message.author}")
                    return

                await self.bot.process_commands(message)

                ctx = await self.bot.get_context(message)
                if ctx.valid:
                    logger.debug(f"on_message: ignored (matched a command: {message.content!r})")
                    return

                is_dm = isinstance(message.channel, discord.DMChannel)
                is_mentioned = self.bot.user and self.bot.user.mentioned_in(message)
                if not is_dm and not is_mentioned:
                    return

                clean_text = message.clean_content if hasattr(message, "clean_content") else message.content
                logger.info(f"on_message: accepted from {message.author}: {clean_text!r}")

                if not self._check_cooldown(message.author.id):
                    await self._safe_reply(message, "*Slow down a little — you're sending messages too fast.*")
                    return

                await self._enqueue_message_job(message, clean_text)

            except Exception as e:
                logger.error(f"Unhandled error in on_message: {e}", exc_info=True)
                try:
                    await message.channel.send(GENERIC_ERROR_TEXT)
                except Exception as send_err:
                    logger.error(f"Also failed to notify the channel: {send_err}", exc_info=True)

    def _ensure_worker(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.get_running_loop().create_task(self._queue_worker())

    async def _enqueue_message_job(self, message: discord.Message, clean_text: str):
        self._ensure_worker()

        if self._msg_queue.qsize() >= DISCORD_QUEUE_SIZE:
            await self._safe_reply(message, "*My queue is full right now — please try again in a minute.*")
            return

        position = self._msg_queue.qsize() + 1
        try:
            await message.add_reaction("👍")
        except Exception:
            pass
        if position > 1:
            await self._safe_reply(message, f"*Queued (position {position}).*")

        await self._msg_queue.put({
            "kind": "message",
            "message": message,
            "text": clean_text,
            "channel": message.channel,
            "author": message.author,
        })

    async def _wait_for_idle_generation(self, notify) -> bool:
        waited = 0.0
        notified = False
        signals = self.main_window.interface_signals
        while getattr(signals, "_is_generating", False):
            if not notified and waited >= 3.0:
                notified = True
                await notify()
            if waited >= DISCORD_BUSY_WAIT_TIMEOUT:
                return False
            await asyncio.sleep(0.5)
            waited += 0.5
        return True

    async def _queue_worker(self):
        while True:
            job = await self._msg_queue.get()
            try:
                signals = self.main_window.interface_signals
                channel = job.get("channel")

                async def _notify_busy(channel=channel):
                    try:
                        await channel.send(BUSY_NOTICE_TEXT)
                    except Exception:
                        pass

                if not await self._wait_for_idle_generation(_notify_busy):
                    try:
                        await channel.send("*Waited too long for the character to become free — request dropped.*")
                    except Exception:
                        pass
                    continue

                if job["kind"] == "message":
                    await self.process_ai_response(job["message"], job["text"])
                elif job["kind"] == "interaction":
                    await self._run_interaction_job(job)
                elif job["kind"] == "interaction":
                    await self._run_interaction_job(job)
            except asyncio.CancelledError:
                signals = self.main_window.interface_signals
                if getattr(signals, "_is_generating", False):
                    signals._is_generating = False
                raise
            except Exception as e:
                logger.error(f"Queue worker error: {e}", exc_info=True)
                try:
                    await job.get("channel").send(GENERIC_ERROR_TEXT)
                except Exception:
                    pass
            finally:
                self._msg_queue.task_done()

    async def process_discord_attachments(self, message: discord.Message) -> tuple[list[dict], list[str]]:
        encoded_images: list[dict] = []
        other_files: list[str] = []

        if not message.attachments:
            return encoded_images, other_files

        for att in message.attachments:
            is_image = att.filename.lower().endswith(IMAGE_EXTENSIONS)
            if not is_image:
                other_files.append(att.filename)
                continue
            if att.size and att.size > DISCORD_MAX_ATTACHMENT_BYTES:
                logger.warning(f"Skipped oversized attachment '{att.filename}' ({att.size} bytes)")
                other_files.append(f"{att.filename} (too large to read)")
                continue
            try:
                data = await att.read()
                with Image.open(io.BytesIO(data)) as img:
                    img = img.convert("RGB") if img.mode not in ("RGB", "RGBA") else img
                    width, height = img.size
                    max_dim = 1536

                    if max(width, height) > max_dim:
                        scale = max_dim / float(max(width, height))
                        resample_filter = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
                        img = img.resize((max(1, int(width * scale)), max(1, int(height * scale))), resample_filter)

                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG")
                    b64_data = base64.b64encode(buffer.getvalue()).decode("utf-8")
                    encoded_images.append({"mime": "image/png", "b64": b64_data})
            except Exception as e:
                logger.error(f"Failed to process Discord image attachment '{att.filename}': {e}")

        return encoded_images, other_files

    async def fetch_channel_history_context(self, channel, before_message=None, limit: int = 20) -> str:
        if not channel:
            return ""

        history_messages = []
        try:
            kwargs = {"limit": limit, "oldest_first": False}
            if before_message is not None:
                kwargs["before"] = before_message
            async for msg in channel.history(**kwargs):
                clean_txt = msg.clean_content.strip() if hasattr(msg, "clean_content") else msg.content.strip()
                if not clean_txt:
                    continue

                author_name = msg.author.display_name
                history_messages.append(f"[{author_name}]: {clean_txt}")

            history_messages.reverse()

            if history_messages:
                channel_name = getattr(channel, 'name', 'chat')
                header = f"[RECENT MESSAGES IN #{channel_name} BEFORE THIS MOMENT]:"
                return header + "\n" + "\n".join(history_messages)
        except Exception as e:
            logger.warning(f"Could not fetch channel history context: {e}")

        return ""

    def _strip_bot_mention(self, text: str) -> str:
        if self.bot.user:
            for prefix in (f"@{self.bot.user.display_name}", f"@{self.bot.user.name}"):
                if text.startswith(prefix):
                    return text[len(prefix):].strip()
        return text

    @staticmethod
    async def _safe_reply(message: discord.Message, content: str):
        try:
            await message.reply(content)
        except Exception as reply_err:
            logger.warning(f"message.reply() failed, falling back to channel.send(): {reply_err}")
            try:
                await message.channel.send(content)
            except Exception as send_err:
                logger.error(
                    f"channel.send() also failed — the bot likely lacks Send Messages "
                    f"permission in this channel: {send_err}",
                    exc_info=True,
                )

    async def process_ai_response(self, message: discord.Message, text_input: str):
        signals = self.main_window.interface_signals
        current_char = self._resolve_character(message.channel.id if not isinstance(message.channel, discord.DMChannel) else None)

        if not current_char:
            logger.warning(
                "process_ai_response: no active/bound character — "
                "open a character chat in the app or use /character in this channel."
            )
            await self._safe_reply(message, "*No character is bound to this chat. Use `/character <name>` here or open a character in the app.*")
            return

        async with self.chat_lock:
            try:
                self.invalidate_config_cache()
                char_info = self._get_char_config(current_char)
                conv_method = char_info.get("conversation_method", "Local LLM")

                channel_history = await self.fetch_channel_history_context(message.channel, before_message=message, limit=20)

                raw_clean_text = message.clean_content if hasattr(message, "clean_content") else text_input
                raw_clean_text = self._strip_bot_mention(raw_clean_text)
                final_text = raw_clean_text.strip()

                discord_images, other_files = await self.process_discord_attachments(message)

                if other_files:
                    notes = ", ".join(other_files[:3])
                    final_text = (final_text + f"\n[User attached file(s): {notes}]").strip()

                if not final_text and not discord_images:
                    if message.attachments:
                        await self._safe_reply(message, UNREADABLE_ATTACHMENT_TEXT)
                    else:
                        await self._safe_reply(message, EMPTY_MESSAGE_HINT)
                    return

                if not final_text and discord_images:
                    final_text = "[Sent an image]"

                self._record_user(message.author)
                known_users_block = self.describe_known_users(exclude_user_id=str(message.author.id))

                stream_session = DiscordStreamSession(message)

                async with message.channel.typing():
                    await signals.handle_user_message(
                        character_name=current_char,
                        conversation_method=conv_method,
                        external_text=final_text,
                        discord_context=message,
                        discord_user_name=message.author.display_name,
                        discord_user_id=str(message.author.id),
                        discord_channel_history=channel_history,
                        discord_image_attachments=discord_images,
                        discord_stream=stream_session,
                        discord_known_users=known_users_block,
                    )

                answer = stream_session.final_text or getattr(signals, "_last_answer_text", "")
                if message.guild and answer.strip():
                    await self._speak_in_voice(message.guild, answer, current_char)

            except Exception as e:
                logger.error(f"Error passing message to Soul of Waifu: {e}", exc_info=True)
                await self._safe_reply(message, GENERIC_ERROR_TEXT)

    def _interaction_allowed(self, interaction: discord.Interaction) -> bool:
        user_ids = self._allowed_ids("DISCORD_ALLOWED_USER_IDS")
        if user_ids and str(interaction.user.id) not in user_ids:
            return False
        guild_ids = self._allowed_ids("DISCORD_ALLOWED_GUILD_IDS")
        if interaction.guild and guild_ids and str(interaction.guild.id) not in guild_ids:
            return False
        return True

    def _register_app_commands(self):
        @self.bot.tree.command(name="ask", description="Ask the character something")
        @app_commands.describe(text="Your message to the character")
        async def ask(interaction: discord.Interaction, text: str):
            if not self._interaction_allowed(interaction):
                await interaction.response.send_message("*You are not allowed to use this bot here.*", ephemeral=True)
                return

            char = self._resolve_character(interaction.channel_id)
            if not char:
                await interaction.response.send_message(
                    "*No character is bound to this chat. Use `/character <name>` first.*",
                    ephemeral=True,
                )
                return

            if not self._check_cooldown(interaction.user.id):
                await interaction.response.send_message("*Slow down a little.*", ephemeral=True)
                return

            await interaction.response.defer(thinking=True)

            if self._msg_queue.qsize() >= DISCORD_QUEUE_SIZE:
                await interaction.followup.send("*My queue is full right now — please try again in a minute.*")
                return

            self._ensure_worker()
            await self._msg_queue.put({
                "kind": "interaction",
                "interaction": interaction,
                "text": text,
                "channel": interaction.channel,
                "author": interaction.user,
            })

        @self.bot.tree.command(name="character", description="Bind a character to this channel")
        @app_commands.describe(name="Character name (empty = show current binding)")
        async def character(interaction: discord.Interaction, name: str = ""):
            if not self._interaction_allowed(interaction):
                await interaction.response.send_message("*You are not allowed to use this bot here.*", ephemeral=True)
                return

            name = name.strip()
            if not name:
                current = self.bindings.get().get(str(interaction.channel_id))
                names = ", ".join(sorted(self._get_all_character_names())) or "none yet"
                msg = f"Bound character: **{current}**\n" if current else "Nothing bound in this channel.\n"
                await interaction.response.send_message(f"{msg}Available characters: {names}", ephemeral=True)
                return

            if name not in self._get_all_character_names():
                available = ", ".join(sorted(self._get_all_character_names())) or "none yet"
                await interaction.response.send_message(f"No character named **{name}**. Available: {available}", ephemeral=True)
                return

            def _bind(data: dict):
                data[str(interaction.channel_id)] = name

            self.bindings.mutate(_bind)
            await interaction.response.send_message(f"**{name}** is now chatting in this channel. Use `/reset` for a fresh start.")

        @self.bot.tree.command(name="unbind", description="Remove the character binding from this channel")
        async def unbind(interaction: discord.Interaction):
            if not self._interaction_allowed(interaction):
                await interaction.response.send_message("*You are not allowed to use this bot here.*", ephemeral=True)
                return

            removed = self.bindings.get().pop(str(interaction.channel_id), None)

            def _remove(data: dict):
                data.pop(str(interaction.channel_id), None)

            self.bindings.mutate(_remove)
            if removed:
                await interaction.response.send_message(f"Unbound **{removed}** from this channel.")
            else:
                await interaction.response.send_message("Nothing was bound in this channel.", ephemeral=True)

        @self.bot.tree.command(name="reset", description="Start a fresh chat with the bound character")
        async def reset(interaction: discord.Interaction):
            if not self._interaction_allowed(interaction):
                await interaction.response.send_message("*You are not allowed to use this bot here.*", ephemeral=True)
                return

            char = self._resolve_character(interaction.channel_id)
            if not char:
                await interaction.response.send_message("*No character is bound to this chat.*", ephemeral=True)
                return

            if getattr(self.main_window.interface_signals, "_is_generating", False):
                await interaction.response.send_message("*The character is mid-sentence — try again in a moment.*", ephemeral=True)
                return

            await interaction.response.defer(thinking=True)
            try:
                new_chat_id = await self._start_fresh_chat(char)
                await interaction.followup.send(f"Started a fresh chat with **{char}** (`{new_chat_id[:8]}…`). Memory cleared!")
            except Exception as e:
                logger.error(f"/reset failed for {char}: {e}", exc_info=True)
                await interaction.followup.send(GENERIC_ERROR_TEXT)

        @self.bot.tree.command(name="whoami", description="What does the bot know about you")
        async def whoami(interaction: discord.Interaction):
            entry = self.known_users.get().get(str(interaction.user.id))
            if not entry:
                await interaction.response.send_message("We haven't properly met yet!", ephemeral=True)
                return
            await interaction.response.send_message(
                f"You are **{entry.get('display_name')}** (id `{interaction.user.id}`), "
                f"~{entry.get('message_count', 0)} messages so far.",
                ephemeral=True,
            )

        @self.bot.tree.command(name="join", description="Join your voice channel")
        async def join(interaction: discord.Interaction):
            if not self._interaction_allowed(interaction):
                await interaction.response.send_message("*You are not allowed to use this bot here.*", ephemeral=True)
                return

            voice_state = interaction.user.voice if isinstance(interaction.user, discord.Member) else None
            if not voice_state or not voice_state.channel:
                await interaction.response.send_message("*You need to be in a voice channel first.*", ephemeral=True)
                return

            try:
                vc = interaction.guild.voice_client
                if vc and vc.channel == voice_state.channel:
                    await interaction.response.send_message(f"Already in **{voice_state.channel.name}**.", ephemeral=True)
                    return
                if vc:
                    await vc.move_to(voice_state.channel)
                else:
                    await voice_state.channel.connect()
                await interaction.response.send_message(f"Joined **{voice_state.channel.name}** — replies will be spoken here.")
            except Exception as e:
                logger.error(f"Voice join failed: {e}", exc_info=True)
                await interaction.response.send_message(
                    "*Could not join voice (missing permissions, or ffmpeg not installed).*", ephemeral=True
                )

        @self.bot.tree.command(name="leave", description="Leave the voice channel")
        async def leave(interaction: discord.Interaction):
            vc = interaction.guild.voice_client if interaction.guild else None
            if vc:
                await vc.disconnect(force=True)
                await interaction.response.send_message("Left the voice channel.")
            else:
                await interaction.response.send_message("I'm not in a voice channel.", ephemeral=True)

    def _get_all_character_names(self) -> list[str]:
        try:
            all_chars = ConfigurationCharacters().load_configuration()
            return list(all_chars.get("character_list", {}).keys())
        except Exception as e:
            logger.error(f"Could not list characters: {e}")
            return []

    async def _start_fresh_chat(self, character_name: str) -> str:
        new_chat_id = str(uuid.uuid4())
        signals = self.main_window.interface_signals
        config_api = signals.configuration_characters

        config = config_api.load_configuration()
        char_data = config.get("character_list", {}).get(character_name)
        if not char_data:
            raise ValueError(f"Character '{character_name}' not found")

        first_message = char_data.get("first_message", "")
        variants = [{"variant_id": "default", "text": first_message}]
        for i, greeting in enumerate(char_data.get("alternate_greetings", []) or []):
            if isinstance(greeting, str) and greeting.strip():
                variants.append({"variant_id": f"v{i+1}", "text": greeting.strip()})

        message_id = str(uuid.uuid4())
        new_chat = {
            "name": "Discord Reset Chat",
            "created_at": datetime.datetime.now().isoformat(),
            "current_emotion": "neutral",
            "chat_history": [{"user": "", "character": first_message}],
            "chat_content": {
                message_id: {
                    "message_id": message_id,
                    "sequence_number": 1,
                    "author_name": character_name,
                    "is_user": False,
                    "current_variant_id": "default",
                    "variants": variants,
                }
            },
        }
        char_data.setdefault("chats", {})[new_chat_id] = new_chat
        char_data["current_chat"] = new_chat_id
        config_api.save_configuration_edit(config)

        if getattr(signals, "current_active_character", None) == character_name:
            try:
                await signals.open_chat(character_name)
            except Exception as e:
                logger.warning(f"Could not refresh GUI after /reset: {e}")

        return new_chat_id

    async def _run_interaction_job(self, job: dict):
        interaction: discord.Interaction = job["interaction"]
        signals = self.main_window.interface_signals
        char = self._resolve_character(interaction.channel_id)

        if not char:
            await interaction.followup.send("*No character is bound to this chat anymore.*")
            return

        async with self.chat_lock:
            try:
                self.invalidate_config_cache()
                char_info = self._get_char_config(char)
                conv_method = char_info.get("conversation_method", "Local LLM")

                channel_history = await self.fetch_channel_history_context(job.get("channel"), limit=20)
                text = self._strip_bot_mention((job.get("text") or "").strip()) or "[Sent an empty message]"

                self._record_user(job["author"])
                known_users_block = self.describe_known_users(exclude_user_id=str(job["author"].id))

                await signals.handle_user_message(
                    character_name=char,
                    conversation_method=conv_method,
                    external_text=text,
                    discord_context=None,
                    discord_user_name=job["author"].display_name,
                    discord_user_id=str(job["author"].id),
                    discord_channel_history=channel_history,
                    discord_image_attachments=None,
                    discord_stream=None,
                    discord_known_users=known_users_block,
                    discord_suppress_local_tts=True,
                )

                answer = getattr(signals, "_last_answer_text", "") or ""
                if not answer.strip():
                    await interaction.followup.send("*The character didn't produce a reply.*")
                    return

                for i, chunk in enumerate(split_message(answer)):
                    if i == 0:
                        await interaction.followup.send(chunk)
                    else:
                        await interaction.channel.send(chunk)

                await self._speak_in_voice(interaction.guild, answer, char)
            except Exception as e:
                logger.error(f"Interaction job failed: {e}", exc_info=True)
                try:
                    await interaction.followup.send(GENERIC_ERROR_TEXT)
                except Exception:
                    pass

    def _get_vc_tts_engine(self, method: str):
        engine = self._vc_tts_engines.get(method)
        if engine is not None:
            return engine

        from app.utils import text_to_speech as tts_mod

        if method == "XTTSv2":
            engine = tts_mod.XTTSv2_SOW_System()
        elif method == "Edge TTS":
            engine = tts_mod.EdgeTTS()
        elif method == "Kokoro":
            engine = tts_mod.KokoroTTS_SOW_System()
        elif method == "Silero":
            engine = tts_mod.SileroTTS_SOW_System()
        elif method == "Qwen-3 TTS":
            engine = tts_mod.Qwen3TTS_SOW_System()
        elif method == "ElevenLabs":
            engine = tts_mod.ElevenLabs()
        else:
            return None

        self._vc_tts_engines[method] = engine
        return engine

    async def _synth_voice_file(self, text: str, char: str, char_info: dict) -> str | None:
        method = char_info.get("current_text_to_speech") or "Edge TTS"
        if method in ("Nothing", "", None):
            method = "Edge TTS"

        engine = self._get_vc_tts_engine(method)
        if engine is None:
            return None

        try:
            if method == "XTTSv2":
                lang = char_info.get("language", "en")
                return await engine.generate_speech_with_xttsv2_sow_system(
                    text=text, language=lang, character_name=char
                )
            if method == "Kokoro":
                return await engine.generate_speech_with_kokoro(text, char)
            if method == "Silero":
                return await engine.generate_speech_with_silero(text, char)
            if method == "Qwen-3 TTS":
                return await engine.generate_speech_with_qwen3(text, char)
            if method == "ElevenLabs":
                voice_id = char_info.get("elevenlabs_voice_id") or ConfigurationAPI().get_token("ELEVENLABS_VOICE_ID")
                if not voice_id:
                    return None
                return await engine.generate_speech_with_elevenlabs_sow_system(text, voice_id)
            if method == "Edge TTS":
                return await engine.generate_speech_with_edge_tts_sow_system(text, char)
        except Exception as e:
            logger.warning(f"[VC] TTS engine '{method}' failed: {e}")
        return None

    async def _speak_in_voice(self, guild: discord.Guild | None, answer_text: str, character_name: str):
        if not guild:
            return
        vc = guild.voice_client
        if not vc or not vc.is_connected() or vc.is_playing():
            return

        spoken = strip_text_for_speech(answer_text)
        if not spoken:
            return

        char_info = self._get_char_config(character_name)
        audio_path = await self._synth_voice_file(spoken, character_name, char_info)

        if not audio_path or not os.path.exists(audio_path):
            try:
                from app.utils.text_to_speech import EdgeTTS
                audio_path = await EdgeTTS().generate_speech_with_edge_tts_sow_system(spoken, character_name)
            except Exception as e:
                logger.warning(f"[VC] EdgeTTS fallback failed: {e}")
        if not audio_path or not os.path.exists(audio_path):
            audio_path = await _fallback_tts(spoken)
        if not audio_path or not os.path.exists(audio_path):
            return

        def _after(err):
            try:
                os.remove(audio_path)
            except OSError:
                pass

        try:
            ffmpeg = _find_ffmpeg()
            source = discord.FFmpegPCMAudio(audio_path, executable=ffmpeg) if ffmpeg else discord.FFmpegPCMAudio(audio_path)
            vc.play(source, after=_after)
        except Exception as e:
            logger.warning(f"Voice playback failed: {e}")

    def _register_prefix_commands(self):

        def _guard(ctx: commands.Context) -> bool:
            allowed, _reason = self._is_allowed(ctx.message)
            return allowed

        @self.bot.command(name="help")
        async def help_cmd(ctx: commands.Context):
            if not _guard(ctx):
                return
            lines = [
                "**Soul of Waifu — commands**",
                "`!ask <text>` — talk to the character (no mention needed)",
                "`!character [name]` — show / set the character bound to this channel",
                "`!bind <name>` — alias of `!character <name>`",
                "`!unbind` — remove the character binding from this channel",
                "`!reset` — start a fresh chat with the bound character",
                "`!whoami` — what the bot knows about you",
                "`!join` — join your voice channel (replies are spoken there)",
                "`!leave` — leave the voice channel",
                "",
                "Without commands: mention me or DM me and the character will answer.",
            ]
            await ctx.reply("\n".join(lines))

        @self.bot.command(name="ask")
        async def ask_cmd(ctx: commands.Context, *, text: str = ""):
            if not _guard(ctx):
                return
            text = (text or "").strip()
            if not text:
                await ctx.reply("Usage: `!ask <your message>`")
                return
            if not self._check_cooldown(ctx.author.id):
                await ctx.reply("*Slow down a little — you're sending messages too fast.*")
                return
            await self._enqueue_message_job(ctx.message, text)

        @self.bot.command(name="character")
        async def character_cmd(ctx: commands.Context, *, name: str = ""):
            if not _guard(ctx):
                return
            name = name.strip()
            if not name:
                current = self.bindings.get().get(str(ctx.channel.id))
                names = ", ".join(sorted(self._get_all_character_names())) or "none yet"
                msg = f"Bound character here: **{current}**\n" if current else "Nothing bound in this channel.\n"
                await ctx.reply(f"{msg}Available characters: {names}")
                return
            if name not in self._get_all_character_names():
                available = ", ".join(sorted(self._get_all_character_names())) or "none yet"
                await ctx.reply(f"No character named **{name}**. Available: {available}")
                return

            def _do(data: dict):
                data[str(ctx.channel.id)] = name

            self.bindings.mutate(_do)
            await ctx.reply(f"**{name}** is now chatting in this channel. Use `!reset` for a fresh start.")

        @self.bot.command(name="bind")
        async def bind_cmd(ctx: commands.Context, *, name: str = ""):
            if not _guard(ctx):
                return
            if not name.strip():
                await ctx.reply("Usage: `!bind <character name>`")
                return
            await character_cmd(ctx, name=name)

        @self.bot.command(name="unbind")
        async def unbind_cmd(ctx: commands.Context):
            if not _guard(ctx):
                return
            removed = self.bindings.get().pop(str(ctx.channel.id), None)

            def _do(data: dict):
                data.pop(str(ctx.channel.id), None)

            self.bindings.mutate(_do)
            await ctx.reply(f"Unbound **{removed}**." if removed else "Nothing was bound here.")

        @self.bot.command(name="reset")
        async def reset_cmd(ctx: commands.Context):
            if not _guard(ctx):
                return
            char = self._resolve_character(ctx.channel.id if ctx.guild else None)
            if not char:
                await ctx.reply("*No character is bound to this chat — use `!character <name>` first.*")
                return
            if getattr(self.main_window.interface_signals, "_is_generating", False):
                await ctx.reply("*The character is mid-sentence — try again in a moment.*")
                return
            try:
                new_chat_id = await self._start_fresh_chat(char)
                await ctx.reply(f"Started a fresh chat with **{char}** (`{new_chat_id[:8]}…`). Memory cleared!")
            except Exception as e:
                logger.error(f"!reset failed for {char}: {e}", exc_info=True)
                await ctx.reply(GENERIC_ERROR_TEXT)

        @self.bot.command(name="whoami")
        async def whoami_cmd(ctx: commands.Context):
            if not _guard(ctx):
                return
            entry = self.known_users.get().get(str(ctx.author.id))
            if not entry:
                await ctx.reply("We haven't properly met yet!")
                return
            await ctx.reply(
                f"You are **{entry.get('display_name')}** (id `{ctx.author.id}`), "
                f"~{entry.get('message_count', 0)} messages so far."
            )

        @self.bot.command(name="join")
        async def join_cmd(ctx: commands.Context):
            if not _guard(ctx):
                return
            if ctx.guild is None:
                await ctx.reply("*Voice channels only exist in servers.*")
                return
            voice_state = ctx.author.voice if isinstance(ctx.author, discord.Member) else None
            if not voice_state or not voice_state.channel:
                await ctx.reply("*You need to be in a voice channel first.*")
                return
            try:
                vc = ctx.guild.voice_client
                if vc and vc.channel == voice_state.channel:
                    await ctx.reply(f"Already in **{voice_state.channel.name}**.")
                    return
                if vc:
                    await vc.move_to(voice_state.channel)
                else:
                    await voice_state.channel.connect()
                vc = ctx.guild.voice_client
                if vc:
                    vc.self_deaf = False

                await ctx.reply(
                    f"Joined **{voice_state.channel.name}** — "
                    f"my replies will be spoken here."
                )
            except Exception as e:
                logger.error(f"Voice join failed: {e}", exc_info=True)
                await ctx.reply("*Could not join voice (missing permissions, or ffmpeg not installed).*")

        @self.bot.command(name="leave")
        async def leave_cmd(ctx: commands.Context):
            if not _guard(ctx):
                return
            vc = ctx.guild.voice_client if ctx.guild else None
            if vc:
                await vc.disconnect(force=True)
                await ctx.reply("Left the voice channel.")
            else:
                await ctx.reply("I'm not in a voice channel.")
