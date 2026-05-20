import os
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_REPOSITORIES_CONFIG_PATH = REPO_ROOT / "config" / "repositories.toml"


@dataclass(frozen=True)
class RepositoryConfig:
    name: str
    git_url: str
    default_branch: str
    workspace_path: str
    sandbox_root: str
    branch_prefix: str
    enabled: bool

    def to_safe_dict(self) -> dict[str, object]:
        return asdict(self)


def resolve_repositories_config_path(
    environ: dict[str, str] | None = None,
) -> Path:
    env = os.environ if environ is None else environ
    configured_path = env.get("CHAO_REPOSITORIES_CONFIG")

    if configured_path:
        return Path(configured_path).expanduser()

    return DEFAULT_REPOSITORIES_CONFIG_PATH


def _required_str(data: dict[str, object], field_name: str, repository_name: str) -> str:
    value = data.get(field_name)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{repository_name} requires {field_name}")
    return value


def _optional_bool(data: dict[str, object], field_name: str, default: bool) -> bool:
    value = data.get(field_name, default)
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value


def _build_repository_config(name: str, data: dict[str, object]) -> RepositoryConfig:
    git_url = _required_str(data, "git_url", name)
    default_branch = _required_str(data, "default_branch", name)
    workspace_path = _required_str(data, "workspace_path", name)
    sandbox_root = _required_str(data, "sandbox_root", name)
    branch_prefix = _required_str(data, "branch_prefix", name)
    enabled = _optional_bool(data, "enabled", True)

    if branch_prefix in {"main", "master", "trunk"}:
        raise ValueError(f"{name}: branch_prefix must not be a protected branch name")
    if not branch_prefix.endswith("/"):
        raise ValueError(f"{name}: branch_prefix must end with /")

    return RepositoryConfig(
        name=name,
        git_url=git_url,
        default_branch=default_branch,
        workspace_path=workspace_path,
        sandbox_root=sandbox_root,
        branch_prefix=branch_prefix,
        enabled=enabled,
    )


def load_repository_registry(
    config_path: Path | None = None,
    environ: dict[str, str] | None = None,
) -> tuple[str, dict[str, RepositoryConfig]]:
    resolved_path = config_path or resolve_repositories_config_path(environ)
    data = tomllib.loads(resolved_path.read_text(encoding="utf-8"))
    default_repository = data.get("default_repository")
    repositories = data.get("repositories")

    if not isinstance(default_repository, str) or not default_repository.strip():
        raise ValueError(f"{resolved_path}: default_repository is required")
    if not isinstance(repositories, dict) or not repositories:
        raise ValueError(f"{resolved_path}: repositories table is required")

    registry = {}
    for repository_name, repository_data in repositories.items():
        if not isinstance(repository_name, str):
            raise ValueError(f"{resolved_path}: repository names must be strings")
        if not isinstance(repository_data, dict):
            raise ValueError(f"{resolved_path}: repositories.{repository_name} must be a table")
        registry[repository_name] = _build_repository_config(repository_name, repository_data)

    if default_repository not in registry:
        raise ValueError(
            f"{resolved_path}: default_repository is not configured: {default_repository}"
        )

    return default_repository, registry


def list_repository_configs(
    *,
    environ: dict[str, str] | None = None,
) -> list[RepositoryConfig]:
    _, registry = load_repository_registry(environ=environ)
    return list(registry.values())


def get_repository_config(
    name: str | None = None,
    *,
    environ: dict[str, str] | None = None,
) -> RepositoryConfig:
    default_repository, registry = load_repository_registry(environ=environ)
    repository_name = name or default_repository

    try:
        return registry[repository_name]
    except KeyError as exc:
        raise ValueError(f"unsupported repository: {repository_name}") from exc


def validate_repository_configs(
    *,
    environ: dict[str, str] | None = None,
) -> list[str]:
    try:
        default_repository, registry = load_repository_registry(environ=environ)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as exc:
        return [str(exc)]

    errors = []
    active_repositories = [repository for repository in registry.values() if repository.enabled]

    if not active_repositories:
        errors.append("at least one repository must be enabled")

    if not registry[default_repository].enabled:
        errors.append(f"default repository is disabled: {default_repository}")

    return errors
