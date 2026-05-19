import os
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

ProviderName = Literal["deepseek", "openai", "anthropic", "openai-compatible"]


@dataclass(frozen=True)
class LLMProviderDefaults:
    name: ProviderName
    api_style: str
    base_url: str | None
    api_key_env: str
    model_env: str
    default_model: str | None
    notes: str


@dataclass(frozen=True)
class LLMProviderConfig:
    name: ProviderName
    api_style: str
    base_url: str
    api_key_env: str
    model: str
    api_key_set: bool

    def to_safe_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "api_style": self.api_style,
            "base_url": self.base_url,
            "api_key_env": self.api_key_env,
            "model": self.model,
            "api_key_set": self.api_key_set,
        }


PROVIDER_DEFAULTS: dict[ProviderName, LLMProviderDefaults] = {
    "deepseek": LLMProviderDefaults(
        name="deepseek",
        api_style="openai-compatible",
        base_url="https://api.deepseek.com",
        api_key_env="DEEPSEEK_API_KEY",
        model_env="DEEPSEEK_MODEL",
        default_model="deepseek-chat",
        notes="DeepSeek official API is OpenAI-compatible.",
    ),
    "openai": LLMProviderDefaults(
        name="openai",
        api_style="openai",
        base_url="https://api.openai.com/v1",
        api_key_env="OPENAI_API_KEY",
        model_env="OPENAI_MODEL",
        default_model="gpt-4.1-mini",
        notes="OpenAI native API provider.",
    ),
    "anthropic": LLMProviderDefaults(
        name="anthropic",
        api_style="anthropic",
        base_url="https://api.anthropic.com",
        api_key_env="ANTHROPIC_API_KEY",
        model_env="ANTHROPIC_MODEL",
        default_model="claude-3-5-sonnet-latest",
        notes="Anthropic native Messages API provider.",
    ),
    "openai-compatible": LLMProviderDefaults(
        name="openai-compatible",
        api_style="openai-compatible",
        base_url=None,
        api_key_env="CHAO_LLM_API_KEY",
        model_env="CHAO_LLM_MODEL",
        default_model=None,
        notes="Generic OpenAI-compatible provider configured by environment.",
    ),
}


def list_llm_provider_defaults() -> list[LLMProviderDefaults]:
    return list(PROVIDER_DEFAULTS.values())


def get_llm_provider_defaults(name: str) -> LLMProviderDefaults:
    try:
        return PROVIDER_DEFAULTS[name.lower()]
    except KeyError as exc:
        raise ValueError(f"unsupported LLM provider: {name}") from exc


def build_llm_provider_config(
    provider: str | None = None,
    environ: Mapping[str, str] | None = None,
) -> LLMProviderConfig:
    env = environ or os.environ
    provider_name = (provider or env.get("CHAO_LLM_PROVIDER") or "deepseek").lower()
    defaults = get_llm_provider_defaults(provider_name)

    api_key_env = env.get("CHAO_LLM_API_KEY_ENV") or defaults.api_key_env
    base_url = env.get("CHAO_LLM_BASE_URL") or defaults.base_url
    model = env.get("CHAO_LLM_MODEL") or env.get(defaults.model_env) or defaults.default_model

    if not base_url:
        raise ValueError(f"{defaults.name} requires CHAO_LLM_BASE_URL")

    if not model:
        raise ValueError(f"{defaults.name} requires CHAO_LLM_MODEL")

    return LLMProviderConfig(
        name=defaults.name,
        api_style=defaults.api_style,
        base_url=base_url,
        api_key_env=api_key_env,
        model=model,
        api_key_set=bool(env.get(api_key_env)),
    )
