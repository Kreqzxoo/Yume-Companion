"""External tool model: the decision "which tool with which arguments?" can be made by a separate language model on another PC
(e.g. the Tools tab of the Yume LLM Server, port + 3) instead of the chat model. The ANSWER is still written by the chat model.

Off (default): the chat model also handles the tools. On: the external server decides; when it is unreachable the chat model takes over
for two minutes (so a switched-off server never blocks the chat).
"""
from __future__ import annotations

import logging
import time
import urllib.request
from urllib.parse import urlparse

from app.configuration import configuration

logger = logging.getLogger("ToolLLM")
_down_until = 0.0


def _api():
    return configuration.ConfigurationAPI()


def _settings():
    return configuration.ConfigurationSettings()


def enabled() -> bool:
    try:
        return bool(_settings().get_main_setting("tool_llm_external")) and bool(base_url())
    except Exception:
        return False


def base_url() -> str:
    try:
        return str(_api().get_token("TOOL_LLM_BASE_URL") or "").strip()
    except Exception:
        return ""


def model_name() -> str:
    try:
        return str(_settings().get_main_setting("tool_llm_model") or "local-model")
    except Exception:
        return "local-model"


def api_key() -> str:
    try:
        return str(_api().get_token("TOOL_LLM_API_TOKEN") or "")
    except Exception:
        return ""


def save(on: bool, url: str, model: str, key: str):
    s = _settings()
    s.update_main_setting("tool_llm_external", bool(on))
    s.update_main_setting("tool_llm_model", (model or "").strip() or "local-model")
    _api().save_api_token("TOOL_LLM_BASE_URL", (url or "").strip())
    _api().save_api_token("TOOL_LLM_API_TOKEN", (key or "").strip())
    global _down_until
    _down_until = 0.0


def suggested_url() -> str:
    """Same PC as the external chat model, port 8083 (Tools tab of the Yume LLM Server)."""
    try:
        base = str(_api().get_token("REMOTE_LLM_BASE_URL") or "").strip()
        if base:
            u = urlparse(base if "://" in base else "http://" + base)
            if u.hostname:
                return f"http://{u.hostname}:8083"
    except Exception:
        pass
    return ""


def provider():
    """RemoteLLMProvider for the decisions, or None (off / server recently unreachable)."""
    if not enabled() or time.time() < _down_until:
        return None
    from app.utils.ai_clients.providers.remote_provider import RemoteLLMProvider
    return RemoteLLMProvider(base_url=base_url(), model=model_name(), api_key=api_key())


def mark_down(seconds: float = 120.0):
    global _down_until
    _down_until = time.time() + seconds


def normalize(url: str) -> str:
    url = (url or "").strip().rstrip("/")
    if url and "://" not in url:
        url = "http://" + url
    return url


def test(url: str, key: str = "") -> tuple[bool, str]:
    """Asks /v1/models (llama.cpp, Ollama, LM Studio ...). -> (ok, text)"""
    url = normalize(url)
    if not url:
        return False, "Keine Adresse eingetragen."
    base = url[:-3] if url.endswith("/v1") else url
    req = urllib.request.Request(base + "/v1/models", headers={"Authorization": "Bearer " + (key or "none")})
    try:
        import json
        with urllib.request.urlopen(req, timeout=5) as r:
            data = json.loads(r.read().decode("utf-8", "replace"))
        names = [m.get("id", "?") for m in data.get("data", [])][:3]
        return True, "Erreichbar" + (": " + ", ".join(names) if names else ".")
    except Exception as exc:
        return False, f"Nicht erreichbar ({str(exc)[:80]}). Läuft der Yume LLM Server, ist der Tab „Werkzeuge“ aktiv und „beim Start mitstarten“ gesetzt?"
