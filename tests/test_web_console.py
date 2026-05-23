from http import HTTPStatus

from app.chao import web_console
from app.chao.repositories import RepositoryConfig


def test_build_console_index_html_contains_read_only_ui():
    html = web_console.build_console_index_html()

    assert "<title>Chao 控制台</title>" in html
    assert "record-limit" in html
    assert "刷新" in html
    assert "控制台分区" in html
    assert "#overview-section" in html
    assert "#repositories-section" in html
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
    assert "控制台加载失败" in html
    assert "/api/console?${buildOverviewQuery(limit, filters)}" in html
    assert 'loadJson("/api/console/repositories")' in html
    assert "/api/console/approvals?limit=${limit}" in html
    assert "/api/console/audit?limit=${limit}" in html
    assert "/api/console/github-sync?limit=${limit}" in html
    assert "/api/console/gates?limit=${limit}" in html
    assert "/api/console/risks?limit=${limit}" in html
    assert "/api/console/tasks/" in html
    assert "审批队列" in html
    assert "approval-result" in html
    assert "data-approve-task-code" in html
    assert "approval-note" in html
    assert "postJson" in html
    assert "/api/console/approvals/approve" in html
    assert "GitHub 同步" in html
    assert "数据边界审计" in html
    assert "审计追踪" in html
    assert "最近工具调用" in html
    assert "最近产物" in html
    assert "最近门槛结果" in html
    assert "最近任务" in html
    assert "risk-details" in html
    assert "gate-details" in html
    assert "renderRiskDetails" in html
    assert "renderGateDetails" in html
    assert "renderGitHubSyncDetails" in html
    assert "renderRepositoryDetails" in html
    assert "仓库工作区" in html
    assert "renderAuditTrail" in html
    assert "task-summary" in html
    assert "renderTaskSummary" in html
    assert "task-detail-tables" in html
    assert "renderTaskDetailTables" in html
    assert "任务工具调用" in html
    assert "任务门槛结果" in html
    assert "任务技能使用" in html
    assert "任务技能执行计划" in html
    assert "任务 LLM 外发授权" in html
    assert "最近 LLM 外发授权" in html
    assert "已过期 LLM 外发授权" in html
    assert "llm_egress_authorizations" in html
    assert "URLSearchParams(window.location.search)" in html
    assert "history.replaceState" in html
    assert "loadTaskDetail(taskCode, false)" in html
    assert "task-link-row" in html
    assert "updateTaskLink" in html
    assert "buildTaskUrl" in html
    assert "gate_results" in html
    assert "运行器失败" in html
    assert "运行器预检阻塞" in html
    assert "过期工具调用" in html
    assert "待处理工具调用" in html
    assert "最近 GitHub 同步链接" in html
    assert "最近 GitHub 交付事件" in html
    assert "未关联的已交付任务" in html
    assert "github-link-result" in html
    assert "renderGitHubBindTable" in html
    assert "data-bind-github-task-code" in html
    assert "github-external-id" in html
    assert "github-url" in html
    assert "/api/console/github-links/bind" in html
    assert "失败 GitHub 同步链接" in html
    assert "github-sync-details" in html
    assert "data-task-code" in html
    assert "任务详情" in html


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


def test_build_console_response_returns_repository_status(monkeypatch):
    repository = RepositoryConfig(
        name="demo",
        git_url="git@github.com:example/demo.git",
        default_branch="main",
        workspace_path="/opt/chao/workspaces/demo",
        sandbox_root="/opt/chao/sandboxes/demo",
        branch_prefix="codex/",
        enabled=True,
    )

    monkeypatch.setattr(
        web_console,
        "list_repository_configs",
        lambda: [repository],
    )
    monkeypatch.setattr(
        web_console,
        "build_repository_status_report",
        lambda repositories: {
            "summary": {
                "repositories": len(repositories),
                "ready": 1,
                "dirty": 0,
                "errors": 0,
            },
            "repositories": [
                {
                    "name": "demo",
                    "workspace_ready": True,
                    "behind": 1,
                }
            ],
        },
    )

    status_code, payload = web_console.build_console_response("/api/console/repositories")

    assert status_code == HTTPStatus.OK
    assert payload["summary"] == {
        "repositories": 1,
        "ready": 1,
        "dirty": 0,
        "errors": 0,
    }
    assert payload["repositories"][0]["name"] == "demo"
    assert payload["repositories"][0]["workspace_ready"] is True
    assert payload["repositories"][0]["behind"] == 1


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
    assert payload["message"] == "控制台数据不可用。"
    assert payload["path"] == "/api/console"
    assert payload["detail"] == "database unavailable"


def test_build_console_response_returns_not_found_for_unknown_path():
    status_code, payload = web_console.build_console_response("/api/missing")

    assert status_code == HTTPStatus.NOT_FOUND
    assert payload["error"] == "not_found"
    assert "/api/console" in payload["available_paths"]
    assert "/api/console/repositories" in payload["available_paths"]
    assert "/api/console/github-sync" in payload["available_paths"]
    assert "/api/console/tasks/{task_code}" in payload["available_paths"]


def test_build_console_write_response_approves_task(monkeypatch):
    calls = []

    monkeypatch.setattr(
        web_console,
        "approve_task",
        lambda task_code, confirmed_by, note="": (
            calls.append((task_code, confirmed_by, note))
            or {"task_code": task_code, "status": "DESIGNING"}
        ),
    )

    status_code, payload = web_console.build_console_write_response(
        "/api/console/approvals/approve",
        {
            "task_code": "TASK-20260518-120000",
            "by": "emperor",
            "note": "approved from console",
        },
    )

    assert status_code == HTTPStatus.OK
    assert payload["task"] == {
        "task_code": "TASK-20260518-120000",
        "status": "DESIGNING",
    }
    assert calls == [
        (
            "TASK-20260518-120000",
            "emperor",
            "approved from console",
        )
    ]


def test_build_console_write_response_rejects_missing_task_code():
    status_code, payload = web_console.build_console_write_response(
        "/api/console/approvals/approve",
        {"note": "missing task"},
    )

    assert status_code == HTTPStatus.BAD_REQUEST
    assert payload["error"] == "invalid_request"
    assert payload["message"] == "task_code 为必填项。"


def test_build_console_write_response_returns_approval_failure(monkeypatch):
    def fail_approval(**_kwargs):
        raise ValueError("Task TASK-1 is not waiting for confirmation.")

    monkeypatch.setattr(web_console, "approve_task", fail_approval)

    status_code, payload = web_console.build_console_write_response(
        "/api/console/approvals/approve",
        {"task_code": "TASK-1"},
    )

    assert status_code == HTTPStatus.BAD_REQUEST
    assert payload == {
        "error": "approval_failed",
        "message": "Task TASK-1 is not waiting for confirmation.",
        "task_code": "TASK-1",
    }


def test_build_console_write_response_returns_not_found_for_unknown_path():
    status_code, payload = web_console.build_console_write_response(
        "/api/console/missing",
        {},
    )

    assert status_code == HTTPStatus.NOT_FOUND
    assert payload["error"] == "not_found"
    assert "/api/console/approvals/approve" in payload["available_paths"]
    assert "/api/console/github-links/bind" in payload["available_paths"]


def test_build_console_write_response_binds_github_link(monkeypatch):
    calls = {
        "links": [],
        "events": [],
        "tool_calls": [],
    }
    task = {
        "id": "task-1",
        "task_code": "TASK-1",
        "task_level": "L2",
        "status": "DELIVERED",
        "route_result": {"required_confirmation": "B"},
    }

    monkeypatch.setattr(web_console, "get_task_detail", lambda _task_code: task)
    monkeypatch.setattr(
        web_console,
        "record_github_link",
        lambda **kwargs: calls["links"].append(kwargs),
    )
    monkeypatch.setattr(
        web_console,
        "record_task_event",
        lambda **kwargs: calls["events"].append(kwargs),
    )
    monkeypatch.setattr(
        web_console,
        "record_tool_call",
        lambda **kwargs: calls["tool_calls"].append(kwargs),
    )

    status_code, payload = web_console.build_console_write_response(
        "/api/console/github-links/bind",
        {
            "task_code": "TASK-1",
            "link_type": "pr",
            "external_id": "42",
            "url": "https://github.com/example/repo/pull/42",
            "by": "lee",
        },
    )

    assert status_code == HTTPStatus.OK
    assert payload["task"] == task
    assert calls["links"][0]["link_type"] == "pull_request"
    assert calls["links"][0]["metadata"] == {
        "task_code": "TASK-1",
        "source": "web-console",
    }
    assert calls["events"][0]["event_type"] == "github_link_bound"
    assert calls["tool_calls"][0]["tool_name"] == "cli.bind_github"
    assert calls["tool_calls"][0]["permission_policy"] == "local-cli-github-link-bind"


def test_build_console_write_response_rejects_missing_github_url():
    status_code, payload = web_console.build_console_write_response(
        "/api/console/github-links/bind",
        {
            "task_code": "TASK-1",
            "link_type": "pull_request",
            "external_id": "42",
        },
    )

    assert status_code == HTTPStatus.BAD_REQUEST
    assert payload == {
        "error": "invalid_request",
        "message": "url 为必填项。",
    }


def test_build_console_write_response_rejects_missing_github_task(monkeypatch):
    monkeypatch.setattr(web_console, "get_task_detail", lambda _task_code: None)

    status_code, payload = web_console.build_console_write_response(
        "/api/console/github-links/bind",
        {
            "task_code": "TASK-MISSING",
            "link_type": "pull_request",
            "external_id": "42",
            "url": "https://github.com/example/repo/pull/42",
        },
    )

    assert status_code == HTTPStatus.NOT_FOUND
    assert payload == {"error": "task_not_found", "task_code": "TASK-MISSING"}
