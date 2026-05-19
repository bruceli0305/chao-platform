from app.chao.llm_providers import (
    build_llm_provider_config,
    get_llm_provider_defaults,
    list_llm_provider_defaults,
)


def test_default_llm_provider_is_deepseek_without_exposing_key():
    config = build_llm_provider_config(environ={})

    assert config.to_safe_dict() == {
        "name": "deepseek",
        "api_style": "openai-compatible",
        "base_url": "https://api.deepseek.com",
        "api_key_env": "DEEPSEEK_API_KEY",
        "model": "deepseek-chat",
        "api_key_set": False,
    }


def test_deepseek_provider_detects_key_presence_without_returning_key():
    key_env = "DEEPSEEK" + "_API" + "_KEY"
    key_value = "test" + "-key" + "-value"
    config = build_llm_provider_config(environ={key_env: key_value})

    assert config.api_key_set is True
    assert key_value not in str(config.to_safe_dict())


def test_openai_provider_uses_openai_defaults():
    config = build_llm_provider_config(provider="openai", environ={})

    assert config.name == "openai"
    assert config.api_style == "openai"
    assert config.base_url == "https://api.openai.com/v1"
    assert config.model == "gpt-4.1-mini"


def test_anthropic_provider_uses_anthropic_defaults():
    config = build_llm_provider_config(provider="anthropic", environ={})

    assert config.name == "anthropic"
    assert config.api_style == "anthropic"
    assert config.base_url == "https://api.anthropic.com"
    assert config.model == "claude-3-5-sonnet-latest"


def test_openai_compatible_provider_requires_base_url():
    try:
        build_llm_provider_config(provider="openai-compatible", environ={})
    except ValueError as exc:
        assert str(exc) == "openai-compatible requires CHAO_LLM_BASE_URL"
    else:
        raise AssertionError("expected missing base URL to raise")


def test_openai_compatible_provider_uses_generic_environment():
    config = build_llm_provider_config(
        provider="openai-compatible",
        environ={
            "CHAO_LLM_BASE_URL": "https://example.test/v1",
            "CHAO_LLM_MODEL": "example-model",
            "CHAO_LLM_API_KEY": "example" + "-key",
        },
    )

    assert config.to_safe_dict() == {
        "name": "openai-compatible",
        "api_style": "openai-compatible",
        "base_url": "https://example.test/v1",
        "api_key_env": "CHAO_LLM_API_KEY",
        "model": "example-model",
        "api_key_set": True,
    }


def test_llm_provider_registry_rejects_unknown_provider():
    try:
        get_llm_provider_defaults("unknown")
    except ValueError as exc:
        assert str(exc) == "unsupported LLM provider: unknown"
    else:
        raise AssertionError("expected unknown provider to raise")


def test_list_llm_provider_defaults_contains_supported_providers():
    provider_names = {provider.name for provider in list_llm_provider_defaults()}

    assert provider_names == {"deepseek", "openai", "anthropic", "openai-compatible"}
