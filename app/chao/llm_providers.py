import os
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

ProviderName = str

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LLM_PROVIDERS_PATH = REPO_ROOT / "config" / "llm-providers.toml"


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


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("optional provider field must be a string")
    if not value.strip():
        return None
    return value


def _required_str(data: Mapping[str, object], key: str, provider_name: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{provider_name} requires {key}")
    return value


def load_llm_provider_defaults(
    config_path: Path = DEFAULT_LLM_PROVIDERS_PATH,
) -> tuple[str, dict[ProviderName, LLMProviderDefaults]]:
    data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    default_provider = data.get("default_provider")
    providers = data.get("providers")

    if not isinstance(default_provider, str) or not default_provider.strip():
        raise ValueError(f"{config_path}: default_provider is required")
    if not isinstance(providers, dict) or not providers:
        raise ValueError(f"{config_path}: providers table is required")

    defaults = {}
    for provider_name, raw_provider in providers.items():
        if not isinstance(provider_name, str):
            raise ValueError(f"{config_path}: provider names must be strings")
        if not isinstance(raw_provider, dict):
            raise ValueError(f"{config_path}: providers.{provider_name} must be a table")

        defaults[provider_name] = LLMProviderDefaults(
            name=provider_name,
            api_style=_required_str(raw_provider, "api_style", provider_name),
            base_url=_optional_str(raw_provider.get("base_url")),
            api_key_env=_required_str(raw_provider, "key_env", provider_name),
            model_env=_required_str(raw_provider, "model_env", provider_name),
            default_model=_optional_str(raw_provider.get("default_model")),
            notes=_optional_str(raw_provider.get("notes")) or "",
        )

    if default_provider not in defaults:
        raise ValueError(f"{config_path}: default_provider is not configured: {default_provider}")

    return default_provider, defaults


DEFAULT_PROVIDER, PROVIDER_DEFAULTS = load_llm_provider_defaults()


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
    env = os.environ if environ is None else environ
    provider_name = (provider or env.get("CHAO_LLM_PROVIDER") or DEFAULT_PROVIDER).lower()
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
