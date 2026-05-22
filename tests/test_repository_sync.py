from app.chao.repositories import RepositoryConfig
from app.chao.repository_sync import (
    build_repository_doctor_report,
    build_repository_status_report,
    build_repository_sync_plan,
    execute_repository_sync,
    inspect_repository_status,
)


def _repository_config(
    *,
    name: str = "demo",
    workspace_path: str,
) -> RepositoryConfig:
    return RepositoryConfig(
        name=name,
        git_url="git@github.com:example/demo.git",
        default_branch="main",
        workspace_path=workspace_path,
        sandbox_root=".chao/sandboxes",
        branch_prefix="codex/",
        enabled=True,
    )


def test_build_repository_sync_plan_clones_missing_workspace(tmp_path):
    workspace = tmp_path / "demo"
    repository = _repository_config(workspace_path=str(workspace))

    result = build_repository_sync_plan(repository)

    assert result["action"] == "clone"
    assert result["workspace_exists"] is False
    assert result["is_git_repository"] is False
    assert result["commands"] == [
        ["git", "clone", "git@github.com:example/demo.git", str(workspace)]
    ]
    assert result["errors"] == []


def test_build_repository_sync_plan_fetches_existing_git_workspace(tmp_path):
    workspace = tmp_path / "demo"
    (workspace / ".git").mkdir(parents=True)
    repository = _repository_config(workspace_path=str(workspace))

    result = build_repository_sync_plan(repository)

    assert result["action"] == "fetch"
    assert result["workspace_exists"] is True
    assert result["is_git_repository"] is True
    assert result["commands"] == [["git", "-C", str(workspace), "fetch", "origin", "main"]]


def test_build_repository_sync_plan_supports_ff_only_pull(tmp_path):
    workspace = tmp_path / "demo"
    (workspace / ".git").mkdir(parents=True)
    repository = _repository_config(workspace_path=str(workspace))

    result = build_repository_sync_plan(repository, mode="pull-ff-only")

    assert result["action"] == "pull-ff-only"
    assert result["commands"] == [
        ["git", "-C", str(workspace), "pull", "--ff-only", "origin", "main"]
    ]


def test_build_repository_sync_plan_rejects_non_git_directory(tmp_path):
    workspace = tmp_path / "demo"
    workspace.mkdir()
    repository = _repository_config(workspace_path=str(workspace))

    result = build_repository_sync_plan(repository)

    assert result["action"] == "none"
    assert result["commands"] == []
    assert result["errors"] == [f"repository workspace is not a git repository: {workspace}"]


def test_execute_repository_sync_runs_planned_command(tmp_path):
    workspace = tmp_path / "demo"
    (workspace / ".git").mkdir(parents=True)
    repository = _repository_config(workspace_path=str(workspace))
    calls = []

    class Completed:
        returncode = 0
        stdout = "ok"
        stderr = ""

    def fake_runner(command, **kwargs):
        calls.append((command, kwargs))
        return Completed()

    result = execute_repository_sync(
        repository,
        dry_run=False,
        command_runner=fake_runner,
    )

    assert result["executed"] is True
    assert result["dry_run"] is False
    assert calls[0][0] == ["git", "-C", str(workspace), "fetch", "origin", "main"]
    assert calls[0][1]["check"] is False


def test_inspect_repository_status_reports_git_workspace_state(tmp_path):
    workspace = tmp_path / "demo"
    (workspace / ".git").mkdir(parents=True)
    repository = _repository_config(workspace_path=str(workspace))
    calls = []

    class Completed:
        def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_runner(command, **_kwargs):
        calls.append(command)
        if command[-2:] == ["branch", "--show-current"]:
            return Completed("main\n")
        if command[-2:] == ["rev-parse", "HEAD"]:
            return Completed("abc123\n")
        if command[-3:] == ["config", "--get", "remote.origin.url"]:
            return Completed("git@github.com:example/demo.git\n")
        if command[-2:] == ["status", "--short"]:
            return Completed(" M app/chao/demo.py\n")
        if command[-4:] == ["rev-list", "--left-right", "--count", "HEAD...origin/main"]:
            return Completed("1\t2\n")
        raise AssertionError(command)

    result = inspect_repository_status(repository, command_runner=fake_runner)

    assert result["current_branch"] == "main"
    assert result["head_commit"] == "abc123"
    assert result["remote_url"] == "git@github.com:example/demo.git"
    assert result["dirty"] is True
    assert result["status_lines"] == [" M app/chao/demo.py"]
    assert result["ahead"] == 1
    assert result["behind"] == 2
    assert result["errors"] == []
    assert calls[0] == ["git", "-C", str(workspace), "branch", "--show-current"]


def test_inspect_repository_status_reports_missing_workspace(tmp_path):
    repository = _repository_config(workspace_path=str(tmp_path / "missing"))

    result = inspect_repository_status(repository)

    assert result["workspace_exists"] is False
    assert result["is_git_repository"] is False
    assert result["current_branch"] is None
    assert result["errors"] == []


def test_inspect_repository_status_rejects_non_git_directory(tmp_path):
    workspace = tmp_path / "demo"
    workspace.mkdir()
    repository = _repository_config(workspace_path=str(workspace))

    result = inspect_repository_status(repository)

    assert result["workspace_exists"] is True
    assert result["is_git_repository"] is False
    assert result["errors"] == [f"repository workspace is not a git repository: {workspace}"]


def test_build_repository_status_report_summarizes_workspaces(tmp_path):
    ready_workspace = tmp_path / "ready"
    dirty_workspace = tmp_path / "dirty"
    (ready_workspace / ".git").mkdir(parents=True)
    (dirty_workspace / ".git").mkdir(parents=True)
    repositories = [
        _repository_config(name="ready", workspace_path=str(ready_workspace)),
        _repository_config(name="dirty", workspace_path=str(dirty_workspace)),
    ]

    class Completed:
        def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_runner(command, **_kwargs):
        workspace = command[2]
        if command[-2:] == ["branch", "--show-current"]:
            return Completed("main\n")
        if command[-2:] == ["rev-parse", "HEAD"]:
            return Completed("abc123\n")
        if command[-3:] == ["config", "--get", "remote.origin.url"]:
            return Completed("git@github.com:example/demo.git\n")
        if command[-2:] == ["status", "--short"]:
            return Completed(" M app/chao/demo.py\n" if workspace == str(dirty_workspace) else "")
        if command[-4:] == ["rev-list", "--left-right", "--count", "HEAD...origin/main"]:
            return Completed("0\t1\n")
        raise AssertionError(command)

    report = build_repository_status_report(repositories, command_runner=fake_runner)

    assert report["summary"] == {
        "repositories": 2,
        "ready": 2,
        "dirty": 1,
        "errors": 0,
    }
    assert report["repositories"][0]["workspace_ready"] is True
    assert report["repositories"][1]["dirty"] is True
    assert report["repositories"][1]["behind"] == 1


def test_build_repository_doctor_report_marks_clean_workspace_ready(tmp_path):
    workspace = tmp_path / "demo"
    (workspace / ".git").mkdir(parents=True)
    repository = _repository_config(workspace_path=str(workspace))

    class Completed:
        def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_runner(command, **_kwargs):
        if command[-2:] == ["branch", "--show-current"]:
            return Completed("main\n")
        if command[-2:] == ["rev-parse", "HEAD"]:
            return Completed("abc123\n")
        if command[-3:] == ["config", "--get", "remote.origin.url"]:
            return Completed("git@github.com:example/demo.git\n")
        if command[-2:] == ["status", "--short"]:
            return Completed("")
        if command[-4:] == ["rev-list", "--left-right", "--count", "HEAD...origin/main"]:
            return Completed("0\t0\n")
        raise AssertionError(command)

    report = build_repository_doctor_report(repository, command_runner=fake_runner)

    assert report["status"] == "ready"
    assert report["runner_ready"] is True
    assert report["suggested_action"] == "ready"
    assert report["sync_plan"]["action"] == "fetch"


def test_build_repository_doctor_report_suggests_clone_for_missing_workspace(tmp_path):
    repository = _repository_config(workspace_path=str(tmp_path / "missing"))

    report = build_repository_doctor_report(repository)

    assert report["status"] == "blocked"
    assert report["runner_ready"] is False
    assert report["suggested_action"] == "run_repository_sync_apply"
    assert report["sync_plan"]["action"] == "clone"


def test_build_repository_doctor_report_blocks_dirty_workspace(tmp_path):
    workspace = tmp_path / "demo"
    (workspace / ".git").mkdir(parents=True)
    repository = _repository_config(workspace_path=str(workspace))

    class Completed:
        def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    def fake_runner(command, **_kwargs):
        if command[-2:] == ["branch", "--show-current"]:
            return Completed("main\n")
        if command[-2:] == ["rev-parse", "HEAD"]:
            return Completed("abc123\n")
        if command[-3:] == ["config", "--get", "remote.origin.url"]:
            return Completed("git@github.com:example/demo.git\n")
        if command[-2:] == ["status", "--short"]:
            return Completed(" M app/chao/demo.py\n")
        if command[-4:] == ["rev-list", "--left-right", "--count", "HEAD...origin/main"]:
            return Completed("0\t0\n")
        raise AssertionError(command)

    report = build_repository_doctor_report(repository, command_runner=fake_runner)

    assert report["runner_ready"] is False
    assert report["suggested_action"] == "review_local_changes"
