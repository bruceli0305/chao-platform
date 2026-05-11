from app.chao.services import design_artifacts


def test_build_design_artifact_markdown_contains_governance_sections():
    content = design_artifacts.build_design_artifact_markdown(
        task={
            "task_code": "TASK-TEST-DESIGN",
            "title": "新增数据库迁移",
            "raw_request": "新增 users.status 字段",
            "task_level": "L3",
            "status": "DESIGNING",
        },
        confirmed_by="lee",
        note="确认执行",
    )

    assert "# TASK-TEST-DESIGN - 中书省方案" in content
    assert "| 当前状态 | DESIGNING |" in content
    assert "## 设计检查项" in content
    assert "## 后续治理" in content
    assert "不得在本文件写入 Secret" in content


def test_save_design_artifact_writes_expected_path(tmp_path, monkeypatch):
    monkeypatch.setattr(design_artifacts, "DESIGN_RECORDS_DIR", tmp_path)

    path = design_artifacts.save_design_artifact(
        task={
            "task_code": "TASK-TEST-DESIGN",
            "title": "新增数据库迁移",
            "raw_request": "新增 users.status 字段",
            "task_level": "L3",
            "status": "DESIGNING",
        },
        confirmed_by="lee",
        note="确认执行",
    )

    assert path == tmp_path / "TASK-TEST-DESIGN-design.md"
    assert path.read_text(encoding="utf-8").startswith("# TASK-TEST-DESIGN - 中书省方案")
