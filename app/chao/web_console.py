import json
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

from app.chao.services.console import (
    get_console_approval_queue,
    get_console_audit,
    get_console_gates,
    get_console_github_sync,
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
    nav { display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }
    nav a {
      color: #fff; text-decoration: none; border: 1px solid #56708c;
      border-radius: 6px; padding: 5px 8px; font-size: 13px;
    }
    nav a:hover { background: #1c3a5b; }
    section { background: #fff; border: 1px solid #d9dee7; border-radius: 8px; padding: 16px; }
    .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 12px; }
    .metric { border: 1px solid #e2e7ef; border-radius: 6px; padding: 12px; background: #fbfcfe; }
    .metric strong { display: block; font-size: 22px; margin-top: 6px; }
    form { display: flex; gap: 8px; flex-wrap: wrap; }
    .controls { align-items: center; }
    .controls input[type="number"] { max-width: 90px; min-width: 90px; }
    .controls input[type="search"] { max-width: 320px; min-width: 220px; }
    input {
      min-width: 280px; flex: 1; padding: 9px 10px;
      border: 1px solid #cbd3df; border-radius: 6px;
    }
    select {
      padding: 9px 10px; border: 1px solid #cbd3df; border-radius: 6px;
      background: #fff;
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
    .muted a { color: #1f6feb; }
    .notice {
      border: 1px solid #d8e0ea; border-radius: 6px; padding: 12px;
      background: #fbfcfe; color: #445268; margin-top: 12px;
    }
    .notice.error { border-color: #f1b9b9; background: #fff7f7; color: #7a2f2f; }
  </style>
</head>
<body>
  <header>
    <h1>Chao Console</h1>
    <div class="muted">Read-only local control plane</div>
    <nav aria-label="Console sections">
      <a href="#controls-section">Controls</a>
      <a href="#overview-section">Overview</a>
      <a href="#risks-section">Risks</a>
      <a href="#github-sync-section">GitHub Sync</a>
      <a href="#gates-section">Gates</a>
      <a href="#audit-section">Audit</a>
      <a href="#approvals-section">Approvals</a>
      <a href="#recent-section">Recent</a>
      <a href="#task-detail-section">Task Detail</a>
    </nav>
  </header>
  <main>
    <section id="controls-section">
      <h2>Controls</h2>
      <form id="refresh-form" class="controls">
        <label for="record-limit">Limit</label>
        <input id="record-limit" name="record-limit" type="number" min="1" max="100" value="8">
        <label for="task-search">Search</label>
        <input id="task-search" name="task-search" type="search" placeholder="Task code or title">
        <label for="status-filter">Status</label>
        <select id="status-filter" name="status-filter">
          <option value="">All</option>
          <option value="DELIVERED">DELIVERED</option>
          <option value="NEED_CONFIRMATION">NEED_CONFIRMATION</option>
          <option value="DESIGNING">DESIGNING</option>
          <option value="MILESTONE_PLANNING">MILESTONE_PLANNING</option>
          <option value="VALIDATION_FAILED">VALIDATION_FAILED</option>
        </select>
        <label for="level-filter">Level</label>
        <select id="level-filter" name="level-filter">
          <option value="">All</option>
          <option value="L1">L1</option>
          <option value="L2">L2</option>
          <option value="L3">L3</option>
          <option value="L4">L4</option>
        </select>
        <button type="submit">Refresh</button>
        <span id="last-updated" class="muted">Not loaded</span>
      </form>
    </section>
    <section id="overview-section">
      <h2>Overview</h2>
      <div id="overview" class="grid"></div>
    </section>
    <section id="risks-section">
      <h2>Risks</h2>
      <div id="risks" class="grid"></div>
      <div id="risk-details"></div>
    </section>
    <section id="github-sync-section">
      <h2>GitHub Sync</h2>
      <div id="github-sync" class="grid"></div>
      <div id="github-sync-details"></div>
    </section>
    <section id="gates-section">
      <h2>Gates</h2>
      <div id="gates" class="grid"></div>
      <div id="gate-details"></div>
    </section>
    <section id="audit-section">
      <h2>Audit Trail</h2>
      <div id="audit-trail"></div>
    </section>
    <section id="approvals-section">
      <h2>Approval Queue</h2>
      <div id="approval-queue"></div>
    </section>
    <section id="recent-section">
      <h2>Recent Tasks</h2>
      <div id="recent-tasks"></div>
    </section>
    <section id="task-detail-section">
      <h2>Task Detail</h2>
      <form id="task-form">
        <input id="task-code" name="task-code" placeholder="TASK-YYYYMMDD-HHMMSS-ffffff">
        <button type="submit">Load</button>
      </form>
      <div id="task-link-row" class="muted">
        Task link: <a id="task-link" href="#">No task selected</a>
      </div>
      <div id="task-summary"></div>
      <div id="task-detail-tables"></div>
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

    function hasError(payload) {
      return Boolean(payload?.error);
    }

    function renderNotice(message, type = "info") {
      return `<div class="notice ${escapeHtml(type)}">${escapeHtml(message)}</div>`;
    }

    function renderPanelError(title, payload) {
      const detail = payload?.message || payload?.detail || payload?.error || "Unknown error";
      return renderNotice(`${title}: ${detail}`, "error");
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
      if (hasError(tasks)) {
        return renderPanelError("Approval Queue", tasks);
      }

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
      if (hasError(risks)) {
        return renderPanelError("Risk details", risks);
      }

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
        renderRiskTable("Stale Tool Calls", risks.stale_tool_calls ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "agent_name", label: "Agent" },
          { key: "tool_name", label: "Tool" },
          { key: "age_minutes", label: "Age Minutes" }
        ]),
        renderRiskTable("Pending Tool Calls", risks.pending_tool_calls ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "agent_name", label: "Agent" },
          { key: "tool_name", label: "Tool" },
          { key: "started_at", label: "Started" }
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
        ]),
        renderRiskTable(
          "Expired LLM Egress Authorizations",
          risks.expired_llm_egress_authorizations ?? [],
          [
            { key: "task_code", label: "Task" },
            { key: "provider", label: "Provider" },
            { key: "model", label: "Model" },
            { key: "expires_at", label: "Expires" }
          ]
        )
      ].join("");
    }

    function renderGateDetails(gates) {
      if (hasError(gates)) {
        return renderPanelError("Gate details", gates);
      }

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

    function renderGitHubSyncDetails(githubSync) {
      if (hasError(githubSync)) {
        return renderPanelError("GitHub Sync", githubSync);
      }

      const typeMetrics = Object.entries(githubSync.link_type_counts ?? {});
      const statusMetrics = Object.entries(githubSync.status_counts ?? {});

      return `
        <h2>GitHub Link Types</h2>
        <div class="grid">${typeMetrics.map(asMetric).join("")}</div>
        <h2>GitHub Link Status</h2>
        <div class="grid">${statusMetrics.map(asMetric).join("")}</div>
        ${renderRiskTable("Recent GitHub Sync Links", githubSync.recent_links ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "link_type", label: "Type" },
          { key: "external_id", label: "External ID" },
          { key: "status", label: "Status" },
          { key: "created_by", label: "By" }
        ])}
        ${renderRiskTable("Recent GitHub Delivery Events", githubSync.recent_delivery_events ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "summary", label: "Summary" },
          { key: "created_by", label: "By" },
          { key: "created_at", label: "Created" }
        ])}
        ${renderRiskTable(
          "Unlinked Delivered Tasks",
          githubSync.recent_unlinked_delivered_tasks ?? [],
          [
            { key: "task_code", label: "Task" },
            { key: "title", label: "Title" },
            { key: "task_level", label: "Level" },
            { key: "owner", label: "Owner" }
          ]
        )}
        ${renderRiskTable("Failed GitHub Sync Links", githubSync.failed_links ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "link_type", label: "Type" },
          { key: "external_id", label: "External ID" },
          { key: "status", label: "Status" }
        ])}
      `;
    }

    function renderAuditTrail(audit) {
      if (hasError(audit)) {
        return renderPanelError("Audit Trail", audit);
      }

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
        ]),
        renderRiskTable("Recent LLM Egress Authorizations", audit.llm_egress_authorizations ?? [
        ], [
          { key: "task_code", label: "Task" },
          { key: "provider", label: "Provider" },
          { key: "model", label: "Model" },
          { key: "active", label: "Active" }
        ])
      ].join("");
    }

    function renderTaskSummary(task) {
      if (task.error) {
        return renderPanelError("Task Detail", task);
      }

      const fields = [
        ["Task", task.task_code],
        ["Title", task.title],
        ["Level", task.task_level],
        ["Status", task.status],
        ["Owner", task.owner],
        ["Created", task.created_at],
        ["Updated", task.updated_at]
      ];
      const counts = {
        events: (task.events ?? []).length,
        tool_calls: (task.tool_calls ?? []).length,
        artifacts: (task.artifacts ?? []).length,
        data_assets: (task.data_assets ?? []).length,
        skill_usage: (task.skill_usage ?? []).length,
        llm_egress_authorizations: (task.llm_egress_authorizations ?? []).length,
        github_links: (task.github_links ?? []).length,
        gate_results: (task.gate_results ?? []).length
      };
      const fieldRows = fields.map(([name, value]) => `
        <tr><td>${escapeHtml(name)}</td><td>${escapeHtml(value)}</td></tr>
      `).join("");

      return `
        <table>
          <tbody>${fieldRows}</tbody>
        </table>
        <div class="grid">${Object.entries(counts).map(asMetric).join("")}</div>
      `;
    }

    function renderTaskDetailTables(task) {
      if (task.error) {
        return "";
      }

      return [
        renderRiskTable("Task Events", task.events ?? [
        ], [
          { key: "event_type", label: "Event" },
          { key: "from_status", label: "From" },
          { key: "to_status", label: "To" },
          { key: "created_by", label: "By" }
        ]),
        renderRiskTable("Task Tool Calls", task.tool_calls ?? [
        ], [
          { key: "agent_name", label: "Agent" },
          { key: "tool_name", label: "Tool" },
          { key: "result_status", label: "Result" },
          { key: "risk_flag", label: "Risk" }
        ]),
        renderRiskTable("Task Artifacts", task.artifacts ?? [
        ], [
          { key: "artifact_type", label: "Type" },
          { key: "artifact_uri", label: "URI" },
          { key: "access_level", label: "Access" }
        ]),
        renderRiskTable("Task Data Assets", task.data_assets ?? [
        ], [
          { key: "asset_type", label: "Type" },
          { key: "classification", label: "Class" },
          { key: "owner", label: "Owner" },
          { key: "primary_storage", label: "Storage" }
        ]),
        renderRiskTable("Task Skill Usage", task.skill_usage ?? [
        ], [
          { key: "name", label: "Skill" },
          { key: "path", label: "Path" },
          { key: "status", label: "Status" },
          { key: "content_sha256", label: "SHA256" }
        ]),
        renderRiskTable("Task Skill Execution Plan", task.skill_execution_plan?.skills ?? [
        ], [
          { key: "name", label: "Skill" },
          { key: "status", label: "Status" },
          { key: "path", label: "Path" },
          { key: "content_sha256", label: "SHA256" }
        ]),
        renderRiskTable("Task GitHub Links", task.github_links ?? [
        ], [
          { key: "link_type", label: "Type" },
          { key: "external_id", label: "External ID" },
          { key: "status", label: "Status" },
          { key: "url", label: "URL" }
        ]),
        renderRiskTable("Task LLM Egress Authorizations", task.llm_egress_authorizations ?? [
        ], [
          { key: "provider", label: "Provider" },
          { key: "model", label: "Model" },
          { key: "data_classification", label: "Class" },
          { key: "active", label: "Active" }
        ]),
        renderRiskTable("Task Gate Results", task.gate_results ?? [
        ], [
          { key: "gate_name", label: "Gate" },
          { key: "status", label: "Status" },
          { key: "command", label: "Command" }
        ])
      ].join("");
    }

    function buildTaskUrl(taskCode) {
      const url = new URL(window.location.href);
      url.searchParams.set("task", taskCode);
      return url;
    }

    function updateTaskUrl(taskCode) {
      const url = buildTaskUrl(taskCode);
      window.history.replaceState({}, "", url);
    }

    function updateTaskLink(taskCode) {
      const url = buildTaskUrl(taskCode);
      const link = document.querySelector("#task-link");
      link.href = url;
      link.textContent = url;
    }

    async function loadTaskDetail(taskCode, updateUrl = true) {
      const detail = await loadJson(`/api/console/tasks/${encodeURIComponent(taskCode)}`);
      document.querySelector("#task-code").value = taskCode;
      document.querySelector("#task-summary").innerHTML = renderTaskSummary(detail);
      document.querySelector("#task-detail-tables").innerHTML = renderTaskDetailTables(detail);
      document.querySelector("#task-output").textContent = JSON.stringify(detail, null, 2);
      updateTaskLink(taskCode);
      if (updateUrl) {
        updateTaskUrl(taskCode);
      }
    }

    async function loadJson(path) {
      const response = await fetch(path, { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok) {
        return { ...payload, http_status: response.status };
      }
      return payload;
    }

    function selectedLimit() {
      const value = Number.parseInt(document.querySelector("#record-limit").value, 10);
      if (Number.isNaN(value)) return 8;
      return Math.min(Math.max(value, 1), 100);
    }

    function selectedTaskFilters() {
      return {
        search: document.querySelector("#task-search").value.trim(),
        status: document.querySelector("#status-filter").value,
        task_level: document.querySelector("#level-filter").value
      };
    }

    function buildOverviewQuery(limit, filters) {
      const params = new URLSearchParams();
      params.set("limit", limit);
      if (filters.search) params.set("search", filters.search);
      if (filters.status) params.set("status", filters.status);
      if (filters.task_level) params.set("task_level", filters.task_level);
      return params.toString();
    }

    function updateFilterUrl(limit, filters) {
      const url = new URL(window.location.href);
      url.searchParams.set("limit", limit);
      for (const key of ["search", "status", "task_level"]) {
        if (filters[key]) {
          url.searchParams.set(key, filters[key]);
        } else {
          url.searchParams.delete(key);
        }
      }
      window.history.replaceState({}, "", url);
    }

    function hydrateFiltersFromUrl() {
      const params = new URLSearchParams(window.location.search);
      const limit = params.get("limit");
      const search = params.get("search");
      const status = params.get("status");
      const taskLevel = params.get("task_level");

      if (limit) document.querySelector("#record-limit").value = limit;
      if (search) document.querySelector("#task-search").value = search;
      if (status) document.querySelector("#status-filter").value = status;
      if (taskLevel) document.querySelector("#level-filter").value = taskLevel;
    }

    async function refresh() {
      const limit = selectedLimit();
      const filters = selectedTaskFilters();
      const overview = await loadJson(`/api/console?${buildOverviewQuery(limit, filters)}`);
      const risks = await loadJson(`/api/console/risks?limit=${limit}`);
      const githubSync = await loadJson(`/api/console/github-sync?limit=${limit}`);
      const gates = await loadJson(`/api/console/gates?limit=${limit}`);
      const audit = await loadJson(`/api/console/audit?limit=${limit}`);
      const approvals = await loadJson(`/api/console/approvals?limit=${limit}`);
      updateFilterUrl(limit, filters);
      if (hasError(overview)) {
        document.querySelector("#overview").innerHTML = renderPanelError("Overview", overview);
        document.querySelector("#recent-tasks").innerHTML = renderPanelError(
          "Recent Tasks",
          overview
        );
      } else {
        const overviewMetrics = {
          artifacts: overview.artifact_count ?? 0,
          data_assets: overview.data_asset_count ?? 0,
          active_llm_egress_authorizations: overview.active_llm_egress_authorization_count ?? 0,
          failed_tool_calls: overview.failed_tool_call_count ?? 0,
          recent_tasks: (overview.recent_tasks ?? []).length
        };
        document.querySelector("#overview").innerHTML =
          Object.entries(overviewMetrics).map(asMetric).join("");
        document.querySelector("#recent-tasks").innerHTML =
          renderRecentTasks(overview.recent_tasks ?? []);
      }
      document.querySelector("#risks").innerHTML = hasError(risks)
        ? renderPanelError("Risks", risks)
        : Object.entries(risks.summary ?? {}).map(asMetric).join("");
      document.querySelector("#risk-details").innerHTML = renderRiskDetails(risks);
      document.querySelector("#github-sync").innerHTML = hasError(githubSync)
        ? renderPanelError("GitHub Sync", githubSync)
        : Object.entries(githubSync.summary ?? {}).map(asMetric).join("");
      document.querySelector("#github-sync-details").innerHTML =
        renderGitHubSyncDetails(githubSync);
      document.querySelector("#gates").innerHTML = hasError(gates)
        ? renderPanelError("Gates", gates)
        : Object.entries(gates.gate_status_counts ?? {}).map(asMetric).join("");
      document.querySelector("#gate-details").innerHTML = renderGateDetails(gates);
      document.querySelector("#audit-trail").innerHTML = renderAuditTrail(audit);
      document.querySelector("#approval-queue").innerHTML =
        renderApprovalQueue(approvals.error ? approvals : (approvals.approvals ?? []));
      document.querySelector("#last-updated").textContent =
        `Last updated ${new Date().toLocaleTimeString()}`;
    }

    document.querySelector("#refresh-form").addEventListener("submit", async (event) => {
      event.preventDefault();
      await refresh();
    });

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

    document.querySelector("#github-sync-details").addEventListener("click", async (event) => {
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

    async function boot() {
      hydrateFiltersFromUrl();
      await refresh();
      const taskCode = new URLSearchParams(window.location.search).get("task");
      if (taskCode) {
        await loadTaskDetail(taskCode, false);
      }
    }

    boot().catch((error) => {
      document.querySelector("#overview").innerHTML =
        renderNotice(`Console load failed: ${error}`, "error");
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


def _parse_optional_filter(query: dict[str, list[str]], name: str) -> str | None:
    values = query.get(name, [])
    if not values:
        return None

    value = values[0].strip()
    if not value:
        return None

    return value


def _build_service_error(path: str, exc: Exception) -> dict[str, Any]:
    return {
        "error": "service_unavailable",
        "message": "Console data unavailable.",
        "path": path,
        "detail": str(exc),
    }


def build_console_response(path: str, query_string: str = "") -> tuple[int, dict[str, Any]]:
    query = parse_qs(query_string)
    limit = _parse_limit(query)
    search = _parse_optional_filter(query, "search")
    status = _parse_optional_filter(query, "status")
    task_level = _parse_optional_filter(query, "task_level")

    if path == "/health":
        return HTTPStatus.OK, {"status": "ok"}

    try:
        if path == "/api/console":
            return HTTPStatus.OK, get_console_overview(
                limit=limit,
                search=search,
                status=status,
                task_level=task_level,
            )
        if path == "/api/console/approvals":
            return HTTPStatus.OK, {"approvals": get_console_approval_queue(limit=limit)}
        if path == "/api/console/audit":
            return HTTPStatus.OK, get_console_audit(limit=limit)
        if path == "/api/console/github-sync":
            return HTTPStatus.OK, get_console_github_sync(limit=limit)
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
    except Exception as exc:
        return HTTPStatus.SERVICE_UNAVAILABLE, _build_service_error(path, exc)

    return HTTPStatus.NOT_FOUND, {
        "error": "not_found",
        "path": path,
        "available_paths": [
            "/health",
            "/api/console",
            "/api/console/approvals",
            "/api/console/audit",
            "/api/console/github-sync",
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
