from app.chao.repositories import RepositoryConfig
from app.chao.self_upgrade_delivery import execute_self_upgrade_delivery


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


def test_execute_self_upgrade_delivery_dry_run_reports_commands():
    calls = []

    def fake_runner(command, **_kwargs):
        calls.append(command)
        if command[3:6] == ["status", "--short", "--"]:
            return Completed(" M app/chao/demo.py\n")
        raise AssertionError(command)

    result = execute_self_upgrade_delivery(
        _repository_config(),
        changed_files=["app/chao/demo.py"],
        commit_message="self-upgrade: patch demo",
        dry_run=True,
        command_runner=fake_runner,
    )

    assert result["dry_run"] is True
    assert result["committed"] is False
    assert result["status_lines"] == [" M app/chao/demo.py"]
    assert result["commands"] == [
        ["git", "-C", ".", "add", "--", "app/chao/demo.py"],
        ["git", "-C", ".", "commit", "-m", "self-upgrade: patch demo"],
    ]


def test_execute_self_upgrade_delivery_commits_and_pushes():
    calls = []

    def fake_runner(command, **_kwargs):
        calls.append(command)
        if command[3:6] == ["status", "--short", "--"]:
            return Completed(" M app/chao/demo.py\n")
        if command[3:4] == ["add"]:
            return Completed()
        if command[3:4] == ["commit"]:
            return Completed("[branch abc123] self-upgrade: patch demo\n")
        if command[3:4] == ["push"]:
            return Completed("pushed\n")
        if command[3:5] == ["rev-parse", "HEAD"]:
            return Completed("abc123\n")
        raise AssertionError(command)

    result = execute_self_upgrade_delivery(
        _repository_config(),
        changed_files=["app/chao/demo.py"],
        commit_message="self-upgrade: patch demo",
        dry_run=False,
        push=True,
        command_runner=fake_runner,
    )

    assert result["errors"] == []
    assert result["committed"] is True
    assert result["pushed"] is True
    assert result["commit_sha"] == "abc123"
    assert calls[-2] == ["git", "-C", ".", "push", "-u", "origin", "HEAD"]


def test_execute_self_upgrade_delivery_rejects_no_changes():
    def fake_runner(command, **_kwargs):
        if command[3:6] == ["status", "--short", "--"]:
            return Completed("")
        raise AssertionError(command)

    result = execute_self_upgrade_delivery(
        _repository_config(),
        changed_files=["app/chao/demo.py"],
        commit_message="self-upgrade: patch demo",
        dry_run=False,
        command_runner=fake_runner,
    )

    assert result["committed"] is False
    assert result["errors"] == ["no self-upgrade changes to commit"]
