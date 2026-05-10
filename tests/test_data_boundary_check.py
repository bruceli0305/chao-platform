from scripts import data_boundary_check


def test_task_markdown_records_reject_secret_pattern(tmp_path, monkeypatch):
    records_dir = tmp_path / ".ai-agents" / "records" / "tasks"
    records_dir.mkdir(parents=True)
    task_record = records_dir / "TASK-20260510-TEST.md"
    task_record.write_text("api" + '_key="1234567890abcdef"', encoding="utf-8")

    monkeypatch.setattr(data_boundary_check, "ROOT", tmp_path)
    monkeypatch.setattr(data_boundary_check, "TASK_RECORDS_DIR", records_dir)

    errors = data_boundary_check.check_task_markdown_records()

    assert len(errors) == 1
    assert errors[0].startswith("史官任务记录疑似敏感信息：")
    assert "TASK-20260510-TEST.md" in errors[0]


def test_task_markdown_records_accept_clean_content(tmp_path, monkeypatch):
    records_dir = tmp_path / ".ai-agents" / "records" / "tasks"
    records_dir.mkdir(parents=True)
    task_record = records_dir / "TASK-20260510-TEST.md"
    task_record.write_text("只记录脱敏后的任务摘要。", encoding="utf-8")

    monkeypatch.setattr(data_boundary_check, "ROOT", tmp_path)
    monkeypatch.setattr(data_boundary_check, "TASK_RECORDS_DIR", records_dir)

    assert data_boundary_check.check_task_markdown_records() == []
