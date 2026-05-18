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

    async function loadJson(path) {
      const response = await fetch(path, { cache: "no-store" });
      return response.json();
    }

    async function refresh() {
      const overview = await loadJson("/api/console?limit=8");
      const risks = await loadJson("/api/console/risks?limit=8");
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
    }

    document.querySelector("#task-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      const taskCode = document.querySelector("#task-code").value.trim();
      if (!taskCode) return;
      const detail = await loadJson(`/api/console/tasks/${encodeURIComponent(taskCode)}`);
      document.querySelector("#task-output").textContent = JSON.stringify(detail, null, 2);
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
