import logging
import os
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from .base_client import BaseLLMClient
from .validators import validate_model

logger = logging.getLogger(__name__)

# Mapping of provider name to its required environment variable
_PROVIDER_API_KEY_ENV = {
    "xai": "XAI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "minimax": "MINIMAX_API_KEY",
    "custom": "CUSTOM_LLM_API_KEY",
}


class UnifiedChatOpenAI(ChatOpenAI):
    """ChatOpenAI subclass that strips temperature/top_p for GPT-5 family models.

    GPT-5 family models use reasoning natively. temperature/top_p are only
    accepted when reasoning.effort is 'none'; with any other effort level
    (or for older GPT-5/GPT-5-mini/GPT-5-nano which always reason) the API
    rejects these params. Langchain defaults temperature=0.7, so we must
    strip it to avoid errors.

    Non-GPT-5 models (GPT-4.1, xAI, Ollama, etc.) are unaffected.
    """

    def __init__(self, **kwargs):
        if "gpt-5" in kwargs.get("model", "").lower():
            kwargs.pop("temperature", None)
            kwargs.pop("top_p", None)
        super().__init__(**kwargs)


class OpenAIClient(BaseLLMClient):
    """Client for OpenAI-compatible providers (OpenAI, xAI, DeepSeek, MiniMax, Ollama, OpenRouter, Custom)."""

    def __init__(
        self,
        model: str,
        base_url: Optional[str] = None,
        provider: str = "openai",
        **kwargs,
    ):
        super().__init__(model, base_url, **kwargs)
        self.provider = provider.lower()

    _PROVIDER_BASE_URLS = {
        "xai": "https://api.x.ai/v1",
        "openrouter": "https://openrouter.ai/api/v1",
        "deepseek": "https://api.deepseek.com",
        "minimax": "https://api.minimaxi.com/v1",
        "ollama": "http://localhost:11434/v1",
    }

    def get_llm(self) -> Any:
        """Return configured ChatOpenAI instance."""
        llm_kwargs = {"model": self.model}

        if self.provider == "ollama":
            llm_kwargs["base_url"] = self._PROVIDER_BASE_URLS["ollama"]
            llm_kwargs["api_key"] = "ollama"
        elif self.provider == "custom":
            if self.base_url:
                llm_kwargs["base_url"] = self.base_url
            self._set_api_key(llm_kwargs)
        elif self.provider in self._PROVIDER_BASE_URLS:
            llm_kwargs["base_url"] = self._PROVIDER_BASE_URLS[self.provider]
            self._set_api_key(llm_kwargs)
        elif self.base_url:
            llm_kwargs["base_url"] = self.base_url

        for key in ("timeout", "max_retries", "reasoning_effort", "api_key", "callbacks", "http_client", "http_async_client", "streaming", "extra_body"):
            if key in self.kwargs:
                llm_kwargs[key] = self.kwargs[key]

        # When streaming is enabled, also request usage metadata so that
        # token counts are included in the streamed response.
        if llm_kwargs.get("streaming"):
            llm_kwargs["stream_usage"] = True

        return UnifiedChatOpenAI(**llm_kwargs)

    def _set_api_key(self, llm_kwargs: dict) -> None:
        """Read the provider's API key from env and warn if missing."""
        env_var = _PROVIDER_API_KEY_ENV.get(self.provider)
        if not env_var:
            return
        api_key = os.environ.get(env_var)
        if api_key:
            llm_kwargs["api_key"] = api_key
        else:
            logger.warning(
                "%s environment variable is not set. "
                "API calls to %s will likely fail. "
                "Set it in your .env file or environment.",
                env_var,
                self.provider,
            )

    def validate_model(self) -> bool:
        """Validate model for the provider."""
        return validate_model(self.provider, self.model)
