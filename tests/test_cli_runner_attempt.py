from typer.testing import CliRunner

from app.chao import cli


def _task():
    return {
        "id": "task-1",
        "task_code": "TASK-1",
        "title": "Patch demo",
        "task_level": "L1",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "none"},
    }


def _task_with_skill_gates():
    task = _task()
    task["skill_execution_plan"] = {
        "status": "ready",
        "combined_gates": ["manual_validation", "lint", "test"],
        "skills": [],
    }
    return task


def _execution_result(applied: bool):
    return {
        "summary": "Applied 1 controlled text patch operation(s).",
        "changed_files": ["app/chao/demo.txt"],
        "operations": [],
        "applied": applied,
        "dry_run": not applied,
    }


def _validation_result(deliverable: bool):
    return {
        "quality": "deliverable" if deliverable else "failed",
        "checks": ["compile"],
        "plan": [],
        "command_results": [
            {
                "gate": "compile",
                "command": "uv run python -m compileall app tests main.py",
                "status": "passed" if deliverable else "failed",
                "exit_code": 0 if deliverable else 1,
                "output_summary": "ok" if deliverable else "failed",
            }
        ],
        "deliverable": deliverable,
        "note": "passed" if deliverable else "failed",
    }


def test_runner_attempt_apply_records_patch_artifact(monkeypatch, tmp_path):
    calls = {
        "artifacts": [],
        "data_assets": [],
        "events": [],
        "tool_calls": [],
        "status_updates": [],
    }
    artifact_path = tmp_path / "TASK-1-patch.md"
    artifact_path.write_text("patch", encoding="utf-8")

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(
        cli,
        "apply_text_patch_operations",
        lambda operations, dry_run=True: _execution_result(applied=not dry_run),
    )
    monkeypatch.setattr(
        cli,
        "execute_runner_validation_commands",
        lambda gates, timeout_seconds=120: _validation_result(deliverable=True),
    )
    monkeypatch.setattr(cli, "save_patch_artifact", lambda task: artifact_path)
    monkeypatch.setattr(cli, "record_artifact", lambda **kwargs: calls["artifacts"].append(kwargs))
    monkeypatch.setattr(
        cli,
        "record_data_asset",
        lambda **kwargs: calls["data_assets"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "update_task_status",
        lambda task_id, status: calls["status_updates"].append((task_id, status)),
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-attempt",
            "TASK-1",
            "app/chao/demo.txt",
            "--old-text",
            "old",
            "--new-text",
            "new",
            "--gate",
            "compile",
            "--apply",
        ],
    )

    assert result.exit_code == 0
    assert calls["artifacts"][0]["artifact_type"] == "runner_patch"
    assert calls["data_assets"][0]["asset_type"] == "runner_patch"
    assert calls["events"][0]["event_type"] == "runner_attempt_delivered"
    assert calls["status_updates"] == [("task-1", "DELIVERED")]
    assert [call["tool_name"] for call in calls["tool_calls"]] == [
        "cli.runner_patch",
        "cli.runner_validate",
    ]
    assert '"artifact_type": "runner_patch"' in result.output


def test_runner_attempt_apply_records_failure_feedback(monkeypatch, tmp_path):
    calls = {
        "artifacts": [],
        "data_assets": [],
        "events": [],
        "tool_calls": [],
        "status_updates": [],
    }
    artifact_path = tmp_path / "TASK-1-failure-feedback.md"
    artifact_path.write_text("failure", encoding="utf-8")

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(
        cli,
        "apply_text_patch_operations",
        lambda operations, dry_run=True: _execution_result(applied=not dry_run),
    )
    monkeypatch.setattr(
        cli,
        "execute_runner_validation_commands",
        lambda gates, timeout_seconds=120: _validation_result(deliverable=False),
    )
    monkeypatch.setattr(cli, "save_failure_feedback_artifact", lambda task: artifact_path)
    monkeypatch.setattr(cli, "record_artifact", lambda **kwargs: calls["artifacts"].append(kwargs))
    monkeypatch.setattr(
        cli,
        "record_data_asset",
        lambda **kwargs: calls["data_assets"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "update_task_status",
        lambda task_id, status: calls["status_updates"].append((task_id, status)),
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-attempt",
            "TASK-1",
            "app/chao/demo.txt",
            "--old-text",
            "old",
            "--new-text",
            "new",
            "--gate",
            "compile",
            "--apply",
        ],
    )

    assert result.exit_code == 1
    assert calls["artifacts"][0]["artifact_type"] == "runner_failure_feedback"
    assert calls["data_assets"][0]["asset_type"] == "runner_failure_feedback"
    assert calls["events"][0]["event_type"] == "runner_attempt_failed"
    assert calls["status_updates"] == [("task-1", "VALIDATION_FAILED")]
    assert calls["tool_calls"][1]["result_status"] == "failed"


def test_runner_attempt_dry_run_skips_artifact_recording(monkeypatch):
    calls = {
        "artifacts": [],
        "data_assets": [],
        "events": [],
        "tool_calls": [],
        "status_updates": [],
    }

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task())
    monkeypatch.setattr(
        cli,
        "apply_text_patch_operations",
        lambda operations, dry_run=True: _execution_result(applied=not dry_run),
    )
    monkeypatch.setattr(
        cli,
        "execute_runner_validation_commands",
        lambda gates, timeout_seconds=120: _validation_result(deliverable=True),
    )
    monkeypatch.setattr(cli, "record_artifact", lambda **kwargs: calls["artifacts"].append(kwargs))
    monkeypatch.setattr(
        cli,
        "record_data_asset",
        lambda **kwargs: calls["data_assets"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "update_task_status",
        lambda task_id, status: calls["status_updates"].append((task_id, status)),
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-attempt",
            "TASK-1",
            "app/chao/demo.txt",
            "--old-text",
            "old",
            "--new-text",
            "new",
            "--gate",
            "compile",
        ],
    )

    assert result.exit_code == 0
    assert calls["artifacts"] == []
    assert calls["data_assets"] == []
    assert calls["status_updates"] == []
    assert calls["events"][0]["to_status"] == "DELIVERED"
    assert '"artifact_type": null' in result.output


def test_runner_attempt_uses_skill_execution_plan_when_gate_omitted(monkeypatch):
    calls = {
        "events": [],
        "tool_calls": [],
        "validation_gates": [],
    }

    def execute_validation(gates, timeout_seconds=120):
        calls["validation_gates"].extend(gates)
        return _validation_result(deliverable=True)

    monkeypatch.setattr(cli, "get_task_detail", lambda _task_code: _task_with_skill_gates())
    monkeypatch.setattr(
        cli,
        "apply_text_patch_operations",
        lambda operations, dry_run=True: _execution_result(applied=not dry_run),
    )
    monkeypatch.setattr(cli, "execute_runner_validation_commands", execute_validation)
    monkeypatch.setattr(
        cli,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        cli,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )

    result = CliRunner().invoke(
        cli.app,
        [
            "runner-attempt",
            "TASK-1",
            "app/chao/demo.txt",
            "--old-text",
            "old",
            "--new-text",
            "new",
        ],
    )

    assert result.exit_code == 0
    assert calls["validation_gates"] == ["manual_validation", "lint", "test"]
    assert calls["events"][0]["summary"] == (
        "Runner attempt dry-run: manual_validation, lint, test"
    )
    assert calls["tool_calls"][1]["arguments_summary"] == (
        "task_code=TASK-1; gates=['manual_validation', 'lint', 'test']"
    )
