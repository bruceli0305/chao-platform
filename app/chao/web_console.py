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
