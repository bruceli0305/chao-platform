from scripts import data_boundary_check


def test_normalize_repo_path_preserves_dotfiles_and_dotdirs():
    assert data_boundary_check.normalize_repo_path("./.ai-agents/router/task-router.md") == (
        ".ai-agents/router/task-router.md"
    )
    assert data_boundary_check.normalize_repo_path(".env.local") == ".env.local"
    assert data_boundary_check.normalize_repo_path(r"docs\11-data-storage-boundary-v3.md") == (
        "docs/11-data-storage-boundary-v3.md"
    )


def test_ingest_policy_allows_only_whitelisted_sources():
    assert data_boundary_check.is_allowed_ingest_source("AGENTS.md") is True
    assert data_boundary_check.is_allowed_ingest_source("README.md") is True
    assert data_boundary_check.is_allowed_ingest_source("CHANGELOG-v3.md") is True
    assert data_boundary_check.is_allowed_ingest_source("docs/11-data-storage-boundary-v3.md")
    assert data_boundary_check.is_allowed_ingest_source(".ai-agents/router/task-router.md")
    assert data_boundary_check.is_allowed_ingest_source("app/chao/cli.py") is False
    assert data_boundary_check.is_allowed_ingest_source("docs/diagram.png") is False


def test_ingest_policy_blocks_forbidden_paths():
    assert data_boundary_check.is_allowed_ingest_source(".env") is False
    assert data_boundary_check.is_allowed_ingest_source(".env.example") is False
    assert data_boundary_check.is_allowed_ingest_source(".env.local") is False
    assert data_boundary_check.is_allowed_ingest_source("data/export.md") is False
    assert data_boundary_check.is_allowed_ingest_source("logs/run.md") is False
    assert data_boundary_check.is_allowed_ingest_source("node_modules/pkg/readme.md") is False
    assert data_boundary_check.is_allowed_ingest_source("dist/report.md") is False
    assert data_boundary_check.is_allowed_ingest_source("build/report.md") is False


def test_ingest_forbidden_tracked_paths_are_reported():
    errors = data_boundary_check.check_ingest_forbidden_tracked_paths(
        ["docs/ok.md", ".env.example", "data/export.md", ".env.local"]
    )

    assert errors == [
        "禁止被 ingest 的路径被 Git 跟踪：data/export.md",
        "禁止被 ingest 的路径被 Git 跟踪：.env.local",
    ]


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
