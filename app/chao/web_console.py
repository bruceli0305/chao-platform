import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from app.chao.services.console import (
    get_console_approval_queue,
    get_console_audit,
    get_console_gates,
    get_console_overview,
    get_console_risks,
)
from app.chao.services.store import get_task_detail

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def build_console_index_html() -> str:
    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Chao Console</title>
  <style>
    :root { color-scheme: light; font-family: Inter, Segoe UI, Arial, sans-serif; }
    body { margin: 0; background: #f6f7f9; color: #1f2933; }
    header { background: #102033; color: #fff; padding: 18px 28px; }
    main { max-width: 1180px; margin: 0 auto; padding: 24px; display: grid; gap: 18px; }
    h1, h2 { margin: 0; letter-spacing: 0; }
    h1 { font-size: 22px; }
    h2 { font-size: 16px; }
    section { background: #fff; border: 1px solid #d9dee7; border-radius: 8px; padding: 16px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .metric { border: 1px solid #e2e7ef; border-radius: 6px; padding: 12px; background: #fbfcfe; }
    .metric strong { display: block; font-size: 22px; margin-top: 6px; }
    form { display: flex; gap: 8px; flex-wrap: wrap; }
    input {
      min-width: 280px; flex: 1; padding: 9px 10px;
      border: 1px solid #cbd3df; border-radius: 6px;
    }
    button {
      padding: 9px 12px; border: 0; border-radius: 6px;
      background: #1f6feb; color: #fff; cursor: pointer;
    }
    pre {
      margin: 12px 0 0; overflow: auto; background: #111827;
      color: #e5e7eb; padding: 12px; border-radius: 6px;
    }
    table { width: 100%; border-collapse: collapse; margin-top: 12px; }
    th, td { text-align: left; border-bottom: 1px solid #e5e9f0; padding: 8px; font-size: 13px; }
    tr[data-task-code] { cursor: pointer; }
    tr[data-task-code]:hover { background: #f3f7fc; }
    .muted { color: #5f6c7b; font-size: 13px; }
  </style>
</head>
<body>
  <header>
    <h1>Chao Console</h1>
    <div class="muted">Read-only local control plane</div>
  </header>
  <main>
    <section>
      <h2>Overview</h2>
      <div id="overview" class="grid"></div>
    </section>
    <section>
      <h2>Risks</h2>
      <div id="risks" class="grid"></div>
      <div id="risk-details"></div>
    </section>
    <section>
      <h2>Gates</h2>
      <div id="gates" class="grid"></div>
      <div id="gate-details"></div>
    </section>
    <section>
      <h2>Audit Trail</h2>
      <div id="audit-trail"></div>
    </section>
    <section>
      <h2>Approval Queue</h2>
      <div id="approval-queue"></div>
    </section>
    <section>
      <h2>Recent Tasks</h2>
      <div id="recent-tasks"></div>
    </section>
    <section>
      <h2>Task Detail</h2>
      <form id="task-form">
        <input id="task-code" name="task-code" placeholder="TASK-YYYYMMDD-HHMMSS-ffffff">
        <button type="submit">Load</button>
      </form>
      <pre id="task-output">{}</pre>
    </section>
  </main>
  <script>
    const asMetric = ([name, value]) =>
      `<div class="metric"><span>${name}</span><strong>${value}</strong></div>`;

    function escapeHtml(value) {
      return String(value ?? "")
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;");
    }

    function renderRecentTasks(tasks) {
      if (!tasks.length) {
        return '<div class="muted">No recent tasks.</div>';
      }

      const rows = tasks.map((task) => `
        <tr data-task-code="${escapeHtml(task.task_code)}">
          <td>${escapeHtml(task.task_code)}</td>
          <td>${escapeHtml(task.title)}</td>
          <td>${escapeHtml(task.task_level)}</td>
          <td>${escapeHtml(task.status)}</td>
          <td>${escapeHtml(task.owner)}</td>
        </tr>
      `).join("");

      return `
        <table>
          <thead>
            <tr><th>Task</th><th>Title</th><th>Level</th><th>Status</th><th>Owner</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    function renderApprovalQueue(tasks) {
      if (!tasks.length) {
        return '<div class="muted">No tasks waiting for confirmation.</div>';
      }

      const rows = tasks.map((task) => `
        <tr data-task-code="${escapeHtml(task.task_code)}">
          <td>${escapeHtml(task.task_code)}</td>
          <td>${escapeHtml(task.title)}</td>
          <td>${escapeHtml(task.task_level)}</td>
          <td>${escapeHtml(task.required_confirmation)}</td>
          <td>${escapeHtml(task.owner)}</td>
        </tr>
      `).join("");

      return `
        <table>
          <thead>
            <tr><th>Task</th><th>Title</th><th>Level</th><th>Confirm</th><th>Owner</th></tr>
          </thead>
          <tbody>${rows}</tbody>
        </table>
      `;
    }

    function renderRiskTable(title, rows, columns) {
      if (!rows.length) {
        return `<div class="muted">${title}: none.</div>`;
      }

      const head = columns.map((column) => `<th>${escapeHtml(column.label)}</th>`).join("");
      const body = rows.map((row) => {
        const taskCode = row.task_code ? ` data-task-code="${escapeHtml(row.task_code)}"` : "";
        const cells = columns.map((column) =>
          `<td>${escapeHtml(row[column.key])}</td>`
        ).join("");
        return `<tr${taskCode}>${cells}</tr>`;
      }).join("");

      return `
        <h2>${escapeHtml(title)}</h2>
        <table>
          <thead><tr>${head}</tr></thead>
          <tbody>${body}</tbody>
        </table>
      `;
    }

    function renderRiskDetails(risks) {
      return [
        renderRiskTable("Blocked Tasks", risks.blocked_tasks ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "title", label: "Title" },
          { key: "task_level", label: "Level" },
          { key: "status", label: "Status" }
        ]),
        renderRiskTable("Runner Failures", risks.runner_failures ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "artifact_type", label: "Artifact" },
          { key: "artifact_uri", label: "URI" }
        ]),
        renderRiskTable("Failed Gates", risks.failed_gates ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "gate_name", label: "Gate" },
          { key: "status", label: "Status" },
          { key: "command", label: "Command" }
        ]),
        renderRiskTable("Tool Risks", risks.tool_risks ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "agent_name", label: "Agent" },
          { key: "tool_name", label: "Tool" },
          { key: "result_status", label: "Result" }
        ]),
        renderRiskTable("GitHub Risks", risks.github_risks ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "link_type", label: "Type" },
          { key: "external_id", label: "External ID" },
          { key: "status", label: "Status" }
        ])
      ].join("");
    }

    function renderGateDetails(gates) {
      const permissionMetrics = Object.entries(gates.tool_permission_audit ?? {});
      const boundaryMetrics = Object.entries(gates.data_boundary_audit ?? {});
      const gateRows = gates.recent_gate_results ?? [];

      return `
        <h2>Tool Permission Audit</h2>
        <div class="grid">${permissionMetrics.map(asMetric).join("")}</div>
        <h2>Data Boundary Audit</h2>
        <div class="grid">${boundaryMetrics.map(asMetric).join("")}</div>
        ${renderRiskTable("Recent Gate Results", gateRows, [
          { key: "task_code", label: "Task" },
          { key: "gate_name", label: "Gate" },
          { key: "status", label: "Status" },
          { key: "command", label: "Command" }
        ])}
      `;
    }

    function renderAuditTrail(audit) {
      return [
        renderRiskTable("Recent Events", audit.events ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "event_type", label: "Event" },
          { key: "from_status", label: "From" },
          { key: "to_status", label: "To" }
        ]),
        renderRiskTable("Recent Tool Calls", audit.tool_calls ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "agent_name", label: "Agent" },
          { key: "tool_name", label: "Tool" },
          { key: "result_status", label: "Result" }
        ]),
        renderRiskTable("Recent Artifacts", audit.artifacts ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "artifact_type", label: "Type" },
          { key: "artifact_uri", label: "URI" }
        ]),
        renderRiskTable("Recent Data Assets", audit.data_assets ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "asset_type", label: "Type" },
          { key: "classification", label: "Class" },
          { key: "owner", label: "Owner" }
        ]),
        renderRiskTable("Recent GitHub Links", audit.github_links ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "link_type", label: "Type" },
          { key: "external_id", label: "External ID" },
          { key: "status", label: "Status" }
        ])
      ].join("");
    }

    async function loadTaskDetail(taskCode) {
      const detail = await loadJson(`/api/console/tasks/${encodeURIComponent(taskCode)}`);
      document.querySelector("#task-code").value = taskCode;
      document.querySelector("#task-output").textContent = JSON.stringify(detail, null, 2);
    }

    async function loadJson(path) {
      const response = await fetch(path, { cache: "no-store" });
      return response.json();
    }

    async function refresh() {
      const overview = await loadJson("/api/console?limit=8");
      const risks = await loadJson("/api/console/risks?limit=8");
      const gates = await loadJson("/api/console/gates?limit=8");
      const audit = await loadJson("/api/console/audit?limit=8");
      const approvals = await loadJson("/api/console/approvals?limit=8");
      const overviewMetrics = {
        artifacts: overview.artifact_count ?? 0,
        data_assets: overview.data_asset_count ?? 0,
        failed_tool_calls: overview.failed_tool_call_count ?? 0,
        recent_tasks: (overview.recent_tasks ?? []).length
      };
      document.querySelector("#overview").innerHTML =
        Object.entries(overviewMetrics).map(asMetric).join("");
      document.querySelector("#risks").innerHTML =
        Object.entries(risks.summary ?? {}).map(asMetric).join("");
      document.querySelector("#risk-details").innerHTML = renderRiskDetails(risks);
      document.querySelector("#gates").innerHTML =
        Object.entries(gates.gate_status_counts ?? {}).map(asMetric).join("");
      document.querySelector("#gate-details").innerHTML = renderGateDetails(gates);
      document.querySelector("#audit-trail").innerHTML = renderAuditTrail(audit);
      document.querySelector("#approval-queue").innerHTML =
        renderApprovalQueue(approvals.approvals ?? []);
      document.querySelector("#recent-tasks").innerHTML =
        renderRecentTasks(overview.recent_tasks ?? []);
    }

    document.querySelector("#task-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const taskCode = document.querySelector("#task-code").value.trim();
      if (!taskCode) return;
      await loadTaskDetail(taskCode);
    });

    document.querySelector("#recent-tasks").addEventListener("click", async (event) => {
      const row = event.target.closest("tr[data-task-code]");
      if (!row) return;
      await loadTaskDetail(row.dataset.taskCode);
    });

    document.querySelector("#approval-queue").addEventListener("click", async (event) => {
      const row = event.target.closest("tr[data-task-code]");
      if (!row) return;
      await loadTaskDetail(row.dataset.taskCode);
    });

    document.querySelector("#risk-details").addEventListener("click", async (event) => {
      const row = event.target.closest("tr[data-task-code]");
      if (!row) return;
      await loadTaskDetail(row.dataset.taskCode);
    });

    document.querySelector("#gate-details").addEventListener("click", async (event) => {
      const row = event.target.closest("tr[data-task-code]");
      if (!row) return;
      await loadTaskDetail(row.dataset.taskCode);
    });

    document.querySelector("#audit-trail").addEventListener("click", async (event) => {
      const row = event.target.closest("tr[data-task-code]");
      if (!row) return;
      await loadTaskDetail(row.dataset.taskCode);
    });

    refresh().catch((error) => {
      document.querySelector("#overview").innerHTML =
        `<div class="metric">Load failed<strong>${error}</strong></div>`;
    });
  </script>
</body>
</html>
"""


def _parse_limit(query: dict[str, list[str]]) -> int:
    values = query.get("limit", [])
    if not values:
        return DEFAULT_LIMIT

    try:
        limit = int(values[0])
    except ValueError:
        return DEFAULT_LIMIT

    return min(max(limit, 1), MAX_LIMIT)


def build_console_response(path: str, query_string: str = "") -> tuple[int, dict[str, Any]]:
    query = parse_qs(query_string)
    limit = _parse_limit(query)

    if path == "/health":
        return HTTPStatus.OK, {"status": "ok"}
    if path == "/api/console":
        return HTTPStatus.OK, get_console_overview(limit=limit)
    if path == "/api/console/approvals":
        return HTTPStatus.OK, {"approvals": get_console_approval_queue(limit=limit)}
    if path == "/api/console/audit":
        return HTTPStatus.OK, get_console_audit(limit=limit)
    if path == "/api/console/gates":
        return HTTPStatus.OK, get_console_gates(limit=limit)
    if path == "/api/console/risks":
        return HTTPStatus.OK, get_console_risks(limit=limit)
    if path.startswith("/api/console/tasks/"):
        task_code = unquote(path.removeprefix("/api/console/tasks/")).strip()
        if not task_code or "/" in task_code:
            return HTTPStatus.NOT_FOUND, {"error": "task_not_found", "task_code": task_code}

        task = get_task_detail(task_code)
        if task is None:
            return HTTPStatus.NOT_FOUND, {"error": "task_not_found", "task_code": task_code}

        return HTTPStatus.OK, task

    return HTTPStatus.NOT_FOUND, {
        "error": "not_found",
        "path": path,
        "available_paths": [
            "/health",
            "/api/console",
            "/api/console/approvals",
            "/api/console/audit",
            "/api/console/gates",
            "/api/console/risks",
            "/api/console/tasks/{task_code}",
        ],
    }


class ConsoleRequestHandler(BaseHTTPRequestHandler):
    server_version = "ChaoWebConsole/0.1"

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.path in {"/", "/console"}:
            response = build_console_index_html().encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)
            return

        status_code, payload = build_console_response(parsed.path, parsed.query)
        response = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")

        self.send_response(int(status_code))
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

    def log_message(self, format: str, *args: Any) -> None:
        return


def run_web_console_server(host: str, port: int) -> None:
    server = ThreadingHTTPServer((host, port), ConsoleRequestHandler)
    server.serve_forever()
