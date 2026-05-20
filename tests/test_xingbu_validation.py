from app.chao.nodes import xingbu


def test_xingbu_records_runner_validation_result():
    result = xingbu.xingbu_validate(
        {
            "task_id": "task-1",
            "task_code": "TASK-TEST",
            "title": "修复文案",
            "raw_request": "把首页标题从系统管理改成项目管理",
            "task_level": "L1",
            "required_gates": ["manual_validation"],
            "status": "IMPLEMENTING",
        }
    )

    assert result["status"] == "VALIDATING"
    assert result["validation_result"]["deliverable"] is True
    assert result["validation_result"]["plan"][0]["gate"] == "manual_validation"


def test_xingbu_prefers_skill_execution_plan_combined_gates():
    result = xingbu.xingbu_validate(
        {
            "task_id": "task-1",
            "task_code": "TASK-TEST",
            "title": "淇鏂囨",
            "raw_request": "鎶婇椤垫爣棰樹粠绯荤粺绠＄悊鏀规垚椤圭洰绠＄悊",
            "task_level": "L1",
            "required_gates": ["manual_validation"],
            "skill_execution_plan": {
                "status": "ready",
                "combined_gates": ["manual_validation", "lint", "test"],
                "skills": [],
            },
            "status": "IMPLEMENTING",
        }
    )

    assert result["validation_result"]["checks"] == ["manual_validation", "lint", "test"]
    assert [step["gate"] for step in result["validation_result"]["plan"]] == [
        "manual_validation",
        "lint",
        "test",
    ]


def test_xingbu_marks_failed_runner_validation_for_feedback(monkeypatch):
    failed_result = {
        "quality": "验证失败",
        "checks": ["lint"],
        "plan": [],
        "command_results": [
            {
                "gate": "lint",
                "command": "uv run ruff check app tests main.py",
                "status": "failed",
                "exit_code": 1,
                "output_summary": "lint failed",
            }
        ],
        "deliverable": False,
        "note": "刑部验证失败，禁止进入交付。",
    }

    monkeypatch.setattr(
        xingbu,
        "build_runner_validation_result",
        lambda gates: failed_result,
    )

    result = xingbu.xingbu_validate(
        {
            "task_id": "task-1",
            "task_code": "TASK-TEST",
            "title": "修复文案",
            "raw_request": "把首页标题从系统管理改成项目管理",
            "task_level": "L1",
            "required_gates": ["lint"],
            "status": "IMPLEMENTING",
        }
    )

    assert result["status"] == "VALIDATION_FAILED"
    assert result["validation_result"]["deliverable"] is False
    assert result["validation_result"]["command_results"][0]["gate"] == "lint"
