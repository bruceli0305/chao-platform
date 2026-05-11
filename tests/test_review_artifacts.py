from app.chao.services import review_artifacts


def test_build_review_artifact_markdown_contains_review_sections():
    content = review_artifacts.build_review_artifact_markdown(
        task={
            "task_code": "TASK-TEST-REVIEW",
            "title": "新增数据库迁移",
            "raw_request": "新增 users.status 字段",
            "task_level": "L3",
            "status": "DESIGNING",
        },
        design_artifact_uri=".ai-agents/records/designs/TASK-TEST-REVIEW-design.md",
    )

    assert "# TASK-TEST-REVIEW - 门下省审核" in content
    assert "| 当前状态 | DESIGNING |" in content
    assert "## 审核检查项" in content
    assert "PENDING_REVIEW" in content
    assert "不得写入 Secret" in content


def test_save_review_artifact_writes_expected_path(tmp_path, monkeypatch):
    monkeypatch.setattr(review_artifacts, "REVIEW_RECORDS_DIR", tmp_path)

    path = review_artifacts.save_review_artifact(
        task={
            "task_code": "TASK-TEST-REVIEW",
            "title": "新增数据库迁移",
            "raw_request": "新增 users.status 字段",
            "task_level": "L3",
            "status": "DESIGNING",
        },
        design_artifact_uri=".ai-agents/records/designs/TASK-TEST-REVIEW-design.md",
    )

    assert path == tmp_path / "TASK-TEST-REVIEW-review.md"
    assert path.read_text(encoding="utf-8").startswith("# TASK-TEST-REVIEW - 门下省审核")
