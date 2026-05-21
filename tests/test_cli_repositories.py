from typer.testing import CliRunner

from app.chao import cli


def test_repositories_list_outputs_configured_repositories():
    result = CliRunner().invoke(cli.app, ["repositories-list", "--json"])

    assert result.exit_code == 0
    assert "chao-platform" in result.output
    assert "git@github.com:bruceli0305/chao-platform.git" in result.output
    assert "codex/" in result.output


def test_repository_show_outputs_default_repository():
    result = CliRunner().invoke(cli.app, ["repository-show"])

    assert result.exit_code == 0
    assert '"name": "chao-platform"' in result.output
    assert '"default_branch": "main"' in result.output


def test_repository_show_rejects_unknown_repository():
    result = CliRunner().invoke(cli.app, ["repository-show", "missing"])

    assert result.exit_code == 1
    assert "unsupported repository: missing" in result.output


def test_repositories_validate_passes_default_config():
    result = CliRunner().invoke(cli.app, ["repositories-validate", "--json"])

    assert result.exit_code == 0
    assert '"status": "success"' in result.output
    assert '"errors": []' in result.output


def test_repository_sync_outputs_dry_run_plan(monkeypatch):
    calls = []

    def fake_execute_repository_sync(repository_config, **kwargs):
        calls.append((repository_config, kwargs))
        return {
            "repository": repository_config.name,
            "git_url": repository_config.git_url,
            "workspace_path": repository_config.workspace_path,
            "default_branch": repository_config.default_branch,
            "action": "fetch",
            "commands": [
                ["git", "-C", repository_config.workspace_path, "fetch", "origin", "main"]
            ],
            "workspace_exists": True,
            "is_git_repository": True,
            "dry_run": kwargs["dry_run"],
            "executed": False,
            "errors": [],
        }

    monkeypatch.setattr(cli, "execute_repository_sync", fake_execute_repository_sync)

    result = CliRunner().invoke(cli.app, ["repository-sync", "chao-platform"])

    assert result.exit_code == 0
    assert calls[0][1] == {"mode": "fetch", "dry_run": True}
    assert '"action": "fetch"' in result.output
    assert '"dry_run": true' in result.output


def test_repository_sync_apply_can_use_ff_only_pull(monkeypatch):
    calls = []

    def fake_execute_repository_sync(repository_config, **kwargs):
        calls.append((repository_config, kwargs))
        return {
            "repository": repository_config.name,
            "git_url": repository_config.git_url,
            "workspace_path": repository_config.workspace_path,
            "default_branch": repository_config.default_branch,
            "action": "pull-ff-only",
            "commands": [
                [
                    "git",
                    "-C",
                    repository_config.workspace_path,
                    "pull",
                    "--ff-only",
                    "origin",
                    "main",
                ]
            ],
            "workspace_exists": True,
            "is_git_repository": True,
            "dry_run": kwargs["dry_run"],
            "executed": True,
            "errors": [],
        }

    monkeypatch.setattr(cli, "execute_repository_sync", fake_execute_repository_sync)

    result = CliRunner().invoke(
        cli.app,
        ["repository-sync", "--pull-ff-only", "--apply"],
    )

    assert result.exit_code == 0
    assert calls[0][1] == {"mode": "pull-ff-only", "dry_run": False}
    assert '"executed": true' in result.output


def test_repository_status_outputs_workspace_status(monkeypatch):
    calls = []

    def fake_inspect_repository_status(repository_config):
        calls.append(repository_config)
        return {
            "repository": repository_config.name,
            "workspace_path": repository_config.workspace_path,
            "default_branch": repository_config.default_branch,
            "workspace_exists": True,
            "is_git_repository": True,
            "current_branch": "main",
            "head_commit": "abc123",
            "remote_url": repository_config.git_url,
            "dirty": False,
            "status_lines": [],
            "ahead": 0,
            "behind": 0,
            "errors": [],
        }

    monkeypatch.setattr(cli, "inspect_repository_status", fake_inspect_repository_status)

    result = CliRunner().invoke(cli.app, ["repository-status", "chao-platform"])

    assert result.exit_code == 0
    assert calls[0].name == "chao-platform"
    assert '"current_branch": "main"' in result.output
    assert '"dirty": false' in result.output


def test_repository_status_exits_nonzero_on_workspace_error(monkeypatch):
    def fake_inspect_repository_status(repository_config):
        return {
            "repository": repository_config.name,
            "workspace_path": repository_config.workspace_path,
            "default_branch": repository_config.default_branch,
            "workspace_exists": True,
            "is_git_repository": False,
            "current_branch": None,
            "head_commit": None,
            "remote_url": None,
            "dirty": False,
            "status_lines": [],
            "ahead": None,
            "behind": None,
            "errors": ["repository workspace is not a git repository: ."],
        }

    monkeypatch.setattr(cli, "inspect_repository_status", fake_inspect_repository_status)

    result = CliRunner().invoke(cli.app, ["repository-status"])

    assert result.exit_code == 1
    assert "repository workspace is not a git repository" in result.output
