import logging
import httpx
from openai import AsyncOpenAI
from app.utils.ai_clients.base_provider import BaseAIProvider

logger = logging.getLogger("OpenRouter Provider")


class OpenRouterProvider(BaseAIProvider):
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str = None,
        session_id: str = None,
        extra_headers: dict = None
    ):
        self.api_key = api_key if api_key else "no-key-required"
        self.model = model if model else "meta-llama/llama-3-8b-instruct:free"
        self.base_url = base_url if base_url else "https://openrouter.ai/api/v1"
        self.session_id = str(session_id)[:256] if session_id else None

        default_headers = {
            "HTTP-Referer": "https://github.com/jofizcd/Soul-of-Waifu",
            "X-Title": "Yume Companion"
        }

        if self.session_id:
            default_headers["x-session-id"] = self.session_id

        if extra_headers:
            default_headers.update(extra_headers)

        self.extra_headers = default_headers

        self.client = AsyncOpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            http_client=httpx.AsyncClient(timeout=120)
        )

    def _prepare_extra_body(self, kwargs: dict) -> dict:
        extra_body = {}
        session_id = kwargs.get("session_id") or self.session_id
        if session_id:
            extra_body["session_id"] = str(session_id)[:256]

        reasoning_effort = kwargs.get("reasoning_effort")
        if reasoning_effort:
            extra_body["reasoning"] = (
                {"enabled": False}
                if reasoning_effort == "none"
                else {"effort": reasoning_effort}
            )
        return extra_body

    def _prepare_headers(self, kwargs: dict) -> dict:
        headers = dict(self.extra_headers)
        session_id = kwargs.get("session_id") or self.session_id
        if session_id:
            headers["x-session-id"] = str(session_id)[:256]
        return headers

    async def generate_stream(self, messages: list[dict], **kwargs):
        extra_body = self._prepare_extra_body(kwargs)
        headers = self._prepare_headers(kwargs)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
            **({"stop": kwargs["stop"]} if kwargs.get("stop") else {}),
            "extra_headers": headers,
            **({"extra_body": extra_body} if extra_body else {})
        }

        if "frequency_penalty" in kwargs:
            payload["frequency_penalty"] = kwargs["frequency_penalty"]
        if "presence_penalty" in kwargs:
            payload["presence_penalty"] = kwargs["presence_penalty"]

        try:
            completion = await self.client.chat.completions.create(**payload)
            async for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenRouter API Stream Error: {e}")
            yield f"\n⚠️ OpenRouter API Error: {str(e)}"

    async def generate_summary(self, messages: list[dict], **kwargs):
        extra_body = self._prepare_extra_body(kwargs)
        extra_body["reasoning"] = {"enabled": False}
        headers = self._prepare_headers(kwargs)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "temperature": kwargs.get("temperature", 0.5),
            "top_p": kwargs.get("top_p", 0.9),
            **({"stop": kwargs["stop"]} if kwargs.get("stop") else {}),
            "extra_headers": headers,
            "extra_body": extra_body
        }

        try:
            completion = await self.client.chat.completions.create(**payload)
            async for chunk in completion:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenRouter API Summary Error: {e}")
            yield ""

    async def generate(self, messages: list[dict], tools: list = None, **kwargs) -> dict:
        extra_body = self._prepare_extra_body(kwargs)
        if "reasoning" not in extra_body:
            extra_body["reasoning"] = {"enabled": False}

        headers = self._prepare_headers(kwargs)

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "max_tokens": kwargs.get("max_tokens", 1000),
            "temperature": kwargs.get("temperature", 0.7),
            "top_p": kwargs.get("top_p", 0.9),
            **({"stop": kwargs["stop"]} if kwargs.get("stop") else {}),
            "extra_headers": headers,
            "extra_body": extra_body
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            completion = await self.client.chat.completions.create(**payload)
            msg = completion.choices[0].message
            return {
                "content": msg.content,
                "tool_calls": msg.tool_calls
            }
        except Exception as e:
            logger.error(f"OpenRouter API Generate Error: {e}")
            return {"content": None, "tool_calls": None}