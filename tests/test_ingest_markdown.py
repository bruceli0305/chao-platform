from scripts.ingest_markdown import (
    build_dry_run_report,
    build_report,
    classify_source,
    collect_candidates,
    summarize_candidate,
)


def test_classify_source():
    assert classify_source("README.md") == ("documentation", "D0", False)
    assert classify_source("AGENTS.md") == ("agent_rule", "D1", True)
    assert classify_source(".ai-agents/router/task-router.md") == ("agent_rule", "D1", True)
    assert classify_source(".ai-agents/records/tasks/TASK-1.md") == (
        "historian_summary",
        "D1",
        True,
    )
    assert classify_source("docs/11-data-storage-boundary-v3.md") == (
        "documentation",
        "D1",
        True,
    )


def test_build_dry_run_report_filters_and_hashes_candidates(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / ".ai-agents" / "router").mkdir(parents=True)

    (tmp_path / "README.md").write_text("Project overview", encoding="utf-8")
    (tmp_path / "docs" / "policy.md").write_text("Policy", encoding="utf-8")
    (tmp_path / ".ai-agents" / "router" / "task-router.md").write_text(
        "Router",
        encoding="utf-8",
    )
    (tmp_path / "data" / "leak.md").write_text("forbidden", encoding="utf-8")
    (tmp_path / "app.py").write_text("print('ignored')", encoding="utf-8")

    report = build_dry_run_report(
        tmp_path,
        [
            "README.md",
            "docs/policy.md",
            ".ai-agents/router/task-router.md",
            "data/leak.md",
            "app.py",
        ],
    )

    assert report["mode"] == "dry_run"
    assert report["candidate_count"] == 3
    assert report["rejected_count"] == 1
    assert report["rejected"] == [{"source_uri": "data/leak.md", "reason": "forbidden_path"}]
    assert [candidate["source_uri"] for candidate in report["candidates"]] == [
        "README.md",
        "docs/policy.md",
        ".ai-agents/router/task-router.md",
    ]
    assert all(candidate["source_hash"] for candidate in report["candidates"])
    assert all("content" not in candidate for candidate in report["candidates"])


def test_collect_candidates_keeps_content_for_write(tmp_path):
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "policy.md").write_text("Policy", encoding="utf-8")

    candidates, rejected = collect_candidates(tmp_path, ["docs/policy.md"])

    assert rejected == []
    assert candidates[0]["source_uri"] == "docs/policy.md"
    assert candidates[0]["content"] == "Policy"


def test_summarize_candidate_removes_content():
    candidate = {
        "source_uri": "README.md",
        "content": "full content",
        "source_hash": "abc123",
    }

    assert summarize_candidate(candidate) == {
        "source_uri": "README.md",
        "source_hash": "abc123",
    }


def test_build_report_omits_candidate_content():
    report = build_report(
        "dry_run",
        [{"source_uri": "README.md", "content": "full content"}],
        [],
    )

    assert report == {
        "mode": "dry_run",
        "candidate_count": 1,
        "rejected_count": 0,
        "candidates": [{"source_uri": "README.md"}],
        "rejected": [],
    }
