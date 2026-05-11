from app.chao.services import bingbu_artifacts


def test_build_bingbu_artifact_markdown_contains_deployment_sections():
    content = bingbu_artifacts.build_bingbu_artifact_markdown(
        task={
            "task_code": "TASK-TEST-BINGBU",
            "title": "新增数据库迁移",
            "raw_request": "新增 users.status 字段",
            "task_level": "L3",
            "status": "DESIGNING",
        },
        design_artifact_uri=".ai-agents/records/designs/TASK-TEST-BINGBU-design.md",
        review_artifact_uri=".ai-agents/records/reviews/TASK-TEST-BINGBU-review.md",
        hubu_artifact_uri=".ai-agents/records/hubu/TASK-TEST-BINGBU-hubu.md",
    )

    assert "# TASK-TEST-BINGBU - 兵部审查" in content
    assert "| 当前状态 | DESIGNING |" in content
    assert "## 部署与 CI 检查项" in content
    assert "## Rollback 检查项" in content
    assert "PENDING_BINGBU_REVIEW" in content
    assert "不得写入 Secret" in content


def test_save_bingbu_artifact_writes_expected_path(tmp_path, monkeypatch):
    monkeypatch.setattr(bingbu_artifacts, "BINGBU_RECORDS_DIR", tmp_path)

    path = bingbu_artifacts.save_bingbu_artifact(
        task={
            "task_code": "TASK-TEST-BINGBU",
            "title": "新增数据库迁移",
            "raw_request": "新增 users.status 字段",
            "task_level": "L3",
            "status": "DESIGNING",
        },
        design_artifact_uri=".ai-agents/records/designs/TASK-TEST-BINGBU-design.md",
        review_artifact_uri=".ai-agents/records/reviews/TASK-TEST-BINGBU-review.md",
        hubu_artifact_uri=".ai-agents/records/hubu/TASK-TEST-BINGBU-hubu.md",
    )

    assert path == tmp_path / "TASK-TEST-BINGBU-bingbu.md"
    assert path.read_text(encoding="utf-8").startswith(
        "# TASK-TEST-BINGBU - 兵部审查"
    )
