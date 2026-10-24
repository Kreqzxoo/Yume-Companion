import asyncio
import base64
import json
import logging
import time
from typing import Any, Optional

from PIL import Image
from curl_cffi.requests import AsyncSession

from app.configuration import configuration

logger = logging.getLogger("Characters Card Client")

IMPERSONATE = "chrome124"

DEFAULT_HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
}

CLOUDFLARE_MARKERS = ("Attention Required!", "Just a moment...")


class _TTLCache:

    def __init__(self, ttl_seconds: int = 60):
        self.ttl = ttl_seconds
        self._store: dict[str, tuple[float, Any]] = {}

    def get(self, key: str):
        item = self._store.get(key)
        if not item:
            return None
        expires_at, value = item
        if time.monotonic() > expires_at:
            self._store.pop(key, None)
            return None
        return value

    def set(self, key: str, value: Any):
        self._store[key] = (time.monotonic() + self.ttl, value)


class CharactersCard:
    _session: Optional[AsyncSession] = None
    _session_lock = asyncio.Lock()

    _trending_cache = _TTLCache(ttl_seconds=60)
    _search_cache = _TTLCache(ttl_seconds=30)
    _info_cache = _TTLCache(ttl_seconds=300)
    _hub_cache = _TTLCache(ttl_seconds=60)

    HUB_TAGS = [
        "", "fantasy", "romance", "adventure", "sci-fi", "horror", "comedy",
        "drama", "mystery", "slice of life", "historical", "cyberpunk",
        "school", "rpg", "anime", "magic", "supernatural", "action",
        "wholesome", "villain", "yandere", "tsundere", "oc", "female", "male",
    ]

    HUB_SORTS = {
        "trending": "trending",
        "recent": "new",
        "popular": "download_count",
        "favorites": "star_count",
    }

    def __init__(self):
        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_api = configuration.ConfigurationAPI()
        self.configuration_characters = configuration.ConfigurationCharacters()

    @classmethod
    async def _get_session(cls) -> AsyncSession:
        if cls._session is None:
            async with cls._session_lock:
                if cls._session is None:
                    cls._session = AsyncSession(
                        headers=DEFAULT_HEADERS,
                        timeout=20,
                    )
        return cls._session

    @classmethod
    async def close(cls):
        if cls._session is not None:
            await cls._session.close()
            cls._session = None

    async def _get_json(self, url: str, retries: int = 2) -> Optional[dict]:
        session = await self._get_session()

        last_error = None
        for attempt in range(retries + 1):
            try:
                response = await session.get(url, impersonate=IMPERSONATE)
                text = response.text

                if any(marker in text for marker in CLOUDFLARE_MARKERS):
                    logger.warning(
                        "Cloudflare challenge detected (attempt %s/%s): %s",
                        attempt + 1, retries + 1, url,
                    )
                    last_error = "cloudflare_challenge"
                    await asyncio.sleep(0.5 * (attempt + 1))
                    continue

                if response.status_code != 200:
                    logger.error(
                        "HTTP Error %s for %s: %s",
                        response.status_code, url, text[:300],
                    )
                    last_error = f"http_{response.status_code}"
                    continue

                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    logger.error("Failed to parse JSON from %s: %s", url, text[:300])
                    return None

            except Exception as e:
                logger.error("Request error for %s: %s", url, e)
                last_error = str(e)
                await asyncio.sleep(0.5 * (attempt + 1))

        logger.error("Giving up on %s after %s attempts (%s)", url, retries + 1, last_error)
        return None

    def _nsfw_flag(self) -> bool:
        return bool(self.configuration_settings.get_main_setting("nsfw_query"))

    async def fetch_trending_character_data(self):
        nsfw = self._nsfw_flag()
        cache_key = f"trending:{nsfw}"
        cached = self._trending_cache.get(cache_key)
        if cached is not None:
            return cached

        url = (
            "https://gateway.chub.ai/search?first=50&page=1&namespace=characters"
            f"&nsfw={'true' if nsfw else 'false'}&nsfw_only=false&nsfl=false"
            "&min_tokens=100&max_tokens=100000&chub=true&sort=trending&venus=true&count=false"
        )

        data = await self._get_json(url)
        if data is not None:
            self._trending_cache.set(cache_key, data)
        return data

    async def search_character(self, character_name: str):
        nsfw = self._nsfw_flag()
        cache_key = f"search:{nsfw}:{character_name}"
        cached = self._search_cache.get(cache_key)
        if cached is not None:
            return cached

        if nsfw:
            url = (
                "https://gateway.chub.ai/search?first=50&page=1&namespace=characters"
                f"&search={character_name}&include_forks=true&nsfw=true&nsfw_only=false"
                "&nsfl=false&asc=false&min_ai_rating=0&min_tokens=100&max_tokens=100000"
                "&chub=true&exclude_mine=true&sort=default&topics=&inclusive_or=false"
                "&recommended_verified=false&venus=true&count=false"
            )
        else:
            url = (
                "https://gateway.chub.ai/search?excludetopics=NSFW&first=50&page=1"
                f"&namespace=characters&search={character_name}&include_forks=true"
                "&nsfw=false&nsfw_only=false&nsfl=false&asc=false&min_ai_rating=0"
                "&min_tokens=100&max_tokens=100000&chub=true&exclude_mine=true"
                "&sort=default&topics=&inclusive_or=false&recommended_verified=false"
                "&venus=true&count=false"
            )

        data = await self._get_json(url)
        if data is not None:
            self._search_cache.set(cache_key, data)
        return data

    async def get_character_information(self, full_path: str):
        cached = self._info_cache.get(full_path)
        if cached is not None:
            return cached

        url = f"https://gateway.chub.ai/api/characters/{full_path}?full=true&nocache=0.6411485396222347"
        data = await self._get_json(url)

        if not data:
            return self._default_character_data()

        node = data.get("node")
        if not node:
            return self._default_character_data()

        definition = node.get("definition", {})
        result = (
            node.get("name", "Unknown"),
            node.get("tagline", "No tagline"),
            node.get("avatar_url", "No avatar"),
            node.get("starCount", 0),
            node.get("n_favorites", 0),
            node.get("nTokens", 0),
            definition.get("personality", ""),
            definition.get("first_message", ""),
            definition.get("tavern_personality", ""),
            definition.get("example_dialogs", ""),
            definition.get("scenario", ""),
            definition.get("alternate_greetings", []),
        )
        self._info_cache.set(full_path, result)
        return result

    async def search_hub(self, query: str = "", page: int = 1, first: int = 50,
                         sort: str = "trending", topics=None, nsfw: bool = False):
        from urllib.parse import quote

        query = (query or "").strip()
        sort_val = self.HUB_SORTS.get(sort, "trending")
        page = max(1, int(page or 1))
        first = max(1, min(100, int(first or 50)))

        cache_key = f"hub:{sort_val}:{page}:{first}:{nsfw}:{topics}:{query}"
        cached = self._hub_cache.get(cache_key)
        if cached is not None:
            return cached

        url = (
            "https://gateway.chub.ai/search"
            f"?first={first}&page={page}&namespace=characters"
            f"&search={quote(query)}&include_forks=true"
            f"&nsfw={'true' if nsfw else 'false'}&nsfw_only=false&nsfl=false"
            "&asc=false&min_ai_rating=0&min_tokens=100&max_tokens=100000"
            f"&chub=true&exclude_mine=true&sort={sort_val}"
            "&inclusive_or=false&recommended_verified=false&venus=true&count=true"
        )
        if topics:
            url += f"&topics={quote(','.join(topics))}"

        data = await self._get_json(url)
        if data is None:
            return [], False

        payload = data.get("data", data) or {}
        nodes = payload.get("nodes", []) or []
        total = None
        if isinstance(payload.get("total_count"), int):
            total = payload["total_count"]
        elif isinstance(payload.get("totalCount"), int):
            total = payload["totalCount"]

        has_more = len(nodes) >= first and (total is None or page * first < total)
        result = (nodes, has_more)
        self._hub_cache.set(cache_key, result)
        return result

    async def download_character_card(self, full_path: str) -> Optional[bytes]:
        from urllib.parse import quote

        session = await self._get_session()

        encoded_path = "/".join(quote(part, safe="") for part in full_path.strip("/").split("/"))
        cdn_url = f"https://avatars.charhub.io/avatars/{encoded_path}/chara_card_v2.png"
        try:
            response = await session.get(cdn_url, impersonate=IMPERSONATE, timeout=30)
            if response.status_code == 200 and response.content[:8] == b"\x89PNG\r\n\x1a\n":
                logger.info(f"[Hub] Got ready-made V2 card from CDN for {full_path}")
                return response.content
            logger.info(f"[Hub] CDN card unavailable ({response.status_code}) for {full_path}")
        except Exception as e:
            logger.warning(f"[Hub] CDN download error ({full_path}): {e}")

        from PIL import PngImagePlugin
        import base64
        import io

        node_data = await self._get_json(
            f"https://api.chub.ai/api/characters/{full_path}?full=true"
        )
        node = (node_data or {}).get("node") if isinstance(node_data, dict) else None
        if not node:
            logger.error(f"[Hub] Could not fetch character node for '{full_path}'.")
            return None

        definition = node.get("definition", {}) or {}

        img = None
        avatar_url = node.get("avatar_url") or ""
        if avatar_url:
            try:
                r = await session.get(avatar_url, impersonate=IMPERSONATE, timeout=25)
                if r.status_code == 200 and r.content:
                    img = Image.open(io.BytesIO(r.content))
            except Exception as e:
                logger.warning(f"[Hub] Avatar download failed ({avatar_url}): {e}")

        if img is None:
            img = Image.new("RGB", (512, 768), (24, 24, 34))

        img = img.convert("RGBA")
        if img.width > 768 or img.height > 768:
            img.thumbnail((768, 768), Image.Resampling.LANCZOS)

        card_data = {
            "name": node.get("name") or definition.get("name") or "Unknown",
            "description": definition.get("description", "") or "",
            "personality": definition.get("tavern_personality", "") or definition.get("personality", "") or "",
            "scenario": definition.get("scenario", "") or "",
            "first_mes": definition.get("first_message", "") or "",
            "mes_example": definition.get("example_dialogs", "") or "",
            "creator_notes": "",
            "system_prompt": definition.get("system_prompt", "") or "",
            "post_history_instructions": definition.get("post_history_instructions", "") or "",
            "alternate_greetings": definition.get("alternate_greetings", []) or [],
            "extensions": definition.get("extensions", {}) or {},
        }
        embedded_lorebook = definition.get("embedded_lorebook")
        if isinstance(embedded_lorebook, dict) and embedded_lorebook.get("entries"):
            card_data["character_book"] = embedded_lorebook

        card_v2 = {"spec": "chara_card_v2", "spec_version": "2.0", "data": card_data}

        payload = base64.b64encode(
            json.dumps(card_v2, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")

        png_info = PngImagePlugin.PngInfo()
        png_info.add_text("chara", payload)

        buf = io.BytesIO()
        img.save(buf, format="PNG", pnginfo=png_info)
        logger.info(f"[Hub] Rebuilt V2 card locally for {full_path}")
        return buf.getvalue()

    async def get_many_character_information(self, full_paths: list[str]):
        return await asyncio.gather(
            *(self.get_character_information(fp) for fp in full_paths)
        )

    def _default_character_data(self):
        return (
            'Unknown',                # character_name
            'No tagline',             # character_title
            'No avatar',              # character_avatar_url
            0,                        # downloads
            0,                        # likes
            0,                        # total_tokens
            'No description',         # character_personality
            'No first message',       # first_message
            None,                     # character_tavern_personality
            [],                       # example_dialogs
            'No scenario',            # character_scenario
            []                        # alternate_greetings
        )

class SoulGateway:
    def __init__(self):
        super().__init__()
        self.configuration_settings = configuration.ConfigurationSettings()
        self.configuration_characters = configuration.ConfigurationCharacters()

    def read_v2_card(self, path):
        try:
            image = Image.open(path)
            user_comment = image.text.get('chara', None)
            if user_comment is None:
                return None
            json_bytes = base64.b64decode(user_comment)
            return json.loads(json_bytes.decode('utf-8'))
        except Exception as e:
            logger.error(f"Error decoding V2 card: {e}")
            return None
