from app.chao import runner_artifacts
from app.chao.runner_policy import build_runner_branch_plan


def test_build_patch_artifact_markdown_contains_runner_evidence():
    task = {
        "task_code": "TASK-TEST-PATCH",
        "title": "修复文案",
        "task_level": "L1",
        "status": "DELIVERED",
        "implementation_result": {
            "summary": "MVP 阶段暂不自动改代码，只生成执行计划。",
            "changed_files": ["app/chao/nodes/gongbu.py"],
            "risk": "未实际修改代码。",
        },
        "validation_result": {
            "deliverable": True,
            "checks": ["manual_validation"],
        },
    }
    branch_plan = build_runner_branch_plan(
        task_code="TASK-TEST-PATCH",
        title="修复文案",
        task_level="L1",
    )

    content = runner_artifacts.build_patch_artifact_markdown(task, branch_plan)

    assert "# TASK-TEST-PATCH - Runner Patch Artifact" in content
    assert "app/chao/nodes/gongbu.py" in content
    assert "当前 MVP 未生成真实 diff patch" in content
    assert "刑部验证结果" in content


def test_save_patch_artifact_writes_expected_path(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_artifacts, "PATCH_RECORDS_DIR", tmp_path)

    path = runner_artifacts.save_patch_artifact(
        {
            "task_code": "TASK-TEST-PATCH",
            "title": "修复文案",
            "task_level": "L1",
            "status": "DELIVERED",
            "implementation_result": {
                "summary": "MVP 阶段暂不自动改代码，只生成执行计划。",
                "changed_files": [],
                "risk": "未实际修改代码。",
            },
            "validation_result": {
                "deliverable": True,
                "checks": ["manual_validation"],
            },
        }
    )

    assert path == tmp_path / "TASK-TEST-PATCH-patch.md"
    assert path.read_text(encoding="utf-8").startswith("# TASK-TEST-PATCH - Runner Patch Artifact")


def test_build_failure_feedback_artifact_markdown_contains_failed_gates():
    task = {
        "task_code": "TASK-TEST-FAILURE",
        "title": "修复文案",
        "task_level": "L1",
        "status": "VALIDATION_FAILED",
        "implementation_result": {
            "summary": "MVP 阶段暂不自动改代码，只生成执行计划。",
            "changed_files": ["app/chao/nodes/gongbu.py"],
            "risk": "未实际修改代码。",
        },
        "validation_result": {
            "deliverable": False,
            "command_results": [
                {
                    "gate": "lint",
                    "command": "uv run ruff check app tests main.py",
                    "status": "failed",
                    "exit_code": 1,
                    "output_summary": "lint failed",
                }
            ],
        },
    }
    branch_plan = build_runner_branch_plan(
        task_code="TASK-TEST-FAILURE",
        title="修复文案",
        task_level="L1",
    )

    content = runner_artifacts.build_failure_feedback_artifact_markdown(
        task,
        branch_plan,
    )

    assert "# TASK-TEST-FAILURE - Runner Failure Feedback" in content
    assert "lint failed" in content
    assert "当前任务禁止交付" in content
    assert "工部必须根据失败 gate" in content


def test_save_failure_feedback_artifact_writes_expected_path(tmp_path, monkeypatch):
    monkeypatch.setattr(runner_artifacts, "FAILURE_RECORDS_DIR", tmp_path)

    path = runner_artifacts.save_failure_feedback_artifact(
        {
            "task_code": "TASK-TEST-FAILURE",
            "title": "修复文案",
            "task_level": "L1",
            "status": "VALIDATION_FAILED",
            "implementation_result": {
                "summary": "MVP 阶段暂不自动改代码，只生成执行计划。",
                "changed_files": [],
                "risk": "未实际修改代码。",
            },
            "validation_result": {
                "deliverable": False,
                "command_results": [],
            },
        }
    )

    assert path == tmp_path / "TASK-TEST-FAILURE-failure-feedback.md"
    assert path.read_text(encoding="utf-8").startswith(
        "# TASK-TEST-FAILURE - Runner Failure Feedback"
    )
