import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.chao.llm_providers import LLMProviderConfig

DEEPSEEK_THINKING_MODELS = {"deepseek-v4-pro"}
DEEPSEEK_DEFAULT_REASONING_EFFORT = "low"
DEEPSEEK_MIN_THINKING_MAX_TOKENS = 8192


@dataclass(frozen=True)
class LLMChatRequest:
    url: str
    headers: dict[str, str]
    payload: dict[str, Any]

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "url": self.url,
            "headers": {key: "<redacted>" for key in self.headers},
            "payload": _redact_payload(self.payload),
        }


@dataclass(frozen=True)
class LLMChatResult:
    provider: str
    model: str
    status: str
    dry_run: bool
    request: dict[str, Any]
    response: dict[str, Any] | None
    error: str | None

    def to_safe_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "status": self.status,
            "dry_run": self.dry_run,
            "request": self.request,
            "response": self.response,
            "error": self.error,
        }


def build_llm_chat_request(
    config: LLMProviderConfig,
    prompt: str,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    require_api_key: bool = True,
) -> LLMChatRequest:
    api_key = _require_api_key(config) if require_api_key else "<dry-run>"

    if config.api_style in {"openai", "openai-compatible"}:
        return _build_openai_compatible_request(
            config,
            api_key,
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    if config.api_style == "anthropic":
        return _build_anthropic_request(
            config,
            api_key,
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    raise ValueError(f"unsupported LLM API style: {config.api_style}")


def execute_llm_chat_completion(
    config: LLMProviderConfig,
    prompt: str,
    *,
    system_prompt: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 1024,
    dry_run: bool = True,
) -> LLMChatResult:
    try:
        request = build_llm_chat_request(
            config,
            prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            max_tokens=max_tokens,
            require_api_key=not dry_run,
        )
    except Exception as exc:
        return LLMChatResult(
            provider=config.name,
            model=config.model,
            status="failed",
            dry_run=dry_run,
            request={},
            response=None,
            error=str(exc),
        )

    if dry_run:
        return LLMChatResult(
            provider=config.name,
            model=config.model,
            status="dry_run",
            dry_run=True,
            request=request.to_safe_dict(),
            response=None,
            error=None,
        )

    try:
        response = _post_json(request)
    except Exception as exc:
        return LLMChatResult(
            provider=config.name,
            model=config.model,
            status="failed",
            dry_run=False,
            request=request.to_safe_dict(),
            response=None,
            error=str(exc),
        )

    return LLMChatResult(
        provider=config.name,
        model=config.model,
        status="success",
        dry_run=False,
        request=request.to_safe_dict(),
        response=response,
        error=None,
    )


def _require_api_key(config: LLMProviderConfig) -> str:
    import os

    api_key = os.environ.get(config.api_key_env)
    if not api_key:
        raise ValueError(f"missing API key environment variable: {config.api_key_env}")

    return api_key


def _build_openai_compatible_request(
    config: LLMProviderConfig,
    api_key: str,
    prompt: str,
    *,
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
) -> LLMChatRequest:
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload: dict[str, Any] = {
        "model": config.model,
        "messages": messages,
        "max_tokens": max_tokens,
    }
    if _uses_deepseek_thinking_mode(config):
        payload["max_tokens"] = max(max_tokens, DEEPSEEK_MIN_THINKING_MAX_TOKENS)
        payload["reasoning_effort"] = DEEPSEEK_DEFAULT_REASONING_EFFORT
        payload["thinking"] = {"type": "enabled"}
    else:
        payload["temperature"] = temperature

    return LLMChatRequest(
        url=f"{config.base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        payload=payload,
    )


def _uses_deepseek_thinking_mode(config: LLMProviderConfig) -> bool:
    return config.name == "deepseek" and config.model in DEEPSEEK_THINKING_MODELS


def _build_anthropic_request(
    config: LLMProviderConfig,
    api_key: str,
    prompt: str,
    *,
    system_prompt: str | None,
    temperature: float,
    max_tokens: int,
) -> LLMChatRequest:
    payload: dict[str, Any] = {
        "model": config.model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if system_prompt:
        payload["system"] = system_prompt

    return LLMChatRequest(
        url=f"{config.base_url.rstrip('/')}/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
        payload=payload,
    )


def _post_json(request: LLMChatRequest) -> dict[str, Any]:
    payload = json.dumps(request.payload).encode("utf-8")
    http_request = urllib.request.Request(
        request.url,
        data=payload,
        headers=request.headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(http_request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM HTTP error {exc.code}: {body[:500]}") from exc


def _redact_payload(payload: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(payload)

    if "messages" in redacted and isinstance(redacted["messages"], list):
        redacted["messages"] = [
            _redact_message(message)
            if isinstance(message, dict)
            else {"type": type(message).__name__, "content": "<redacted>"}
            for message in redacted["messages"]
        ]

    if "system" in redacted and isinstance(redacted["system"], str):
        redacted["system"] = {
            "content": "<redacted>",
            "content_chars": len(redacted["system"]),
        }

    return redacted


def _redact_message(message: dict[str, Any]) -> dict[str, Any]:
    redacted = dict(message)
    content = redacted.get("content")

    if isinstance(content, str):
        redacted["content"] = "<redacted>"
        redacted["content_chars"] = len(content)
    elif content is not None:
        redacted["content"] = "<redacted>"
        redacted["content_type"] = type(content).__name__

    return redacted