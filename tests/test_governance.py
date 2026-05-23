import pytest

from app.chao.governance import build_governance_check_result


def _task(*, task_level="L3", artifacts=None):
    return {
        "task_code": "TASK-1",
        "task_level": task_level,
        "artifacts": artifacts or [],
    }


def test_menxia_governance_passes_when_design_artifact_exists():
    result = build_governance_check_result(
        _task(artifacts=[{"artifact_type": "l3_design_plan", "artifact_uri": "design.md"}]),
        agent_name="menxia",
    )

    assert result["status"] == "passed"
    assert result["deliverable"] is True
    assert result["missing_artifacts"] == []


def test_hubu_governance_blocks_until_menxia_review_exists():
    result = build_governance_check_result(
        _task(artifacts=[{"artifact_type": "l3_design_plan", "artifact_uri": "design.md"}]),
        agent_name="hubu",
    )

    assert result["status"] == "blocked"
    assert result["deliverable"] is False
    assert result["missing_artifacts"] == ["l3_menxia_review"]


def test_bingbu_governance_requires_hubu_review():
    result = build_governance_check_result(
        _task(
            artifacts=[
                {"artifact_type": "l3_design_plan", "artifact_uri": "design.md"},
                {"artifact_type": "l3_menxia_review", "artifact_uri": "review.md"},
            ]
        ),
        agent_name="bingbu",
    )

    assert result["status"] == "blocked"
    assert result["missing_artifacts"] == ["l3_hubu_review"]


def test_governance_is_not_required_for_l2_tasks():
    result = build_governance_check_result(_task(task_level="L2"), agent_name="hubu")

    assert result["status"] == "not_required"
    assert result["deliverable"] is True


def test_governance_rejects_unknown_agent():
    with pytest.raises(ValueError, match="unsupported governance agent"):
        build_governance_check_result(_task(), agent_name="gongbu")
