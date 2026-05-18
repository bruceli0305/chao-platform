from http import HTTPStatus

from app.chao import web_console


def test_build_console_index_html_contains_read_only_ui():
    html = web_console.build_console_index_html()

    assert "<title>Chao Console</title>" in html
    assert "/api/console?limit=8" in html
    assert "/api/console/approvals?limit=8" in html
    assert "/api/console/audit?limit=8" in html
    assert "/api/console/gates?limit=8" in html
    assert "/api/console/risks?limit=8" in html
    assert "/api/console/tasks/" in html
    assert "Approval Queue" in html
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
    assert "renderAuditTrail" in html
    assert "Runner Failures" in html
    assert "data-task-code" in html
    assert "Task Detail" in html


def test_build_console_response_returns_overview(monkeypatch):
    calls = []

    monkeypatch.setattr(
        web_console,
        "get_console_overview",
        lambda limit=20: calls.append(limit) or {"task_status_counts": {"DELIVERED": 1}},
    )

    status_code, payload = web_console.build_console_response("/api/console", "limit=3")

    assert status_code == HTTPStatus.OK
    assert payload["task_status_counts"] == {"DELIVERED": 1}
    assert calls == [3]


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


def test_build_console_response_returns_not_found_for_unknown_path():
    status_code, payload = web_console.build_console_response("/api/missing")

    assert status_code == HTTPStatus.NOT_FOUND
    assert payload["error"] == "not_found"
    assert "/api/console" in payload["available_paths"]
    assert "/api/console/tasks/{task_code}" in payload["available_paths"]
