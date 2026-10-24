"""Safe, opt-in Home Assistant REST API client for Soul of Waifu.

The endpoint/token come only from user configuration. Tools never accept a URL
from the model, preventing prompt injection from redirecting requests to an
arbitrary host. Control calls are restricted to a conservative allow-list and
require an explicit configured entity allow-list.
"""
from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import aiohttp

from app.configuration.configuration import ConfigurationAPI, ConfigurationSettings

logger = logging.getLogger("Home Assistant")
_ENTITY_RE = re.compile(r"^[a-z0-9_]+\.[a-z0-9_]+$")

# Only these domain/service combinations are callable from an LLM tool.
_ALLOWED_SERVICES = {
    "light": {"turn_on", "turn_off", "toggle"},
    "switch": {"turn_on", "turn_off", "toggle"},
    "input_boolean": {"turn_on", "turn_off", "toggle"},
    "fan": {"turn_on", "turn_off", "toggle"},
    "scene": {"turn_on"},
    "climate": {"set_temperature", "set_hvac_mode"},
    "cover": {"open_cover", "close_cover", "stop_cover"},
    "media_player": {"media_play", "media_pause", "media_play_pause", "media_stop", "volume_set"},
}
_ALLOWED_HVAC_MODES = {"off", "heat", "cool", "heat_cool", "auto", "dry", "fan_only"}


def normalize_base_url(value: str) -> str:
    """Normalize and validate the configured Home Assistant base URL."""
    value = (value or "").strip().rstrip("/")
    parts = urlsplit(value)
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("Bitte eine vollständige URL inklusive http:// oder https:// angeben.")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Die URL darf keine Zugangsdaten, Query-Parameter oder Fragmente enthalten.")
    try:
        _ = parts.port  # raises ValueError for non-numeric or out-of-range ports
    except ValueError as exc:
        raise ValueError("Die URL enthält einen ungültigen Port.") from exc
    if any(ch.isspace() for ch in value):
        raise ValueError("Die URL darf keine Leerzeichen enthalten.")
    path = parts.path.rstrip("/")
    if path.endswith("/api"):
        path = path[:-4].rstrip("/")
    return urlunsplit((parts.scheme, parts.netloc, path, "", "")).rstrip("/")


def parse_entity_allowlist(raw: Any) -> set[str]:
    if isinstance(raw, (list, tuple, set)):
        entries = raw
    else:
        entries = re.split(r"[\s,;]+", str(raw or ""))
    return {item.strip().lower() for item in entries if item and _ENTITY_RE.fullmatch(item.strip().lower())}


class HomeAssistantClient:
    def __init__(self, base_url: str | None = None, token: str | None = None, timeout: float = 8.0):
        settings = ConfigurationSettings()
        api = ConfigurationAPI()
        self.base_url = normalize_base_url(base_url if base_url is not None else settings.get_main_setting("home_assistant_url") or "")
        self.token = token if token is not None else (api.get_token("HOME_ASSISTANT_TOKEN") or "")
        if not self.token.strip():
            raise ValueError("Home-Assistant-Long-Lived-Access-Token fehlt.")
        self.timeout = aiohttp.ClientTimeout(total=max(2.0, min(float(timeout), 20.0)))

    async def _request(self, method: str, path: str, *, payload: dict | None = None):
        url = f"{self.base_url}/api/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "SoulOfWaifu/2.5.3",
        }
        # Redirects are disabled so the bearer token can never be forwarded to
        # a different host by a misconfigured proxy or endpoint.
        async with aiohttp.ClientSession(timeout=self.timeout, headers=headers) as session:
            async with session.request(method, url, json=payload, allow_redirects=False) as response:
                raw = await response.text()
                if 300 <= response.status < 400:
                    raise RuntimeError("Home Assistant antwortete mit einer Weiterleitung; bitte die Basis-URL korrigieren.")
                if response.status < 200 or response.status >= 300:
                    excerpt = raw[:300].replace("\n", " ")
                    raise RuntimeError(f"Home Assistant HTTP {response.status}: {excerpt}")
                if not raw.strip():
                    return None
                try:
                    import json
                    return json.loads(raw)
                except Exception:
                    return raw

    async def test_connection(self) -> dict:
        return await self._request("GET", "")

    async def list_entities(self, query: str = "", limit: int = 30) -> list[dict]:
        states = await self._request("GET", "states")
        if not isinstance(states, list):
            raise RuntimeError("Home Assistant lieferte keine gültige Entitätenliste.")
        query = (query or "").strip().casefold()
        output = []
        for item in states:
            if not isinstance(item, dict):
                continue
            entity_id = str(item.get("entity_id", "")).lower()
            attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
            friendly_name = str(attrs.get("friendly_name", ""))
            if not _ENTITY_RE.fullmatch(entity_id):
                continue
            if query and query not in entity_id.casefold() and query not in friendly_name.casefold():
                continue
            output.append({
                "entity_id": entity_id,
                "name": friendly_name or entity_id,
                "state": str(item.get("state", "unknown"))[:100],
                "domain": entity_id.split(".", 1)[0],
            })
            if len(output) >= max(1, min(int(limit), 50)):
                break
        return output

    async def get_state(self, entity_id: str) -> dict:
        entity_id = (entity_id or "").strip().lower()
        if not _ENTITY_RE.fullmatch(entity_id):
            raise ValueError("Ungültige entity_id. Beispiel: light.wohnzimmer")
        item = await self._request("GET", f"states/{entity_id}")
        if not isinstance(item, dict):
            raise RuntimeError("Home Assistant lieferte keinen gültigen Zustand.")
        attrs = item.get("attributes") if isinstance(item.get("attributes"), dict) else {}
        return {
            "entity_id": entity_id,
            "name": attrs.get("friendly_name", entity_id),
            "state": item.get("state", "unknown"),
            "attributes": {k: v for k, v in attrs.items() if k in {
                "unit_of_measurement", "temperature", "current_temperature", "hvac_mode",
                "brightness", "volume_level", "battery_level", "device_class", "friendly_name"
            }},
            "last_changed": item.get("last_changed"),
        }

    async def call_service(self, domain: str, service: str, entity_id: str, data: dict | None = None) -> dict:
        settings = ConfigurationSettings()
        if not bool(settings.get_main_setting("home_assistant_allow_control")):
            raise PermissionError("Steuerung ist deaktiviert. Aktiviere sie bewusst in den Einstellungen.")
        domain = (domain or "").strip().lower()
        service = (service or "").strip().lower()
        entity_id = (entity_id or "").strip().lower()
        if domain not in _ALLOWED_SERVICES or service not in _ALLOWED_SERVICES[domain]:
            raise PermissionError(f"Der Dienst {domain}.{service} ist aus Sicherheitsgründen nicht freigegeben.")
        if not _ENTITY_RE.fullmatch(entity_id) or entity_id.split(".", 1)[0] != domain:
            raise ValueError("entity_id muss zum angegebenen Domain passen und genau eine Entität bezeichnen.")
        allowlist = self._allowlist()
        if not allowlist:
            raise PermissionError("Lege zuerst konkrete erlaubte entity_id-Werte in der Freigabeliste fest.")
        if entity_id not in allowlist:
            raise PermissionError("Diese Entität ist nicht in der Home-Assistant-Freigabeliste.")
        clean_data: dict[str, Any] = {"entity_id": entity_id}
        data = data if isinstance(data, dict) else {}
        if service == "set_temperature":
            try:
                temperature = float(data.get("temperature"))
            except (TypeError, ValueError):
                raise ValueError("Für set_temperature ist ein numerischer Wert temperature erforderlich.")
            if not 5 <= temperature <= 35:
                raise ValueError("Temperatur muss zwischen 5 und 35 °C liegen.")
            clean_data["temperature"] = temperature
        elif service == "set_hvac_mode":
            mode = str(data.get("hvac_mode", "")).lower()
            if mode not in _ALLOWED_HVAC_MODES:
                raise ValueError("Nicht unterstützter HVAC-Modus.")
            clean_data["hvac_mode"] = mode
        elif service == "volume_set":
            try:
                volume = float(data.get("volume_level"))
            except (TypeError, ValueError):
                raise ValueError("Für volume_set ist volume_level zwischen 0 und 1 erforderlich.")
            if not 0 <= volume <= 1:
                raise ValueError("volume_level muss zwischen 0 und 1 liegen.")
            clean_data["volume_level"] = volume
        # Only validated fields above ever reach Home Assistant; arbitrary data
        # from the LLM is deliberately discarded.
        result = await self._request("POST", f"services/{domain}/{service}", payload=clean_data)
        return {"service": f"{domain}.{service}", "entity_id": entity_id, "result": result}

    @staticmethod
    def _allowlist() -> set[str]:
        settings = ConfigurationSettings()
        return parse_entity_allowlist(settings.get_main_setting("home_assistant_allowed_entities"))
