from app.chao.repositories import (
    get_repository_config,
    list_repository_configs,
    load_repository_registry,
    validate_repository_configs,
)


def test_repository_registry_loads_default_config():
    default_repository, registry = load_repository_registry()

    assert default_repository == "chao-platform"
    assert registry["chao-platform"].git_url == "git@github.com:bruceli0305/chao-platform.git"
    assert registry["chao-platform"].default_branch == "main"
    assert registry["chao-platform"].branch_prefix == "codex/"


def test_repository_config_can_be_loaded_from_env_override(tmp_path):
    config = tmp_path / "repositories.toml"
    config.write_text(
        """
default_repository = "demo"

[repositories.demo]
enabled = true
git_url = "https://github.com/example/demo.git"
default_branch = "main"
workspace_path = "/opt/chao/workspaces/demo"
sandbox_root = "/opt/chao/sandboxes/demo"
branch_prefix = "codex/"
""".strip(),
        encoding="utf-8",
    )

    repository = get_repository_config(
        environ={"CHAO_REPOSITORIES_CONFIG": str(config)},
    )

    assert repository.name == "demo"
    assert repository.workspace_path == "/opt/chao/workspaces/demo"
    assert repository.sandbox_root == "/opt/chao/sandboxes/demo"


def test_list_repository_configs_returns_safe_dicts():
    repositories = list_repository_configs()

    assert repositories[0].to_safe_dict()["name"] == "chao-platform"
    assert "git_url" in repositories[0].to_safe_dict()


def test_validate_repository_configs_passes_default_config():
    assert validate_repository_configs() == []


def test_validate_repository_configs_reports_disabled_default(tmp_path):
    config = tmp_path / "repositories.toml"
    config.write_text(
        """
default_repository = "demo"

[repositories.demo]
enabled = false
git_url = "https://github.com/example/demo.git"
default_branch = "main"
workspace_path = "/opt/chao/workspaces/demo"
sandbox_root = "/opt/chao/sandboxes/demo"
branch_prefix = "codex/"
""".strip(),
        encoding="utf-8",
    )

    errors = validate_repository_configs(environ={"CHAO_REPOSITORIES_CONFIG": str(config)})

    assert errors == [
        "at least one repository must be enabled",
        "default repository is disabled: demo",
    ]
