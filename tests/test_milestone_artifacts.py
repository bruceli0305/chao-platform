from app.chao.services import milestone_artifacts


def test_build_milestone_artifact_markdown_contains_l4_boundaries():
    content = milestone_artifacts.build_milestone_artifact_markdown(
        {
            "task_code": "TASK-TEST-L4",
            "title": "平台级路线图",
            "raw_request": "规划完整平台路线图，拆解成多个子任务",
            "task_level": "L4",
            "status": "NEED_CONFIRMATION",
        }
    )

    assert "# TASK-TEST-L4 - L4 里程碑规划" in content
    assert "| 任务等级 | L4 |" in content
    assert "只生成里程碑规划，不直接进入工部执行" in content
    assert "MILESTONE_ONLY" in content


def test_save_milestone_artifact_writes_expected_path(tmp_path, monkeypatch):
    monkeypatch.setattr(milestone_artifacts, "MILESTONE_RECORDS_DIR", tmp_path)

    path = milestone_artifacts.save_milestone_artifact(
        {
            "task_code": "TASK-TEST-L4",
            "title": "平台级路线图",
            "raw_request": "规划完整平台路线图，拆解成多个子任务",
            "task_level": "L4",
            "status": "NEED_CONFIRMATION",
        }
    )

    assert path == tmp_path / "TASK-TEST-L4-milestones.md"
    assert path.read_text(encoding="utf-8").startswith(
        "# TASK-TEST-L4 - L4 里程碑规划"
    )
