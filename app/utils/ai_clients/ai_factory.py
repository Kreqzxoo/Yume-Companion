import asyncio
import json
import logging
import time
import weakref
from app.configuration import configuration
from app.utils.ai_clients.providers.openai_provider import OpenAIProvider
from app.utils.ai_clients.providers.openrouter_provider import OpenRouterProvider
from app.utils.ai_clients.providers.mistral_provider import MistralProvider
from app.utils.ai_clients.providers.local_provider import LocalProvider
from app.utils.ai_clients.providers.remote_provider import RemoteLLMProvider
from app.utils.ai_clients.providers.anthropic_provider import AnthropicProvider
from app.utils.ai_clients.providers.gemini_provider import GeminiProvider
from app.utils.ai_clients.providers.deepseek_provider import DeepSeekProvider
from app.utils.ai_clients.providers.grok_provider import GrokProvider
from app.utils.ai_clients.providers.qwen_provider import QwenProvider
from app.utils.ai_clients.providers.zai_provider import ZAIProvider
from app.utils.ai_clients.providers.player2_provider import Player2Provider

logger = logging.getLogger("AI Factory")

try:
    from app.utils.runtime_stats import install_openai_hook
    install_openai_hook()
except Exception:  # statistics must never break the chat
    pass


class _MeteredProvider:
    """Transparent proxy that records speed/size of every chat generation for the dashboard (runtime_stats)."""

    def __init__(self, inner, method):
        object.__setattr__(self, "_inner", inner)
        object.__setattr__(self, "_method", method)

    def __getattr__(self, name):
        return getattr(object.__getattribute__(self, "_inner"), name)

    def __setattr__(self, name, value):
        setattr(object.__getattribute__(self, "_inner"), name, value)

    def _model(self):
        inner = object.__getattribute__(self, "_inner")
        return str(getattr(inner, "model", "") or "")

    async def generate_stream(self, messages, *args, **kwargs):
        from app.utils.runtime_stats import stats, est_tokens, messages_chars
        inner = object.__getattribute__(self, "_inner")
        t0 = time.time()
        first = None
        chars = 0
        ok = True
        stats.llm_begin()
        stats.take_usage()
        try:
            async for chunk in inner.generate_stream(messages, *args, **kwargs):
                if first is None and chunk:
                    first = time.time() - t0
                if isinstance(chunk, str):
                    chars += len(chunk)
                yield chunk
        except Exception:
            ok = False
            raise
        finally:
            try:
                stats.llm_end(object.__getattribute__(self, "_method"), self._model(),
                              max(1, int(messages_chars(messages) / 3.8)), max(0, int(round(chars / 3.8))),
                              first, time.time() - t0, ok, real=stats.take_usage())
            except Exception:
                pass

    async def generate(self, messages, *args, **kwargs):
        from app.utils.runtime_stats import stats, messages_chars
        inner = object.__getattribute__(self, "_inner")
        t0 = time.time()
        ok = True
        out_chars = 0
        stats.llm_begin()
        stats.take_usage()
        try:
            result = await inner.generate(messages, *args, **kwargs)
            if isinstance(result, dict) and isinstance(result.get("content"), str):
                out_chars = len(result["content"])
            return result
        except Exception:
            ok = False
            raise
        finally:
            try:
                dur = time.time() - t0
                stats.llm_end(object.__getattribute__(self, "_method"), self._model(),
                              max(1, int(messages_chars(messages) / 3.8)), int(round(out_chars / 3.8)), None, dur, ok,
                              real=stats.take_usage())
            except Exception:
                pass

class AIFactory:
    # Provider instances (and their HTTP clients) are reused per running event
    # loop while the relevant settings/tokens are unchanged. Without this every
    # call created a fresh async HTTP client that was never closed. httpx
    # clients must not be shared across event loops, hence the per-loop cache.
    _provider_cache = weakref.WeakKeyDictionary()

    @staticmethod
    def get_provider(conversation_method: str):
        """
        Return a provider for the method, reusing a cached one when the
        configuration is unchanged and an event loop is running.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return AIFactory._build_provider(conversation_method)

        try:
            fingerprint = json.dumps(
                [
                    conversation_method,
                    configuration.ConfigurationSettings().load_configuration().get("main_settings"),
                    configuration.ConfigurationAPI().load_configuration(),
                ],
                sort_keys=True, default=str,
            )
        except Exception:
            return AIFactory._build_provider(conversation_method)

        per_loop = AIFactory._provider_cache.setdefault(loop, {})
        cached = per_loop.get(conversation_method)
        if cached and cached[0] == fingerprint:
            return cached[1]
        provider = AIFactory._build_provider(conversation_method)
        if provider is not None:
            per_loop[conversation_method] = (fingerprint, provider)
        return provider

    @staticmethod
    def _build_provider(conversation_method: str):
        provider = AIFactory._build_provider_raw(conversation_method)
        return _MeteredProvider(provider, conversation_method) if provider is not None else None

    @staticmethod
    def _build_provider_raw(conversation_method: str):
        """
        Factory method to instantiate the appropriate AI provider.
        """
        config_settings = configuration.ConfigurationSettings()
        config_api = configuration.ConfigurationAPI()

        if conversation_method == "Open AI":
            api_key = config_api.get_token("OPEN_AI_API_TOKEN")
            model = config_settings.get_main_setting("openai_model") or "gpt-4o-mini"
            base_url = config_api.get_token("CUSTOM_ENDPOINT_URL")
            if base_url and base_url.strip():
                base_url = base_url.strip().rstrip('/')
                if not base_url.endswith('/v1'):
                    base_url = f"{base_url}/v1"
            else:
                base_url = "https://api.openai.com/v1"
            
            return OpenAIProvider(api_key=api_key, model=model, base_url=base_url)

        elif conversation_method == "OpenRouter":
            api_key = config_api.get_token("OPENROUTER_API_TOKEN")
            model = config_settings.get_main_setting("openrouter_model")
            base_url = "https://openrouter.ai/api/v1"

            return OpenRouterProvider(api_key=api_key, model=model, base_url=base_url)

        elif conversation_method == "Mistral AI":
            api_key = config_api.get_token("MISTRAL_AI_API_TOKEN")
            model = config_settings.get_main_setting("mistral_model_endpoint") or "mistral-small-latest"
            return MistralProvider(api_key=api_key, model=model)

        elif conversation_method == "Anthropic":
            api_key = config_api.get_token("ANTHROPIC_API_TOKEN")
            model = config_settings.get_main_setting("anthropic_model") or "claude-sonnet-4-6"
            return AnthropicProvider(api_key=api_key, model=model)

        elif conversation_method == "Google Gemini":
            api_key = config_api.get_token("GEMINI_API_TOKEN")
            model = config_settings.get_main_setting("gemini_model") or "gemini-3.5-flash"
            return GeminiProvider(api_key=api_key, model=model)

        elif conversation_method == "DeepSeek":
            api_key = config_api.get_token("DEEPSEEK_API_TOKEN")
            model = config_settings.get_main_setting("deepseek_model") or "deepseek-v4-flash"
            return DeepSeekProvider(api_key=api_key, model=model)

        elif conversation_method == "Grok":
            api_key = config_api.get_token("GROK_API_TOKEN")
            model = config_settings.get_main_setting("grok_model") or "grok-4.3"
            return GrokProvider(api_key=api_key, model=model)

        elif conversation_method == "Qwen":
            api_key = config_api.get_token("QWEN_API_TOKEN")
            model = config_settings.get_main_setting("qwen_model") or "qwen3.5-flash"
            return QwenProvider(api_key=api_key, model=model)

        elif conversation_method == "Z.AI":
            api_key = config_api.get_token("ZAI_API_TOKEN")
            model = config_settings.get_main_setting("zai_model") or "glm-4.7"
            return ZAIProvider(api_key=api_key, model=model)

        elif conversation_method == "Player2":
            return Player2Provider()

        elif conversation_method == "Remote LLM":
            # Remote Ollama/llama.cpp server exposing an OpenAI-compatible /v1 API.
            remote_url = config_api.get_token("REMOTE_LLM_BASE_URL") or ""
            remote_model = config_settings.get_main_setting("remote_llm_model") or "local-model"
            remote_api_key = config_api.get_token("REMOTE_LLM_API_TOKEN") or ""
            return RemoteLLMProvider(
                base_url=remote_url,
                model=remote_model,
                api_key=remote_api_key,
            )

        elif conversation_method == "Local LLM":
            if config_settings.get_main_setting("local_llm_route") == "remote":
                remote_url = config_api.get_token("REMOTE_LLM_BASE_URL") or ""
                remote_model = config_settings.get_main_setting("remote_llm_model") or "local-model"
                remote_api_key = config_api.get_token("REMOTE_LLM_API_TOKEN") or ""
                return RemoteLLMProvider(
                    base_url=remote_url,
                    model=remote_model,
                    api_key=remote_api_key,
                )

            advanced_enabled = config_settings.get_main_setting("adv_sampling")
            advanced_params = {}
            if advanced_enabled:
                advanced_params = {
                    "min_p": config_settings.get_main_setting("min_p") or 0.05,
                    "xtc_probability": config_settings.get_main_setting("xtc_probability") or 0.0,
                    "xtc_threshold": config_settings.get_main_setting("xtc_threshold") or 0.1,
                    "dry_multiplier": config_settings.get_main_setting("dry_multiplier") or 0.0,
                    "dry_base": config_settings.get_main_setting("dry_base") or 1.75,
                    "dry_allowed_length": config_settings.get_main_setting("dry_allowed_length") or 2
                }
                
                dyn_temp_min = config_settings.get_main_setting("dyn_temp_min")
                dyn_temp_max = config_settings.get_main_setting("dyn_temp_max")
                if dyn_temp_min is not None and dyn_temp_max is not None:
                    dyn_range = (float(dyn_temp_max) - float(dyn_temp_min)) / 2.0
                    if dyn_range > 0:
                        advanced_params["dynatemp_range"] = dyn_range

            return LocalProvider(port=48596, advanced_params=advanced_params)

        else:
            logger.error(f"Unknown conversation method requested: {conversation_method}")
            return None
