"""Remote OpenAI-compatible LLM provider (Ollama or llama.cpp server).

This intentionally uses the existing OpenAI-compatible chat-completions client so
streaming, summaries, and tool-call handling follow the same contract as cloud providers.
"""

from app.utils.ai_clients.providers.openai_provider import OpenAIProvider


class RemoteLLMProvider(OpenAIProvider):
    """Connect to an OpenAI-compatible endpoint on another machine or local host."""

    def __init__(self, base_url: str, model: str = "local-model", api_key: str = ""):
        clean_url = (base_url or "").strip().rstrip("/")
        # Accept either the host root or an explicit /v1 endpoint.
        if clean_url.endswith("/v1/chat/completions"):
            clean_url = clean_url[:-len("/chat/completions")]
        elif clean_url.endswith("/v1/models"):
            clean_url = clean_url[:-len("/models")]
        if not clean_url:
            # Safe loopback fallback: never silently send a request to a cloud provider.
            clean_url = "http://127.0.0.1:11434/v1"
        if not clean_url.endswith("/v1"):
            clean_url = f"{clean_url}/v1"

        super().__init__(
            api_key=(api_key or "no-key-required").strip(),
            model=(model or "local-model").strip(),
            base_url=clean_url,
            provider_name="Remote LLM",
        )

    _think_cache = (0.0, False)

    def _thinking_enabled(self) -> bool:
        """Setting 'llm_thinking' (Organizer page > AI behaviour): thinking models reason first (better for hard questions, but slower)."""
        import time as _time
        ts, value = self._think_cache
        if _time.time() - ts < 5:
            return value
        try:
            from app.configuration.configuration import ConfigurationSettings
            value = bool(ConfigurationSettings().get_main_setting("llm_thinking"))
        except Exception:
            value = False
        RemoteLLMProvider._think_cache = (_time.time(), value)
        return value

    def _apply_token_and_sampling_params(self, payload: dict, kwargs: dict, default_max_tokens: int):
        """Qwen3 and other "thinking" models first write a long hidden reasoning. For a companion chat and for tool decisions that only costs
        seconds and - with a small token limit - can use up all tokens so that the answer / the tool call is EMPTY. Thinking is switched off
        (chat_template_kwargs is ignored by servers / templates that do not know it); kwargs thinking=True turns it back on."""
        super()._apply_token_and_sampling_params(payload, kwargs, default_max_tokens)
        if not (kwargs.get("thinking") or self._thinking_enabled()):
            payload["extra_body"] = {"chat_template_kwargs": {"enable_thinking": False}}
        return payload
