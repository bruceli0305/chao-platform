from app.chao.github_pr import build_self_upgrade_pr_body, execute_github_pr_create
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


def test_build_self_upgrade_pr_body_includes_task_code():
    body = build_self_upgrade_pr_body(
        task_code="TASK-1",
        summary="Patch demo heading.",
        changed_files=["app/chao/demo.py"],
        validation_gates=["lint", "test"],
    )

    assert "Task Code: TASK-1" in body
    assert "- app/chao/demo.py" in body
    assert "- lint" in body


def test_execute_github_pr_create_dry_run_builds_command():
    calls = []

    def fake_runner(command, **_kwargs):
        calls.append(command)
        if command == ["git", "branch", "--show-current"]:
            return Completed("codex/task-1-demo\n")
        raise AssertionError(command)

    result = execute_github_pr_create(
        _repository_config(),
        title="self-upgrade: patch demo",
        body="Task Code: TASK-1",
        base_ref="main",
        dry_run=True,
        command_runner=fake_runner,
    )

    assert result["dry_run"] is True
    assert result["head_ref"] == "codex/task-1-demo"
    assert result["commands"] == [
        [
            "gh",
            "pr",
            "create",
            "--base",
            "main",
            "--head",
            "codex/task-1-demo",
            "--title",
            "self-upgrade: patch demo",
            "--body",
            "Task Code: TASK-1",
        ]
    ]


def test_execute_github_pr_create_parses_created_pr_url():
    def fake_runner(command, **_kwargs):
        if command == ["git", "branch", "--show-current"]:
            return Completed("codex/task-1-demo\n")
        if command[:3] == ["gh", "pr", "create"]:
            return Completed("https://github.com/example/repo/pull/42\n")
        raise AssertionError(command)

    result = execute_github_pr_create(
        _repository_config(),
        title="self-upgrade: patch demo",
        body="Task Code: TASK-1",
        base_ref="main",
        dry_run=False,
        command_runner=fake_runner,
    )

    assert result["created"] is True
    assert result["url"] == "https://github.com/example/repo/pull/42"
    assert result["external_id"] == "42"
    assert result["errors"] == []
