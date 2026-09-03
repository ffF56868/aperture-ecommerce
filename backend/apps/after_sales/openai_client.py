"""Small, lazy OpenAI client factory for the after-sales Agent."""

from typing import Any

from django.conf import settings


class OpenAIConfigurationError(RuntimeError):
    """Raised before a request is attempted when Agent configuration is incomplete."""


def get_openai_client() -> Any:
    """Return an OpenAI SDK client without exposing the key to application code."""

    api_key = settings.OPENAI_API_KEY.strip()
    if not api_key:
        raise OpenAIConfigurationError(
            "未配置 OPENAI_API_KEY。请在 backend/.env 中填写 API Key 后重启后端服务。"
        )

    # Keep the import lazy so management commands and tests work before the SDK is installed.
    from openai import OpenAI

    # The API endpoint is served by Gunicorn with a shorter request lifetime than
    # the SDK's default retry window. One bounded attempt lets the view return a
    # controlled 503 instead of having the worker killed during a retry sleep.
    request_timeout = max(5, min(settings.OPENAI_REQUEST_TIMEOUT_SECONDS, 20))
    return OpenAI(
        api_key=api_key,
        timeout=request_timeout,
        max_retries=0,
    )


def get_openai_model() -> str:
    """Return the configured model name for the future Responses API loop."""

    return settings.OPENAI_MODEL
