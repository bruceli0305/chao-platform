import json

from app.chao.github_ci import execute_github_pr_checks
from app.chao.repositories import RepositoryConfig


def _repository_config():
    return RepositoryConfig(
        name="chao-platform",
        git_url="git@github.com:example/repo.git",
        default_branch="main",
        workspace_path=".",
        sandbox_root=".chao/sandboxes",
        branch_prefix="codex/",
        enabled=True,
    )


class Completed:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


def test_execute_github_pr_checks_dry_run_builds_command():
    result = execute_github_pr_checks(
        _repository_config(),
        pr_ref="https://github.com/example/repo/pull/42",
        dry_run=True,
    )

    assert result["status"] == "dry_run"
    assert result["commands"] == [
        [
            "gh",
            "pr",
            "checks",
            "https://github.com/example/repo/pull/42",
            "--json",
            "name,state,link,bucket,workflow",
        ]
    ]


def test_execute_github_pr_checks_classifies_success():
    def fake_runner(command, **_kwargs):
        assert command[:3] == ["gh", "pr", "checks"]
        return Completed(
            json.dumps(
                [
                    {
                        "name": "test",
                        "state": "SUCCESS",
                        "link": "https://github.com/example/repo/actions/runs/1",
                        "workflow": "CI",
                        "bucket": "pass",
                    }
                ]
            )
        )

    result = execute_github_pr_checks(
        _repository_config(),
        pr_ref="42",
        dry_run=False,
        command_runner=fake_runner,
    )

    assert result["status"] == "passed"
    assert result["deliverable"] is True
    assert result["checks"][0]["name"] == "test"


def test_execute_github_pr_checks_classifies_pending_and_failed():
    def pending_runner(_command, **_kwargs):
        return Completed(json.dumps([{"name": "test", "state": "PENDING"}]))

    pending = execute_github_pr_checks(
        _repository_config(),
        pr_ref="42",
        dry_run=False,
        command_runner=pending_runner,
    )

    assert pending["status"] == "pending"
    assert pending["deliverable"] is False

    def failed_runner(_command, **_kwargs):
        return Completed(json.dumps([{"name": "test", "state": "FAILURE"}]))

    failed = execute_github_pr_checks(
        _repository_config(),
        pr_ref="42",
        dry_run=False,
        command_runner=failed_runner,
    )

    assert failed["status"] == "failed"
    assert failed["deliverable"] is False
