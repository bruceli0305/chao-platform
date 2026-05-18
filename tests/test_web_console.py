from http import HTTPStatus

from app.chao import web_console


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


def test_build_console_response_returns_not_found_for_unknown_path():
    status_code, payload = web_console.build_console_response("/api/missing")

    assert status_code == HTTPStatus.NOT_FOUND
    assert payload["error"] == "not_found"
    assert "/api/console" in payload["available_paths"]
