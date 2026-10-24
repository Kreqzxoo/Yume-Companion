import os
import re
import secrets
import asyncio
import logging
import ipaddress
import time
import uuid
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, HTTPException, Security, Depends
from fastapi.responses import HTMLResponse, FileResponse, PlainTextResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.security import APIKeyHeader, APIKeyQuery
from faster_whisper import WhisperModel
import uvicorn

from app.utils import mobile_devices

logger = logging.getLogger("WebBridge")

_QUOTES = set('"\u201c\u201d\u201e\u00ab\u00bb')          # " " " „ « »  - every one toggles "inside a quotation"


class SpeechFilter:
    """Keeps only the spoken words (inside quotation marks) of a streamed reply - no *actions*, feelings or descriptions.
    Works chunk by chunk. A reply without any quotation marks is pure narration and produces nothing."""

    def __init__(self):
        self.reset()

    def reset(self):
        self.inside = False
        self.emitted = False
        self.raw = ""

    def feed(self, chunk: str) -> str:
        self.raw += chunk
        out = []
        for ch in chunk:
            if ch in _QUOTES:
                self.inside = not self.inside
                if not self.inside and out and not out[-1].isspace():
                    out.append(" ")                      # separate two spoken parts
            elif self.inside:
                out.append(ch)
        text = "".join(out)
        if text.strip():
            self.emitted = True
        return text

    def finish(self) -> str:
        return ""


def strip_actions(text: str) -> str:
    text = re.sub(r"\*[^*]*\*", " ", text)
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"\[[^\]]*\]", " ", text)
    return re.sub(r"[ \t]{2,}", " ", text).strip()


def speech_only(text: str, plain: bool = False) -> str:
    """Only the quoted words of a finished message. Without any quotation marks: the text itself when the model is in plain-text
    mode (it then writes only speech), otherwise nothing (narration)."""
    f = SpeechFilter()
    out = f.feed(text) or ""
    if f.emitted:
        return re.sub(r"[ \t]{2,}", " ", out).strip()
    return text.strip() if plain else ""


class ConnectionManager:
    def __init__(self):
        self.active_connections: list[WebSocket] = []
        self.meta: dict = {}

    async def connect(self, websocket: WebSocket, info: dict | None = None):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.meta[websocket] = info or {"role": "web"}

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        self.meta.pop(websocket, None)

    async def broadcast_by_role(self, make_message):
        """make_message(role) -> dict or None (skip). Lets phones receive something different from browsers."""
        disconnected = []
        for connection in list(self.active_connections):
            role = (self.meta.get(connection) or {}).get("role", "web")
            message = make_message(role)
            if message is None:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket Broadcast Error: {e}")
                disconnected.append(connection)
        for connection in disconnected:
            self.disconnect(connection)

    async def broadcast(self, message: dict, exclude: WebSocket = None):
        disconnected = []
        for connection in self.active_connections:
            if connection == exclude:
                continue
            try:
                await connection.send_json(message)
            except Exception as e:
                logger.error(f"WebSocket Broadcast Error: {e}")
                disconnected.append(connection)
                
        for connection in disconnected:
            self.disconnect(connection)

class WebBridge:
    def __init__(self, interface_signals, auth_token: str = None):
        self.app = FastAPI(docs_url=None, redoc_url=None)
        self.signals = interface_signals
        self.manager = ConnectionManager()
        
        self.auth_token = auth_token or secrets.token_urlsafe(16)
        self.phone_pending: dict = {}
        self._speech = SpeechFilter()
        self._pair_failures: list = []
        mobile_devices.BRIDGE = self
        
        self.app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.project_dir = os.path.dirname(self.app_dir)
        
        self.setup_middleware()
        self.setup_routes()
        self.hook_interface_signals()

    def hook_interface_signals(self):
        self.signals.web_bridge = self

    def setup_middleware(self):
        @self.app.middleware("http")
        async def validate_host_header(request: Request, call_next):
            raw_host = (request.headers.get("host") or "").strip().lower()
            # Handle bracketed IPv6 and an optional port without trusting arbitrary hostnames.
            if raw_host.startswith("[") and "]" in raw_host:
                host_header = raw_host[1:raw_host.index("]")]
            else:
                host_header = raw_host.rsplit(":", 1)[0] if raw_host.count(":") == 1 else raw_host
            allowed_hosts = {"localhost", "127.0.0.1", "::1", ""}
            try:
                remote_url = self.signals.configuration_settings.get_main_setting("android_remote_url") or ""
                from urllib.parse import urlparse
                configured_host = (urlparse(remote_url).hostname or "").lower()
                if configured_host:
                    allowed_hosts.add(configured_host)
            except Exception:
                pass
            if host_header in allowed_hosts:
                return await call_next(request)
            try:
                ipaddress.ip_address(host_header)
            except ValueError:
                return PlainTextResponse("Forbidden: Hostname is not configured in Settings > Android Connector", status_code=400)
            return await call_next(request)

        @self.app.middleware("http")
        async def check_auth_token(request: Request, call_next):
            path = request.url.path
            if path in ["/", "/favicon.ico", "/api/ping", "/api/pair"] or path.startswith("/static") or path.startswith("/vrm") or path.startswith("/assets"):
                return await call_next(request)

            bearer = (request.headers.get("Authorization") or "")
            bearer = bearer[7:].strip() if bearer.lower().startswith("bearer ") else ""
            candidates = [request.headers.get("X-Yume-Token"), request.headers.get("X-SOW-Token"), bearer, request.query_params.get("token")]
            for token in candidates:
                if not token:
                    continue
                if secrets.compare_digest(token, self.auth_token):
                    return await call_next(request)
                device = mobile_devices.get_registry().verify(token)
                if device is not None:
                    request.state.device = device
                    return await call_next(request)

            return PlainTextResponse("Unauthorized: Invalid Token", status_code=401)

    def setup_routes(self):
        web_client_dir = os.path.join(self.app_dir, "web_client")
        vrm_dir = os.path.join(self.app_dir, "utils", "emotions", "vrm")
        
        if not os.path.exists(web_client_dir):
            os.makedirs(web_client_dir, exist_ok=True)
            
        self.app.mount("/static", StaticFiles(directory=web_client_dir), name="static")
        self.app.mount("/assets", StaticFiles(directory=os.path.join(self.project_dir, "assets")), name="assets")
        
        if os.path.exists(vrm_dir):
            self.app.mount("/vrm", StaticFiles(directory=vrm_dir), name="vrm")

        @self.app.get("/", response_class=HTMLResponse)
        async def index():
            index_path = os.path.join(web_client_dir, "index.html")
            if os.path.exists(index_path):
                try:
                    from app.utils.branding import app_name
                    name = app_name()
                    if name != "Soul of Waifu":
                        with open(index_path, "r", encoding="utf-8") as fh:
                            return HTMLResponse(fh.read().replace("Soul of Waifu", name))
                except Exception:
                    pass
                return FileResponse(index_path)
            return HTMLResponse("<h1>Web Client Not Found</h1>")

        @self.app.get("/api/ping")
        async def ping(request: Request):
            """Open endpoint: lets the phone find out whether this is the right host (local vs. external address)."""
            mobile_devices.LAST_CONTACT.update(ip=request.client.host if request.client else "?", t=time.time(), what="ping")
            from app.utils.branding import app_name
            return {"app": app_name(), "host_id": mobile_devices.host_id(self.signals.configuration_settings),
                    "name": mobile_devices.host_name(), "api": "yume-mobile-v1", "t": time.time()}

        @self.app.post("/api/pair")
        async def pair(request: Request):
            now = time.time()
            mobile_devices.LAST_CONTACT.update(ip=request.client.host if request.client else "?", t=now, what="pair")
            self._pair_failures = [x for x in self._pair_failures if now - x < 300]
            if len(self._pair_failures) >= 10:
                return JSONResponse({"status": "error", "message": "too many attempts"}, status_code=429)
            data = await request.json()
            registry = mobile_devices.get_registry()
            if not registry.consume_code(str(data.get("code", ""))):
                self._pair_failures.append(now)
                return JSONResponse({"status": "error", "message": "invalid or expired code"}, status_code=403)
            token, device = registry.add_device(str(data.get("device_name", "Android")), str(data.get("device_id", "")) or None)
            settings = self.signals.configuration_settings
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            logger.info("Android device paired: %s", device.get("name"))
            return {
                "status": "ok", "token": token, "device": device,
                "host_id": mobile_devices.host_id(settings), "host_name": mobile_devices.host_name(),
                "local_url": settings.get_main_setting("android_local_url") or "",
                "remote_url": settings.get_main_setting("android_remote_url") or "",
                "macs": mobile_devices.mac_addresses(),
                "characters": list(config.get("character_list", {}).keys()),
                "active_character": self.signals.current_active_character or "",
            }

        @self.app.get("/api/mobile/devices")
        async def list_devices():
            return {"devices": mobile_devices.get_registry().list_devices()}

        @self.app.delete("/api/mobile/devices/{device_id}")
        async def delete_device(device_id: str):
            return {"status": "ok" if mobile_devices.get_registry().revoke(device_id) else "error"}

        @self.app.post("/api/vision/describe")
        async def vision_describe(request: Request):
            """Phone screenshots / camera photos: describe them with the vision model of this PC."""
            form = await request.form()
            image = form.get("image")
            prompt = form.get("prompt") or None
            if image is None:
                return JSONResponse({"status": "error", "message": "image missing"}, status_code=400)
            from app.utils import vision_manager as vm
            if not vm.is_ready():
                return JSONResponse({"status": "error", "message": "vision not ready"}, status_code=503)
            raw = await image.read()
            try:
                text = await asyncio.to_thread(vm.describe_bytes, raw, prompt, False)
            except Exception as exc:
                return JSONResponse({"status": "error", "message": str(exc)}, status_code=500)
            return {"status": "ok", "text": text}

        @self.app.get("/api/sync/{char_name}")
        async def sync_character(char_name: str, limit: int = 30):
            """Everything the phone needs to keep talking as this character without the PC (offline emergency mode)."""
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            info = config.get("character_list", {}).get(char_name)
            if info is None:
                return JSONResponse({"status": "error", "message": "unknown character"}, status_code=404)
            user_name = self.signals.configuration_settings.get_user_data("user_name") or "User"
            current_chat = info.get("current_chat", "default")
            content = info.get("chats", {}).get(current_chat, {}).get("chat_content", {})
            history = []
            for _mid, msg in sorted(content.items(), key=lambda x: x[1].get("sequence_number", 0)):
                vid = msg.get("current_variant_id", "default")
                text = next((v["text"] for v in msg.get("variants", []) if v.get("variant_id") == vid), "")
                history.append({"role": "user" if msg.get("is_user", True) else "assistant",
                                "text": text.replace("{{user}}", user_name).replace("{{char}}", char_name)})
            language = info.get("character_language", "auto")
            return {
                "status": "ok", "name": char_name, "user_name": user_name, "language": language,
                "description": info.get("character_description", ""), "personality": info.get("character_personality", ""),
                "scenario": info.get("scenario", ""), "first_message": info.get("first_message", ""),
                "example_messages": info.get("example_messages", ""),
                "character_information": info.get("character_information", ""),
                "history": history[-max(1, min(limit, 100)):],
            }

        @self.app.get("/api/mobile/bootstrap")
        async def mobile_bootstrap():
            """Authenticated bootstrap endpoint consumed by the Android connector."""
            settings = self.signals.configuration_settings
            return {
                "app": "Soul of Waifu",
                "active_character": self.signals.current_active_character or "None",
                "local_url": settings.get_main_setting("android_local_url") or "",
                "wifi_ssid": settings.get_main_setting("android_wifi_ssid") or "",
                "remote_url": settings.get_main_setting("android_remote_url") or "",
                "web_port": int(settings.get_main_setting("web_server_port") or 8000),
                "features": {"chat": True, "vrm": True, "live2d": True, "voice_stt": True, "websocket": True,
                             "pairing": True, "phone_control": True, "vision": True, "sync": True},
                "host_id": mobile_devices.host_id(settings),
                "macs": mobile_devices.mac_addresses(),
            }

        @self.app.get("/api/mobile/health")
        async def mobile_health():
            return {"status": "ok", "app": "Soul of Waifu", "api": "mobile-v1"}

        @self.app.get("/api/config")
        async def get_config():
            char_name = self.signals.current_active_character or "None"
            return {
                "active_character": char_name,
                "user_name": "User"
            }

        @self.app.get("/api/avatar_config/{char_name}")
        async def get_avatar_config(char_name: str):
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            char_info = config["character_list"].get(char_name, {})
            
            mode = char_info.get("current_sow_system_mode", "Nothing")
            img_folder = char_info.get("expression_images_folder", "")
            l2d_folder = char_info.get("live2d_model_folder", "")
            vrm_file = char_info.get("vrm_model_file", "")
            
            # a model entry that points to a folder (or a missing file) cannot be shown: report "Nothing" instead of a broken model
            if mode == "VRM" and not (vrm_file and os.path.isfile(vrm_file)):
                mode, vrm_file = "Nothing", ""
            if mode == "Live2D Model":
                has_model = False
                try:
                    has_model = bool(l2d_folder) and os.path.isdir(l2d_folder) and any(f.endswith((".model3.json", ".model.json")) for f in os.listdir(l2d_folder))
                except OSError:
                    pass
                if not has_model:
                    mode, l2d_folder = "Nothing", ""
            if img_folder: img_folder = "/" + os.path.relpath(img_folder, self.project_dir).replace("\\", "/")
            if l2d_folder:
                for file in os.listdir(l2d_folder):
                    if file.endswith(".model3.json") or file.endswith(".model.json"):
                        l2d_folder = "/" + os.path.relpath(os.path.join(l2d_folder, file), self.project_dir).replace("\\", "/")
                        break
            if vrm_file: vrm_file = "/" + os.path.relpath(vrm_file, self.project_dir).replace("\\", "/")

            return {
                "mode": mode,
                "expression_images_folder": img_folder,
                "live2d_model_file": l2d_folder,
                "vrm_model_file": vrm_file
            }

        def _vrm_dir() -> str:
            return os.path.join(self.project_dir, "assets", "emotions", "vrm")

        @self.app.get("/api/avatar/models")
        async def avatar_models(character: str = ""):
            """VRM models the phone can download and animate by itself (3D avatar in the Android app)."""
            vrm_dir = _vrm_dir()
            models = []
            if os.path.isdir(vrm_dir):
                for f in sorted(os.listdir(vrm_dir)):
                    path = os.path.join(vrm_dir, f)
                    if f.lower().endswith(".vrm") and os.path.isfile(path):
                        models.append({"name": f, "size": os.path.getsize(path)})
            current = ""
            if character:
                config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
                chosen = os.path.basename(str(config.get("character_list", {}).get(character, {}).get("vrm_model_file") or ""))
                if any(m["name"] == chosen for m in models):
                    current = chosen
            return {"models": models, "current": current}

        @self.app.get("/api/avatar/model")
        async def avatar_model(name: str):
            safe = os.path.basename(name)
            path = os.path.join(_vrm_dir(), safe)
            if not safe.lower().endswith(".vrm") or not os.path.isfile(path):
                return JSONResponse({"status": "error", "message": "unknown model"}, status_code=404)
            return FileResponse(path, media_type="application/octet-stream", filename=safe)

        @self.app.get("/api/spotify/credentials")
        async def spotify_credentials():
            """Client ID + login of the PC's Spotify connection: the phone takes them over, so both use the same account."""
            from app.utils import spotify_pc
            return spotify_pc.credentials()

        @self.app.post("/api/spotify/credentials")
        async def spotify_adopt(request: Request):
            """The phone was logged in first: the PC takes over (only if it has no login yet)."""
            from app.utils import spotify_pc
            body = await request.json()
            return {"adopted": spotify_pc.adopt(str(body.get("client_id", "")), str(body.get("refresh_token", "")))}

        @self.app.get("/api/spotify/now")
        async def spotify_now():
            from app.utils import spotify_pc
            return await asyncio.to_thread(spotify_pc.now_playing)

        @self.app.post("/api/spotify/control")
        async def spotify_control(request: Request):
            from app.utils import spotify_pc
            body = await request.json()
            ok, message = await asyncio.to_thread(spotify_pc.control, str(body.get("action", "")), body.get("value"))
            return {"ok": ok, "message": message}

        @self.app.post("/api/inbox")
        async def inbox_upload(request: Request, name: str = "datei", mime: str = ""):
            """'Share -> Yume' on the phone: the raw file in the body (voice note, picture, PDF ...)."""
            from app.utils import inbox
            clean = inbox.safe_name(name, mime)
            path = inbox.target_path(clean)
            size = 0
            try:
                with open(path, "wb") as fh:
                    async for chunk in request.stream():
                        size += len(chunk)
                        if size > inbox.MAX_BYTES:
                            raise ValueError("too large")
                        fh.write(chunk)
            except Exception as exc:
                try:
                    path.unlink()
                except OSError:
                    pass
                return JSONResponse({"ok": False, "message": str(exc)[:120]}, status_code=400 if "large" not in str(exc) else 413)
            if size == 0:
                path.unlink()
                return JSONResponse({"ok": False, "message": "empty"}, status_code=400)
            device = getattr(request.state, "device", None)
            item = inbox.register(path, mime, (device or {}).get("name", "phone"))
            await self.manager.broadcast({"type": "inbox_item", "id": item["id"], "name": item["name"], "kind": item["kind"]})
            return {"ok": True, "id": item["id"], "kind": item["kind"]}

        @self.app.post("/api/inbox/text")
        async def inbox_text(request: Request):
            from app.utils import inbox
            body = await request.json()
            device = getattr(request.state, "device", None)
            item = inbox.save_text(str(body.get("text", "")), str(body.get("title", "")), (device or {}).get("name", "phone"))
            await self.manager.broadcast({"type": "inbox_item", "id": item["id"], "name": item["name"], "kind": item["kind"]})
            return {"ok": True, "id": item["id"], "kind": "text"}

        @self.app.post("/api/translate")
        async def translate_api(request: Request):
            """Interpreter mode of the phone: text -> translation (the character's own language model, no chat history)."""
            from app.utils.ai_clients.ai_factory import AIFactory
            body = await request.json()
            text = str(body.get("text", "")).strip()[:2000]
            target = str(body.get("target", "English")).strip()[:40] or "English"
            if not text:
                return {"ok": False, "message": "empty"}
            char = str(body.get("character", "")) or str(getattr(self.signals, "current_active_character", "") or "")
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            method = config.get("character_list", {}).get(char, {}).get("conversation_method", "Local LLM")
            try:
                provider = AIFactory.get_provider(method)
                result = await provider.generate([
                    {"role": "system", "content": f"You are a professional interpreter. Translate the user's text into {target}. Output ONLY the translation: no quotes, no notes, no explanations. "
                                                  "Keep names, numbers and the tone. If the text is already in that language, repeat it unchanged."},
                    {"role": "user", "content": text}], temperature=0.2, max_tokens=500)
                out = str((result or {}).get("content") or "").strip().strip('"')
            except Exception as exc:
                logger.warning("Translation failed: %s", exc)
                return JSONResponse({"ok": False, "message": str(exc)[:120]}, status_code=500)
            return {"ok": bool(out), "text": out}

        @self.app.post("/api/transcribe")
        async def transcribe_api(request: Request):
            """Speech to text only (no chat answer): the audio of the interpreter mode."""
            form = await request.form()
            audio = form.get("audio")
            if audio is None:
                return {"ok": False, "message": "missing audio"}
            data = await audio.read()
            language = (form.get("language") or "").strip().lower() or None
            path = os.path.join(self.app_dir, "cache", f"web_tr_{os.getpid()}_{uuid.uuid4().hex[:6]}{'.wav' if data[:4] == b'RIFF' else '.webm'}")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as fh:
                fh.write(data)
            try:
                text = await asyncio.to_thread(self.transcribe_file, path, language)
            finally:
                try:
                    os.remove(path)
                except OSError:
                    pass
            return {"ok": True, "text": text}

        @self.app.get("/api/kiosk")
        async def kiosk_endpoint():
            """Data for the wall / tablet display of the phone app."""
            from app.utils import kiosk
            return await asyncio.to_thread(kiosk.collect, self.signals)

        @self.app.get("/api/characters")
        async def get_characters():
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            chars = list(config.get("character_list", {}).keys())
            return {"characters": chars}

        @self.app.post("/api/character/switch")
        async def switch_character(request: Request):
            data = await request.json()
            char_name = data.get("character")
            if char_name:
                if str(getattr(self.signals, "current_active_character", "")) != str(char_name):
                    asyncio.create_task(self._open_chat_quietly(char_name))
                await self.manager.broadcast({
                    "type": "character_changed",
                    "character": char_name
                })
                return {"status": "ok"}
            return {"status": "error"}

        @self.app.get("/api/background")
        async def get_background():
            bg_path = await asyncio.to_thread(self.signals.configuration_settings.get_main_setting, "chat_background_image")
            if bg_path and bg_path != "None" and os.path.exists(bg_path):
                return FileResponse(bg_path)
            return HTMLResponse("No background", status_code=404)

        @self.app.get("/api/history/{char_name}")
        async def get_history(request: Request, char_name: str, offset: int = 0, limit: int = 50):
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            char_info = config["character_list"].get(char_name, {})
            current_chat = char_info.get("current_chat", "default")
            chat_content = char_info.get("chats", {}).get(current_chat, {}).get("chat_content", {})
            
            user_name = self.signals.configuration_settings.get_user_data("user_name") or "User"
            
            messages = []
            for msg_id, msg_data in sorted(chat_content.items(), key=lambda x: x[1].get("sequence_number", 0)):
                current_variant_id = msg_data.get("current_variant_id", "default")
                variant = next((v for v in msg_data.get("variants", []) if v["variant_id"] == current_variant_id), {})
                text = variant.get("text", "")
                created = str(variant.get("created_at", "") or "")
                
                processed_text = (text.replace("{{user}}", user_name)
                                      .replace("{{char}}", char_name)
                                      .replace("{{User}}", user_name)
                                      .replace("{{Char}}", char_name)
                                      .replace("<USER>", user_name)
                                      .replace("<CHAR>", char_name))
                
                if (not msg_data.get("is_user", True)) and getattr(request.state, "device", None) is not None and self._speech_only_enabled():
                    processed_text = speech_only(processed_text, plain=self._plain_text_mode())
                    if not processed_text:
                        continue
                messages.append({
                    "id": msg_id,
                    "is_user": msg_data.get("is_user", True),
                    "text": processed_text,
                    "time": created,
                })
            
            if messages:
                total = len(messages)
                start_idx = max(0, total - offset - limit)
                end_idx = total - offset
                history_slice = messages[start_idx:end_idx]
            else:
                history_slice = []
                
            return {"history": history_slice}

        @self.app.delete("/api/messages/{message_id}")
        async def delete_message_api(message_id: str, request: Request):
            data = await request.json()
            char_name = data.get("character")
            
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            char_info = config["character_list"].get(char_name, {})
            conv_method = char_info.get("conversation_method", "Local LLM")
            
            asyncio.create_task(self.signals.delete_message(char_name, conv_method, message_id))
            
            await self.manager.broadcast({"type": "message_deleted", "id": message_id})
            return {"status": "ok"}

        @self.app.patch("/api/messages/{message_id}")
        async def edit_message_api(message_id: str, request: Request):
            data = await request.json()
            char_name = data.get("character")
            new_text = data.get("text")
            
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            char_info = config.get("character_list", {}).get(char_name, {})
            current_chat = char_info.get("current_chat", "default")
            chats = char_info.get("chats", {})
            
            updated_on_disk = False
            if current_chat in chats:
                chat_content = chats[current_chat].get("chat_content", {})
                if message_id in chat_content:
                    msg_data = chat_content[message_id]
                    current_variant_id = msg_data.get("current_variant_id", "default")
                    
                    for variant in msg_data.get("variants", []):
                        if variant["variant_id"] == current_variant_id:
                            variant["text"] = new_text
                            updated_on_disk = True
                            break
            
            if updated_on_disk:
                await asyncio.to_thread(self.signals.configuration_characters.save_configuration, config)
                
                if message_id in self.signals.messages:
                    processed_text = self.signals.markdown_to_html(new_text)
                    user_name = self.signals.configuration_settings.get_user_data("user_name") or "User"
                    processed_text = (processed_text.replace("{{user}}", user_name)
                                .replace("{{char}}", char_name)
                                .replace("{{User}}", user_name)
                                .replace("{{Char}}", char_name))
                    
                    self.signals.messages[message_id]["label"].setText(processed_text)
                    self.signals.messages[message_id]["text"] = new_text
                
                await self.manager.broadcast({"type": "message_edited", "id": message_id, "text": new_text})
                return {"status": "ok"}
                
            return {"status": "error", "message": "Message not found in database"}

        @self.app.post("/api/messages/{message_id}/regenerate")
        async def regenerate_message_api(message_id: str, request: Request):
            data = await request.json()
            char_name = data.get("character")
            
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            char_info = config["character_list"].get(char_name, {})
            conv_method = char_info.get("conversation_method", "Local LLM")
            
            asyncio.create_task(self.signals.regenerate_message(conv_method, char_name, message_id))
            return {"status": "ok"}

        @self.app.post("/api/messages/{message_id}/variant")
        async def switch_variant_api(message_id: str, request: Request):
            data = await request.json()
            char_name = data.get("character")
            direction = data.get("direction", 1)
            try:
                direction = int(direction)
            except Exception:
                direction = 1
            if direction not in (-1, 1):
                direction = 1 if direction > 0 else -1
            result = self.signals.switch_message_variant(char_name, message_id, direction)
            if not result:
                return JSONResponse({"status": "error", "message": "No variants"}, status_code=400)
            await self.manager.broadcast({
                "type": "message_variant_changed",
                "id": message_id,
                "text": result["text"],
                "current": result["current"] + 1,
                "total": result["total"]
            })
            return {"status": "ok", "current": result["current"] + 1, "total": result["total"], "text": result["text"]}

        @self.app.get("/api/wake_phrase")
        async def wake_phrase(character: str, text: str, hq: int = 1, verify: int = 1):
            """The phone's answer to its wake word ("Ja, ich höre?"), spoken in the character's own voice (TTS + RVC from the settings here)."""
            text = (text or "").strip()[:200]
            if not text or not character:
                return JSONResponse({"status": "error", "message": "text or character missing"}, status_code=400)
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            info = config.get("character_list", {}).get(character)
            if info is None or info.get("current_text_to_speech") in (None, "Nothing"):
                return JSONResponse({"status": "error", "message": "this character has no voice"}, status_code=404)
            self.signals.ensure_chat_tts(character)
            worker = getattr(self.signals, "chat_tts_worker", None)
            if worker is None or getattr(worker, "character_name", None) != character:
                return JSONResponse({"status": "error", "message": "voice not available"}, status_code=503)
            lang_name = str(info.get("qwen_language") or "")
            lang_code = {"german": "de", "english": "en", "russian": "ru", "french": "fr", "spanish": "es", "italian": "it",
                         "portuguese": "pt", "japanese": "ja", "korean": "ko", "chinese": "zh"}.get(lang_name.lower())
            best, best_score, best_heard = None, -1.0, ""
            attempts = 3 if verify else 1
            for _ in range(attempts):
                try:
                    data = await asyncio.to_thread(worker.render_to_bytes, text, 300, bool(hq))
                except Exception as exc:
                    logger.warning("Wake phrase could not be synthesized: %s", exc)
                    if best is not None:
                        break
                    return JSONResponse({"status": "error", "message": str(exc)[:160]}, status_code=500)
                if not verify:
                    best, best_score = data, 1.0
                    break
                score, heard = await asyncio.to_thread(self._similarity_to_text, data, text, lang_code)
                if score > best_score:
                    best, best_score, best_heard = data, score, heard
                if score >= 0.85:                       # speech recognition hears the sentence as intended: a good take
                    break
            return Response(content=best, media_type="audio/wav",
                            headers={"X-Yume-Score": str(int(best_score * 100)), "X-Yume-Heard": best_heard.encode("ascii", "ignore").decode()[:80]})

        @self.app.post("/api/generation/stop")
        async def stop_generation_api():
            self.signals.stop_generation()
            return {"status": "ok"}

        @self.app.post("/api/voice/stt")
        async def stt_api(request: Request):
            form = await request.form()
            audio_file = form.get("audio")
            char_name = form.get("character")
            
            if not audio_file or not char_name:
                return {"status": "error", "message": "Missing audio or character"}

            audio_bytes = await audio_file.read()
            try:
                if self.signals.configuration_settings.get_main_setting("voice_mood"):
                    from app.utils import voice_mood, mood as _vm
                    label = await asyncio.to_thread(lambda: voice_mood.observe(voice_mood.pcm_from_wav(audio_bytes)))
                    if label:
                        _vm.from_voice(label)
            except Exception:
                logger.debug("voice mood failed", exc_info=True)
            if str(form.get("mode") or "") == "quiet":
                from app.utils import mood as _mood
                _mood.force("late")
            video_frame = form.get("image")                  # video call: the camera picture belonging to this sentence
            video_bytes = await video_frame.read() if video_frame is not None and hasattr(video_frame, "read") else None
            language = (form.get("language") or "").strip().lower() or None
            suffix = ".wav" if audio_bytes[:4] == b"RIFF" else ".webm"
            temp_path = os.path.join(self.app_dir, "cache", f"web_stt_{os.getpid()}_{uuid.uuid4().hex[:6]}{suffix}")
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
            
            with open(temp_path, "wb") as f:
                f.write(audio_bytes)
                
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            char_info = config["character_list"].get(char_name, {})
            conv_method = char_info.get("conversation_method", "Local LLM")

            def _transcribe():
                if not hasattr(self, "_whisper_model"):
                    settings = self.signals.configuration_settings
                    device = str(settings.get_main_setting("whisper_device") or "cpu").lower()
                    model = None
                    if device == "cuda":
                        try:
                            index = int(settings.get_main_setting("whisper_gpu_index") or 0)
                            model = WhisperModel("small", device="cuda", device_index=index, compute_type="float16")
                        except Exception:
                            logger.warning("Whisper on CUDA failed for the phone speech input; using the CPU", exc_info=True)
                    self._whisper_model = model or WhisperModel("small", device="cpu", compute_type="int8")

                started = time.time()
                use_language = language
                if use_language is None:
                    configured = str(self.signals.configuration_settings.get_main_setting("stt_language") or "auto").strip().lower()
                    use_language = None if configured in ("", "auto") else configured
                segments, info = self._whisper_model.transcribe(temp_path, beam_size=5, language=use_language)
                full_text = "".join([segment.text for segment in segments]).strip()
                try:                                                # the dashboard shows the speech input of the phone, too
                    from app.utils.runtime_stats import stats as _stats
                    _stats.record_stt(float(getattr(info, "duration", 0.0) or 0.0), time.time() - started, len(full_text))
                except Exception:
                    pass
                return full_text

            try:
                text = await asyncio.to_thread(_transcribe)
                os.remove(temp_path)
            except Exception as e:
                logger.error(f"Web STT Error: {e}")
                return {"status": "error", "message": str(e)}

            if text and len(text) > 2:
                message = text
                if video_bytes:
                    try:
                        from app.utils import vision_manager as vm
                        if vm.is_ready():
                            german = int(self.signals.configuration_settings.get_main_setting("program_language") or 0) == 2
                            prompt = ("Beschreibe in 2-3 kurzen Sätzen, was die Kamera gerade zeigt: die Person (Ausdruck, Tätigkeit), Gegenstände und Umgebung."
                                      if german else
                                      "Describe in 2-3 short sentences what the camera shows right now: the person (expression, activity), objects and surroundings.")
                            seen = await asyncio.to_thread(vm.describe_bytes, video_bytes, prompt, False)
                            if seen:
                                message = f"{text} [Videoanruf - das siehst du gerade durch die Kamera des Nutzers: {str(seen).strip()}]"
                    except Exception:
                        logger.warning("Video call: the camera picture could not be described", exc_info=True)

                if str(getattr(self.signals, "current_active_character", "")) != str(char_name):
                    await self._open_chat_quietly(char_name)

                await self.manager.broadcast({
                    "type": "user_message",
                    "text": text
                })

                self.pending_phone_turn = True
                try:
                    from app.utils import voice_guard
                    voice_guard.set_speaker(str(form.get("speaker") or ""))
                except Exception:
                    logger.debug("voice guard failed", exc_info=True)
                asyncio.create_task(
                    self.signals.handle_user_message(char_name, conv_method, external_text=message)
                )
                
            return {"status": "ok", "text": text}

        @self.app.get("/api/avatar/{char_name}")
        async def get_avatar(char_name: str):
            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
            char_info = config["character_list"].get(char_name, {})
            path = char_info.get("character_avatar")
            if path and os.path.exists(path):
                return FileResponse(path)
            
            fallback_path = os.path.join(self.app_dir, "gui", "icons", "logotype.png")
            if os.path.exists(fallback_path):
                return FileResponse(fallback_path)
            return HTMLResponse("Avatar not found", status_code=404)

        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            token = websocket.query_params.get("token") or ""
            device = None
            if not (token and secrets.compare_digest(token, self.auth_token)):
                device = mobile_devices.get_registry().verify(token)
                if device is None:
                    await websocket.close(code=1008)
                    return
            role = websocket.query_params.get("role", "web")
            info = {"role": role, "device_id": device["id"] if device else None,
                    "name": device["name"] if device else "web", "caps": [], "call": False,
                    "ip": websocket.client.host if websocket.client else ""}
            await self.manager.connect(websocket, info)
            if role == "phone":
                self._phone_changed()
            try:
                while True:
                    data = await websocket.receive_json()
                    kind = data.get("type")
                    if kind == "user_input":
                        char_name = data.get("character")
                        text = data.get("text")
                        if data.get("mode") == "quiet":
                            from app.utils import mood as _mood
                            _mood.force("late")

                        if text and char_name:
                            if str(getattr(self.signals, "current_active_character", "")) != str(char_name):
                                await self._open_chat_quietly(char_name)       # the chat has to exist on the PC before it can answer

                            config = await asyncio.to_thread(self.signals.configuration_characters.load_configuration)
                            char_info = config["character_list"].get(char_name, {})
                            conv_method = char_info.get("conversation_method", "Local LLM")

                            await self.manager.broadcast({
                                "type": "user_message",
                                "text": text
                            }, exclude=websocket)

                            self.pending_phone_turn = True       # this answer is for the phone: the PC stays silent
                            self.pending_text_only = bool(data.get("text_only"))     # plain chat on the phone: no voice is made at all
                            asyncio.create_task(
                                self.signals.handle_user_message(char_name, conv_method, external_text=text)
                            )
                    elif kind == "hello":
                        info["caps"] = list(data.get("caps", []))[:64]
                        info["battery"] = data.get("battery")
                        info["model"] = str(data.get("model", ""))[:60]
                    elif kind == "device_result":
                        future = self.phone_pending.pop(str(data.get("id", "")), None)
                        if future is not None and not future.done():
                            future.set_result(data)
                    elif kind == "call_start":
                        info["call"] = True
                        self._update_call_audio()
                    elif kind == "call_end":
                        info["call"] = False
                        self._update_call_audio()
                        try:
                            self.signals.stop_generation()          # hung up: no more thinking, no more speech
                        except Exception:
                            logger.debug("stop after hang-up failed", exc_info=True)
                    elif kind == "ping":
                        await websocket.send_json({"type": "pong", "t": data.get("t")})

            except WebSocketDisconnect:
                pass
            except Exception as e:
                logger.error(f"WebSocket Error: {e}")
            finally:
                self.manager.disconnect(websocket)
                info["call"] = False
                self._update_call_audio()
                if role == "phone":
                    self._phone_changed()

    # ------------------------------------------------------------------ phone channel
    def has_phone(self) -> bool:
        return any(m.get("role") == "phone" for m in self.manager.meta.values())

    def drop_device_sockets(self, device_id: str):
        for ws, meta in list(self.manager.meta.items()):
            if meta.get("device_id") == device_id:
                asyncio.ensure_future(ws.close(code=1008))

    def _phone_changed(self):
        """A phone came or went: the chat tool list (phone tools) changes with it."""
        try:
            refresh = getattr(self.signals, "refresh_tool_registry", None)
            if callable(refresh):
                refresh()
        except Exception:
            logger.debug("tool registry refresh failed", exc_info=True)

    def _whisper(self):
        if not hasattr(self, "_whisper_model"):
            settings = self.signals.configuration_settings
            device = str(settings.get_main_setting("whisper_device") or "cpu").lower()
            model = None
            if device == "cuda":
                try:
                    index = int(settings.get_main_setting("whisper_gpu_index") or 0)
                    model = WhisperModel("small", device="cuda", device_index=index, compute_type="float16")
                except Exception:
                    logger.warning("Whisper on CUDA failed; using the CPU", exc_info=True)
            self._whisper_model = model or WhisperModel("small", device="cpu", compute_type="int8")
        return self._whisper_model

    def _similarity_to_text(self, wav_bytes: bytes, target: str, language):
        """How well speech recognition understands the generated audio as [target] (0..1) - a take that adds, drops or garbles words scores low."""
        import difflib
        path = os.path.join(self.app_dir, "cache", f"verify_{uuid.uuid4().hex[:8]}.wav")
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(wav_bytes)
            segments, _info = self._whisper().transcribe(path, beam_size=5, language=language)
            heard = " ".join(s.text for s in segments).strip()
        except Exception:
            logger.debug("take verification failed", exc_info=True)
            return 0.5, ""
        finally:
            try:
                os.remove(path)
            except OSError:
                pass
        norm = lambda s: re.sub(r"[^\w ]+", "", str(s).casefold()).strip()
        return difflib.SequenceMatcher(None, norm(heard), norm(target)).ratio(), heard

    def transcribe_file(self, path: str, language: str | None = None) -> str:
        """Speech to text for a file on disk (voice notes of the inbox) with the same Whisper model as the phone speech input."""
        if not hasattr(self, "_whisper_model"):
            settings = self.signals.configuration_settings
            device = str(settings.get_main_setting("whisper_device") or "cpu").lower()
            model = None
            if device == "cuda":
                try:
                    index = int(settings.get_main_setting("whisper_gpu_index") or 0)
                    model = WhisperModel("small", device="cuda", device_index=index, compute_type="float16")
                except Exception:
                    logger.warning("Whisper on CUDA failed for the inbox; using the CPU", exc_info=True)
            self._whisper_model = model or WhisperModel("small", device="cpu", compute_type="int8")
        if language is None:
            configured = str(self.signals.configuration_settings.get_main_setting("stt_language") or "auto").strip().lower()
            language = None if configured in ("", "auto") else configured
        segments, _info = self._whisper_model.transcribe(path, beam_size=5, language=language)
        return "".join(s.text for s in segments).strip()

    pending_phone_turn = False
    phone_turn = False
    pending_text_only = False
    phone_text_only = False

    def begin_turn(self):
        """Called when a message is handled: remembers whether the phone (not the PC) asked for it."""
        self.phone_turn = self.pending_phone_turn and self.has_phone()
        self.phone_text_only = self.phone_turn and self.pending_text_only
        self.pending_phone_turn = False
        self.pending_text_only = False
        self._update_call_audio()

    async def _open_chat_quietly(self, char_name: str):
        """The phone picked a character: the host loads it but the PC window stays on whatever page it showed."""
        if getattr(self, "_open_lock", None) is None:
            self._open_lock = asyncio.Lock()
        async with self._open_lock:                  # one chat is built at a time (switch request + first message arrive together)
            if str(getattr(self.signals, "current_active_character", "")) == str(char_name):
                return
            stack = getattr(getattr(self.signals, "ui", None), "stackedWidget", None)
            before = stack.currentWidget() if stack is not None else None
            try:
                await self.signals.open_chat(char_name)
            finally:
                if stack is not None and before is not None:
                    stack.setCurrentWidget(before)

    def _update_call_audio(self):
        """While a phone call runs, or the phone asked for the text, the voice comes out of the phone only (PC speakers stay silent)."""
        try:
            from app.utils import text_to_speech
            in_call = any(m.get("call") for m in self.manager.meta.values())
            mute = bool(self.signals.configuration_settings.get_main_setting("android_call_mute_pc") is not False)
            text_to_speech.set_remote_audio_only((in_call or self.phone_turn) and mute)
        except Exception:
            logger.debug("could not update the call audio routing", exc_info=True)

    async def phone_command(self, action: str, params: dict | None = None, timeout: float = 30.0) -> dict:
        target = next((ws for ws, m in self.manager.meta.items() if m.get("role") == "phone"), None)
        if target is None:
            return {"ok": False, "error": "no_phone"}
        command_id = uuid.uuid4().hex[:12]
        future = asyncio.get_running_loop().create_future()
        self.phone_pending[command_id] = future
        try:
            await target.send_json({"type": "device_command", "id": command_id, "action": action, "params": params or {}})
            return await asyncio.wait_for(future, timeout)
        except asyncio.TimeoutError:
            return {"ok": False, "error": "timeout"}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}
        finally:
            self.phone_pending.pop(command_id, None)

    def _speech_only_enabled(self) -> bool:
        """Is the "only the spoken words to the phone" option on?"""
        try:
            return self.signals.configuration_settings.get_main_setting("android_speech_only") is not False
        except Exception:
            return True

    def _plain_text_mode(self) -> bool:
        try:
            return bool(self.signals.configuration_settings.get_main_setting("llm_plain_text_only"))
        except Exception:
            return False

    listeners: list = []

    def _notify(self, kind: str):
        """Other parts of the program (the 'Hey Yume' overlay) follow the stream of the chat: chunk / audio / message_start / message_end."""
        for cb in list(self.listeners):
            try:
                cb(kind)
            except Exception:
                logger.debug("bridge listener failed", exc_info=True)

    async def broadcast_chunk(self, chunk: str):
        self._notify("chunk")
        if not self._speech_only_enabled() or self._plain_text_mode():      # plain-text mode: the model writes only speech already
            await self.manager.broadcast({"type": "chunk", "text": chunk})
            return
        spoken = self._speech.feed(chunk)                   # phones get only what is said, everybody else the whole text
        def message_for(role):
            if role != "phone":
                return {"type": "chunk", "text": chunk}
            return {"type": "chunk", "text": spoken} if spoken else None
        await self.manager.broadcast_by_role(message_for)
        
    async def broadcast_message_start(self):
        self._speech.reset()
        self._notify("message_start")
        await self.manager.broadcast({"type": "message_start"})
        
    async def broadcast_message_end(self):
        self._notify("message_end")
        await self.manager.broadcast({"type": "message_end"})

    async def broadcast_character_change(self, new_char: str):
        await self.manager.broadcast({"type": "character_changed", "character": new_char})

    async def broadcast_audio(self, b64_audio: str):
        if self.phone_text_only:
            return
        self._notify("audio")
        await self.manager.broadcast({"type": "audio", "data": b64_audio})

async def run_web_server(interface_signals, host="127.0.0.1", port=8000, auth_token=None):
    bridge = WebBridge(interface_signals, auth_token=auth_token)
    config = uvicorn.Config(bridge.app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)
    await server.serve()
