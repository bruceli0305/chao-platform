from app.chao.services import hubu_artifacts


def test_build_hubu_artifact_markdown_contains_data_review_sections():
    content = hubu_artifacts.build_hubu_artifact_markdown(
        task={
            "task_code": "TASK-TEST-HUBU",
            "title": "新增数据库迁移",
            "raw_request": "新增 users.status 字段",
            "task_level": "L3",
            "status": "DESIGNING",
        },
        design_artifact_uri=".ai-agents/records/designs/TASK-TEST-HUBU-design.md",
        review_artifact_uri=".ai-agents/records/reviews/TASK-TEST-HUBU-review.md",
    )

    assert "# TASK-TEST-HUBU - 户部审查" in content
    assert "| 当前状态 | DESIGNING |" in content
    assert "## 数据边界检查项" in content
    assert "## 依赖与 Secret 检查项" in content
    assert "PENDING_HUBU_REVIEW" in content
    assert "不得写入 Secret" in content


def test_save_hubu_artifact_writes_expected_path(tmp_path, monkeypatch):
    monkeypatch.setattr(hubu_artifacts, "HUBU_RECORDS_DIR", tmp_path)

    path = hubu_artifacts.save_hubu_artifact(
        task={
            "task_code": "TASK-TEST-HUBU",
            "title": "新增数据库迁移",
            "raw_request": "新增 users.status 字段",
            "task_level": "L3",
            "status": "DESIGNING",
        },
        design_artifact_uri=".ai-agents/records/designs/TASK-TEST-HUBU-design.md",
        review_artifact_uri=".ai-agents/records/reviews/TASK-TEST-HUBU-review.md",
    )

    assert path == tmp_path / "TASK-TEST-HUBU-hubu.md"
    assert path.read_text(encoding="utf-8").startswith(
        "# TASK-TEST-HUBU - 户部审查"
    )
