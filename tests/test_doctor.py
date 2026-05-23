from pathlib import Path

from app.chao.doctor import run_chao_doctor


class Completed:
    def __init__(self, stdout: str = "", returncode: int = 0, stderr: str = ""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_chao_doctor_reports_ready_with_runtime_dependencies(tmp_path):
    workspace = tmp_path / "workspace"
    (workspace / ".git").mkdir(parents=True)
    repositories_config = tmp_path / "repositories.toml"
    repositories_config.write_text(
        f"""
default_repository = "demo"

[repositories.demo]
enabled = true
git_url = "git@github.com:example/demo.git"
default_branch = "main"
workspace_path = "{workspace.as_posix()}"
sandbox_root = "{(tmp_path / "sandboxes").as_posix()}"
branch_prefix = "codex/"
""".strip(),
        encoding="utf-8",
    )

    def command_exists(command: str) -> bool:
        return command in {"uv", "docker", "gh"}

    def command_runner(command, **_kwargs):
        if command[:3] == ["docker", "ps", "--filter"]:
            return Completed("chao-postgres\n")
        if command[:3] == ["docker", "exec", "chao-postgres"]:
            return Completed("chao-postgres:5432 - accepting connections\n")
        if command == ["uv", "run", "python", "scripts/schema_check.py"]:
            return Completed("schema check passed\n")
        if command == ["gh", "auth", "status"]:
            return Completed("Logged in to github.com\n")
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

    report = run_chao_doctor(
        repo_root=Path("."),
        environ={
            "CHAO_REPOSITORIES_CONFIG": str(repositories_config),
            "DEEPSEEK_" + "API_KEY": "x",
        },
        command_exists=command_exists,
        command_runner=command_runner,
    )

    assert report["status"] == "ready"
    assert report["ready"] is True
    assert {check["name"]: check["ready"] for check in report["checks"]} == {
        "command:uv": True,
        "docker:postgres": True,
        "database:schema": True,
        "github:auth": True,
        "llm:deepseek_key": True,
        "repository:config": True,
        "repository:workspace": True,
        "self_upgrade:agents_and_skills": True,
    }


def test_chao_doctor_reports_blocked_when_required_dependencies_are_missing(tmp_path):
    repositories_config = tmp_path / "repositories.toml"
    repositories_config.write_text(
        """
default_repository = "demo"

[repositories.demo]
enabled = false
git_url = "git@github.com:example/demo.git"
default_branch = "main"
workspace_path = "/missing/workspace"
sandbox_root = "/missing/sandboxes"
branch_prefix = "codex/"
""".strip(),
        encoding="utf-8",
    )

    report = run_chao_doctor(
        environ={"CHAO_REPOSITORIES_CONFIG": str(repositories_config)},
        command_exists=lambda _command: False,
        command_runner=lambda command, **_kwargs: Completed(stderr=str(command), returncode=1),
    )

    checks = {check["name"]: check for check in report["checks"]}

    assert report["status"] == "blocked"
    assert report["ready"] is False
    assert checks["command:uv"]["ready"] is False
    assert checks["docker:postgres"]["summary"] == "docker is not available on PATH"
    assert checks["database:schema"]["summary"] == "schema check requires uv"
    assert checks["github:auth"]["summary"] == "gh is not available on PATH"
    assert checks["llm:deepseek_key"]["ready"] is False
    assert checks["repository:config"]["ready"] is False
    assert checks["self_upgrade:agents_and_skills"]["ready"] is True
