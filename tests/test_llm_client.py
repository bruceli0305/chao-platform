import os

from app.chao.llm_client import build_llm_chat_request, execute_llm_chat_completion
from app.chao.llm_providers import build_llm_provider_config


def test_build_deepseek_chat_request_uses_openai_compatible_shape(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    config = build_llm_provider_config(environ=os.environ)

    request = build_llm_chat_request(config, "hello", system_prompt="system")

    assert request.url == "https://api.deepseek.com/chat/completions"
    assert request.payload["model"] == "deepseek-v4-pro"
    assert request.payload["messages"] == [
        {"role": "system", "content": "system"},
        {"role": "user", "content": "hello"},
    ]
    assert request.payload["thinking"] == {"type": "enabled"}
    assert request.payload["reasoning_effort"] == "high"
    assert "temperature" not in request.payload
    assert request.to_safe_dict()["headers"]["Authorization"] == "<redacted>"
    assert request.to_safe_dict()["payload"]["messages"] == [
        {"role": "system", "content": "<redacted>", "content_chars": 6},
        {"role": "user", "content": "<redacted>", "content_chars": 5},
    ]


def test_execute_llm_chat_completion_dry_run_does_not_require_api_key():
    config = build_llm_provider_config(environ={})

    result = execute_llm_chat_completion(config, "hello", dry_run=True)

    assert result.status == "dry_run"
    assert result.error is None
    assert result.request["headers"]["Authorization"] == "<redacted>"
    assert result.request["payload"]["messages"][0]["content"] == "<redacted>"


def test_execute_llm_chat_completion_execute_requires_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    config = build_llm_provider_config(environ={})

    result = execute_llm_chat_completion(config, "hello", dry_run=False)

    assert result.status == "failed"
    assert result.error == "missing API key environment variable: DEEPSEEK_API_KEY"


def test_build_anthropic_chat_request_uses_messages_endpoint(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    config = build_llm_provider_config(provider="anthropic", environ=os.environ)

    request = build_llm_chat_request(config, "hello", system_prompt="system")

    assert request.url == "https://api.anthropic.com/v1/messages"
    assert request.payload["system"] == "system"
    assert request.payload["messages"] == [{"role": "user", "content": "hello"}]
    assert request.to_safe_dict()["headers"]["x-api-key"] == "<redacted>"
    assert request.to_safe_dict()["payload"]["system"] == {
        "content": "<redacted>",
        "content_chars": 6,
    }
