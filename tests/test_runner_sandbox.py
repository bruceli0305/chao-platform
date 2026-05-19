from dataclasses import dataclass
from pathlib import Path

import pytest

from app.chao.runner_sandbox import build_runner_sandbox_commands, execute_runner_sandbox_commands


@dataclass
class FakeCompletedProcess:
    returncode: int
    stdout: str = ""
    stderr: str = ""


def test_build_runner_sandbox_commands_maps_gate_to_docker_command(tmp_path):
    commands, errors = build_runner_sandbox_commands(
        ["compile"],
        workspace_path=".",
        image="sandbox-image",
        repo_root=tmp_path,
    )

    assert errors == []
    assert commands[0]["gate"] == "compile"
    assert commands[0]["command"] == "uv run python -m compileall app tests main.py"
    assert commands[0]["docker_command"] == [
        "docker",
        "run",
        "--rm",
        "-v",
        f"{Path(tmp_path).resolve()}:/workspace",
        "-w",
        "/workspace",
        "sandbox-image",
        "bash",
        "-lc",
        "uv run python -m compileall app tests main.py",
    ]


def test_execute_runner_sandbox_commands_dry_run_does_not_run_docker(tmp_path):
    def fake_runner(**_kwargs):
        raise AssertionError("docker should not run in dry-run")

    result = execute_runner_sandbox_commands(
        ["compile"],
        repo_root=tmp_path,
        dry_run=True,
        command_runner=fake_runner,
    )

    assert result["dry_run"] is True
    assert result["executed"] is False
    assert result["deliverable"] is False
    assert result["command_results"] == []
    assert result["docker_commands"][0]["gate"] == "compile"


def test_execute_runner_sandbox_commands_runs_docker_when_apply_enabled(tmp_path):
    calls = []

    def fake_runner(command, **_kwargs):
        calls.append(command)
        return FakeCompletedProcess(returncode=0, stdout="ok")

    result = execute_runner_sandbox_commands(
        ["compile"],
        repo_root=tmp_path,
        dry_run=False,
        command_runner=fake_runner,
    )

    assert result["dry_run"] is False
    assert result["executed"] is True
    assert result["deliverable"] is True
    assert result["command_results"][0]["status"] == "passed"
    assert calls == [result["docker_commands"][0]["docker_command"]]


def test_execute_runner_sandbox_commands_rejects_manual_gate(tmp_path):
    with pytest.raises(ValueError, match="not executable"):
        execute_runner_sandbox_commands(
            ["manual_validation"],
            repo_root=tmp_path,
            dry_run=True,
        )
