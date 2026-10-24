"""Scenes by voice: "Filmabend", "Szene Gute Laune", "aktiviere Lesen" start the matching Home Assistant scene at once (no model needed).
Only scenes that are allowed in the Home Assistant settings (allow-list) are known. The list is cached for 5 minutes."""
from __future__ import annotations

import logging
import re
import time

logger = logging.getLogger("HA Scenes")
_cache = {"t": 0.0, "items": []}
VERBS = r"(?:aktiviere|aktivier|starte|start|schalte|schalt|mach|stell|setz|lade|spiel)"
FILLER = {"die", "den", "das", "szene", "modus", "stimmung", "bitte", "mal", "mir", "an", "ein", "auf", "doch", "jetzt", "mach", "aktiviere", "starte", "schalte", "stell", "setz", "lade", "spiel", "kannst", "du"}


def _norm(s: str) -> str:
    return re.sub(r"[^\w\säöüß]", " ", s.lower()).replace("_", " ")


async def scenes() -> list[tuple[str, str]]:
    """[(entity_id, friendly name)] of the allowed scenes."""
    if time.time() - _cache["t"] < 300:
        return _cache["items"]
    items: list[tuple[str, str]] = []
    try:
        from app.configuration.configuration import ConfigurationSettings
        if bool(ConfigurationSettings().get_main_setting("home_assistant_enabled")):
            from app.utils.integrations.home_assistant import HomeAssistantClient
            for e in await HomeAssistantClient().list_entities("", limit=200):
                if str(e.get("entity_id", "")).startswith("scene."):
                    items.append((e["entity_id"], str(e.get("name") or e["entity_id"].split(".", 1)[1])))
    except Exception:
        logger.debug("scene list not available", exc_info=True)
    _cache.update(t=time.time(), items=items)
    return items


def pick(text: str, items: list[tuple[str, str]]) -> tuple[str, str] | None:
    """The scene meant by this sentence (all words of the scene name appear, nothing else important is said), or None."""
    sentence = _norm(text)
    words = [w for w in sentence.split() if w not in FILLER]
    if not words or len(words) > 4 or len(sentence.split()) > 7:
        return None
    best = None
    for entity, name in items:
        tokens = [w for w in _norm(name).split() if w not in FILLER]
        if not tokens:
            continue
        if sorted(tokens) == sorted(words) or (len(tokens) >= 2 and set(tokens) <= set(words) and len(words) <= len(tokens) + 1):
            if best is None or len(tokens) > best[2]:
                best = (entity, name, len(tokens))
    return (best[0], best[1]) if best else None


async def match(text: str) -> tuple[str, str] | None:
    items = await scenes()
    return pick(text, items) if items else None


async def activate(entity_id: str) -> tuple[bool, str]:
    try:
        from app.utils.integrations.home_assistant import HomeAssistantClient
        result = await HomeAssistantClient().call_service("scene", "turn_on", entity_id, {})
        return True, f"Szene aktiviert: {entity_id.split('.', 1)[1].replace('_', ' ')}."
    except Exception as exc:
        return False, f"Home Assistant: {str(exc)[:120]}"
