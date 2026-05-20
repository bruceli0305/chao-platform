from scripts import record_github_delivery


def test_extract_task_code_from_pull_request_body():
    assert (
        record_github_delivery.extract_task_code(
            {
                "pull_request": {
                    "body": "Task Code: TASK-20260511-120000-123456",
                }
            }
        )
        == "TASK-20260511-120000-123456"
    )


def test_extract_task_code_from_issue_title():
    assert (
        record_github_delivery.extract_task_code(
            {
                "issue": {
                    "title": "Follow up TASK-20260511-130000-654321",
                    "body": "",
                }
            }
        )
        == "TASK-20260511-130000-654321"
    )


def test_extract_task_code_from_push_commit_message():
    assert (
        record_github_delivery.extract_task_code(
            {
                "head_commit": {
                    "message": "Complete TASK-20260511-120000",
                }
            }
        )
        == "TASK-20260511-120000"
    )


def test_extract_task_code_from_workflow_run_commit_message():
    assert (
        record_github_delivery.extract_task_code(
            {
                "workflow_run": {
                    "display_title": "CI",
                    "head_commit": {
                        "message": "Validate TASK-20260511-140000",
                    },
                }
            }
        )
        == "TASK-20260511-140000"
    )


def test_extract_task_code_from_workflow_run_without_head_commit():
    assert (
        record_github_delivery.extract_task_code(
            {
                "workflow_run": {
                    "display_title": "CI TASK-20260511-150000",
                    "head_commit": None,
                }
            }
        )
        == "TASK-20260511-150000"
    )


def test_build_delivery_links_for_issue():
    links = record_github_delivery.build_delivery_links(
        {
            "action": "opened",
            "issue": {
                "number": 7,
                "html_url": "https://github.com/example/repo/issues/7",
                "title": "Follow up",
                "state": "open",
                "labels": [{"name": "chao"}],
            },
        },
        {
            "GITHUB_REPOSITORY": "example/repo",
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_SHA": "abc123",
            "GITHUB_RUN_ID": "99",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW": "Task sync",
            "GITHUB_JOB": "github-task-sync",
        },
    )

    assert [link["link_type"] for link in links] == ["issue", "commit", "ci_run"]
    assert links[0]["external_id"] == "7"
    assert links[0]["metadata"]["action"] == "opened"
    assert links[0]["metadata"]["labels"] == ["chao"]


def test_build_delivery_links_for_pull_request():
    links = record_github_delivery.build_delivery_links(
        {
            "pull_request": {
                "number": 42,
                "html_url": "https://github.com/example/repo/pull/42",
                "title": "Bind task",
                "state": "closed",
                "merged": True,
                "base": {"ref": "main"},
                "head": {"ref": "feature/task"},
            }
        },
        {
            "GITHUB_REPOSITORY": "example/repo",
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_SHA": "abc123",
            "GITHUB_RUN_ID": "99",
            "GITHUB_REF": "refs/pull/42/merge",
            "GITHUB_WORKFLOW": "CI",
            "GITHUB_JOB": "python-gates",
        },
    )

    assert [link["link_type"] for link in links] == ["pull_request", "commit", "ci_run"]
    assert links[0]["status"] == "merged"
    assert links[1]["url"] == "https://github.com/example/repo/commit/abc123"
    assert links[2]["url"] == "https://github.com/example/repo/actions/runs/99"


def test_build_delivery_links_for_workflow_run():
    links = record_github_delivery.build_delivery_links(
        {
            "workflow_run": {
                "id": 123,
                "html_url": "https://github.com/example/repo/actions/runs/123",
                "name": "CI",
                "conclusion": "success",
                "event": "pull_request",
                "head_branch": "feature/task",
                "head_sha": "def456",
            }
        },
        {
            "GITHUB_REPOSITORY": "example/repo",
            "GITHUB_SERVER_URL": "https://github.com",
            "GITHUB_RUN_ID": "99",
            "GITHUB_REF": "refs/heads/main",
            "GITHUB_WORKFLOW": "Task sync",
            "GITHUB_JOB": "github-task-sync",
        },
    )

    assert [link["link_type"] for link in links] == ["ci_run", "commit", "ci_run"]
    assert links[0]["external_id"] == "123"
    assert links[0]["status"] == "success"
    assert links[1]["external_id"] == "def456"


def test_record_delivery_context_writes_links_historian_and_event(monkeypatch):
    calls = {
        "links": [],
        "historian": [],
        "events": [],
    }
    monkeypatch.setattr(
        record_github_delivery,
        "get_task_detail",
        lambda _task_code: {"id": "task-1", "status": "DELIVERED"},
    )
    monkeypatch.setattr(
        record_github_delivery,
        "record_github_link",
        lambda **kwargs: calls["links"].append(kwargs),
    )
    monkeypatch.setattr(
        record_github_delivery,
        "record_historian_record",
        lambda **kwargs: calls["historian"].append(kwargs),
    )
    monkeypatch.setattr(
        record_github_delivery,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )

    recorded = record_github_delivery.record_delivery_context(
        task_code="TASK-20260511-120000",
        links=[
            {
                "link_type": "commit",
                "external_id": "abc123",
                "url": "https://github.com/example/repo/commit/abc123",
            }
        ],
        created_by="ci",
    )

    assert recorded is True
    assert calls["links"][0]["link_type"] == "commit"
    assert calls["historian"][0]["record_type"] == "github_delivery"
    assert calls["events"][0]["event_type"] == "github_delivery_recorded"


def test_record_delivery_context_skips_missing_task_when_allowed(monkeypatch):
    monkeypatch.setattr(record_github_delivery, "get_task_detail", lambda _task_code: None)

    assert (
        record_github_delivery.record_delivery_context(
            task_code="TASK-20260511-120000",
            links=[],
            created_by="ci",
            allow_missing_task=True,
        )
        is False
    )
