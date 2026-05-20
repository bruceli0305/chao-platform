from http import HTTPStatus

from app.chao import web_console


def test_build_console_index_html_contains_read_only_ui():
    html = web_console.build_console_index_html()

    assert "<title>Chao Console</title>" in html
    assert "record-limit" in html
    assert "Refresh" in html
    assert "Console sections" in html
    assert "#overview-section" in html
    assert "#task-detail-section" in html
    assert "selectedLimit" in html
    assert "task-search" in html
    assert "status-filter" in html
    assert "level-filter" in html
    assert "selectedTaskFilters" in html
    assert "buildOverviewQuery" in html
    assert "updateFilterUrl" in html
    assert "hydrateFiltersFromUrl" in html
    assert "renderNotice" in html
    assert "renderPanelError" in html
    assert "Console load failed" in html
    assert "/api/console?${buildOverviewQuery(limit, filters)}" in html
    assert "/api/console/approvals?limit=${limit}" in html
    assert "/api/console/audit?limit=${limit}" in html
    assert "/api/console/github-sync?limit=${limit}" in html
    assert "/api/console/gates?limit=${limit}" in html
    assert "/api/console/risks?limit=${limit}" in html
    assert "/api/console/tasks/" in html
    assert "Approval Queue" in html
    assert "GitHub Sync" in html
    assert "Data Boundary Audit" in html
    assert "Audit Trail" in html
    assert "Recent Tool Calls" in html
    assert "Recent Artifacts" in html
    assert "Recent Gate Results" in html
    assert "Recent Tasks" in html
    assert "risk-details" in html
    assert "gate-details" in html
    assert "renderRiskDetails" in html
    assert "renderGateDetails" in html
    assert "renderGitHubSyncDetails" in html
    assert "renderAuditTrail" in html
    assert "task-summary" in html
    assert "renderTaskSummary" in html
    assert "task-detail-tables" in html
    assert "renderTaskDetailTables" in html
    assert "Task Tool Calls" in html
    assert "Task Gate Results" in html
    assert "Task Skill Usage" in html
    assert "Task LLM Egress Authorizations" in html
    assert "Recent LLM Egress Authorizations" in html
    assert "Expired LLM Egress Authorizations" in html
    assert "llm_egress_authorizations" in html
    assert "URLSearchParams(window.location.search)" in html
    assert "history.replaceState" in html
    assert "loadTaskDetail(taskCode, false)" in html
    assert "task-link-row" in html
    assert "updateTaskLink" in html
    assert "buildTaskUrl" in html
    assert "gate_results" in html
    assert "Runner Failures" in html
    assert "Stale Tool Calls" in html
    assert "Pending Tool Calls" in html
    assert "Recent GitHub Sync Links" in html
    assert "Recent GitHub Delivery Events" in html
    assert "Failed GitHub Sync Links" in html
    assert "github-sync-details" in html
    assert "data-task-code" in html
    assert "Task Detail" in html


def test_build_console_response_returns_overview(monkeypatch):
    calls = []

    monkeypatch.setattr(
        web_console,
        "get_console_overview",
        lambda limit=20, **filters: (
            calls.append((limit, filters)) or {"task_status_counts": {"DELIVERED": 1}}
        ),
    )

    status_code, payload = web_console.build_console_response("/api/console", "limit=3")

    assert status_code == HTTPStatus.OK
    assert payload["task_status_counts"] == {"DELIVERED": 1}
    assert calls == [(3, {"search": None, "status": None, "task_level": None})]


def test_build_console_response_passes_overview_filters(monkeypatch):
    calls = []

    monkeypatch.setattr(
        web_console,
        "get_console_overview",
        lambda limit=20, **filters: (
            calls.append((limit, filters)) or {"filters": filters, "recent_tasks": []}
        ),
    )

    status_code, payload = web_console.build_console_response(
        "/api/console",
        "limit=5&search=TASK-1&status=DELIVERED&task_level=L2",
    )

    assert status_code == HTTPStatus.OK
    assert payload["filters"] == {
        "search": "TASK-1",
        "status": "DELIVERED",
        "task_level": "L2",
    }
    assert calls == [
        (
            5,
            {
                "search": "TASK-1",
                "status": "DELIVERED",
                "task_level": "L2",
            },
        )
    ]


def test_build_console_response_clamps_limit(monkeypatch):
    calls = []

    monkeypatch.setattr(
        web_console,
        "get_console_risks",
        lambda limit=20: calls.append(limit) or {"summary": {}},
    )

    status_code, payload = web_console.build_console_response("/api/console/risks", "limit=999")

    assert status_code == HTTPStatus.OK
    assert payload == {"summary": {}}
    assert calls == [100]


def test_build_console_response_returns_github_sync(monkeypatch):
    calls = []

    monkeypatch.setattr(
        web_console,
        "get_console_github_sync",
        lambda limit=20: calls.append(limit) or {"summary": {"github_link_count": 2}},
    )

    status_code, payload = web_console.build_console_response(
        "/api/console/github-sync",
        "limit=4",
    )

    assert status_code == HTTPStatus.OK
    assert payload["summary"] == {"github_link_count": 2}
    assert calls == [4]


def test_build_console_response_returns_task_detail(monkeypatch):
    calls = []

    monkeypatch.setattr(
        web_console,
        "get_task_detail",
        lambda task_code: (
            calls.append(task_code)
            or {
                "task_code": task_code,
                "events": [],
                "tool_calls": [],
                "artifacts": [],
                "data_assets": [],
                "skill_usage": [],
                "llm_egress_authorizations": [],
            }
        ),
    )

    status_code, payload = web_console.build_console_response(
        "/api/console/tasks/TASK-20260518-120000"
    )

    assert status_code == HTTPStatus.OK
    assert payload["task_code"] == "TASK-20260518-120000"
    assert calls == ["TASK-20260518-120000"]


def test_build_console_response_returns_not_found_for_missing_task(monkeypatch):
    monkeypatch.setattr(web_console, "get_task_detail", lambda _task_code: None)

    status_code, payload = web_console.build_console_response("/api/console/tasks/TASK-MISSING")

    assert status_code == HTTPStatus.NOT_FOUND
    assert payload == {"error": "task_not_found", "task_code": "TASK-MISSING"}


def test_build_console_response_returns_service_unavailable_on_data_error(monkeypatch):
    def raise_data_error(**_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(web_console, "get_console_overview", raise_data_error)

    status_code, payload = web_console.build_console_response("/api/console")

    assert status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert payload["error"] == "service_unavailable"
    assert payload["message"] == "Console data unavailable."
    assert payload["path"] == "/api/console"
    assert payload["detail"] == "database unavailable"


def test_build_console_response_returns_not_found_for_unknown_path():
    status_code, payload = web_console.build_console_response("/api/missing")

    assert status_code == HTTPStatus.NOT_FOUND
    assert payload["error"] == "not_found"
    assert "/api/console" in payload["available_paths"]
    assert "/api/console/github-sync" in payload["available_paths"]
    assert "/api/console/tasks/{task_code}" in payload["available_paths"]
