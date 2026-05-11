# 当前项目进度 v3 Alpha

> 本文件记录 `chao-platform` 当前本地 MVP / Alpha 的真实工程进度，用于 Codex、ChatGPT、开发者和后续 Agent 接管项目。

## 1. 当前版本定位

```text
版本阶段：chao-v3-local-mvp-alpha
运行环境：Windows 10 + WSL2 Ubuntu + Docker Desktop
代码管理：GitHub 仓库 bruceli0305/chao-platform
主技术栈：Python 3.12、uv、LangGraph、Typer、Rich、PostgreSQL、pgvector、GitHub Actions
```

当前阶段不是完整 v3，而是 v3 的本地运行内核 Alpha：

```text
已具备任务路由、状态机、审批、审计、数据边界和 CI 门禁；
尚未具备完整 MCP 工具权限、Skills 执行机制、Agent Runner / Sandbox、GitHub Issue / PR 双向绑定和 Web Console。
```

## 2. 已完成能力

### 2.1 基础运行环境

```text
WSL2 Ubuntu 已可用；
Docker Desktop 已可用；
PostgreSQL + pgvector 已通过 Docker Compose 启动；
uv 项目环境已可用；
GitHub SSH 推送已可用；
GitHub Actions 已跑通。
```

### 2.2 数据库控制平面

已建基础表：

```text
tasks
task_routes
historian_records
gate_results
context_chunks
confirmations
task_events
tool_calls
artifacts
data_assets
storage_policies
```

`context_chunks` 已补充第一版 ingest 审计元数据：

```text
source_type
source_hash
data_classification
redacted
ingest_allowed
retention_policy
created_by
```

已建视图：

```text
artifact_records
```

已启用扩展：

```text
vector
```

已完成默认存储策略：

```text
D0_PUBLIC_KNOWLEDGE
D1_INTERNAL_ENGINEERING_KNOWLEDGE
D2_SENSITIVE_ENGINEERING_DATA
D3_STRICT_SECRET_DATA
D4_TEMP_EXECUTION_DATA
```

### 2.3 CLI 能力

当前 CLI 已支持：

```bash
uv run python main.py new "标题" "原始需求"
uv run python main.py list
uv run python main.py show TASK-xxxx
uv run python main.py approve TASK-xxxx --by lee --note "确认说明"
uv run python main.py status
```

### 2.4 任务路由与状态机

已完成：

```text
L1：低风险单点任务，最终 DELIVERED；
L2：普通功能 / 页面 / 接口类任务，最终 DELIVERED；
L3：数据库、迁移、权限、部署、Secret、架构等高风险任务，进入 NEED_CONFIRMATION；
approve 后：L3 从 NEED_CONFIRMATION 进入 DESIGNING，confirmations.status 记录 APPROVED。
```

当前状态机为 MVP 状态机，已支持：

```text
RAW → ROUTING → CLASSIFIED → IMPLEMENTING → VALIDATING → DELIVERED
RAW → ROUTING → CLASSIFIED → NEED_CONFIRMATION → DESIGNING
```

### 2.5 史官记录与 Markdown 双写

已完成：

```text
任务创建后写入 PostgreSQL；
任务创建后生成 .ai-agents/records/tasks/TASK-xxxx.md；
Markdown 史官记录登记为 artifacts；
Markdown 史官记录登记为 D1 data_asset；
L3 approve 后生成 .ai-agents/records/designs/TASK-xxxx-design.md；
L3 中书省方案登记为 artifacts 和 D1 data_asset；
L3 approve 后生成 .ai-agents/records/reviews/TASK-xxxx-review.md；
L3 门下省审核登记为 artifacts 和 D1 data_asset；
L3 approve 后生成 .ai-agents/records/hubu/TASK-xxxx-hubu.md；
L3 户部审查登记为 artifacts 和 D1 data_asset；
L3 approve 后生成 .ai-agents/records/bingbu/TASK-xxxx-bingbu.md；
L3 兵部审查登记为 artifacts 和 D1 data_asset；
L4 创建后生成 .ai-agents/records/milestones/TASK-xxxx-milestones.md；
L4 里程碑规划登记为 artifacts 和 D1 data_asset，且不进入工部执行；
Agent Runner / Sandbox 边界已定义，最小策略运行时可校验 allowed scope / forbidden scope；
任务详情 show 已包含 events / tool_calls / artifacts / data_assets。
```

### 2.6 A 级审批流

已完成：

```text
L3 自动生成 NEED_CONFIRMATION；
confirmations 表记录审批数据；
approve 命令执行后任务状态变为 DESIGNING；
approve 命令执行后生成中书省方案 artifact；
approve 命令执行后生成门下省审核 artifact；
approve 命令执行后生成户部审查 artifact；
approve 命令执行后生成兵部审查 artifact；
L4 approve 后进入 MILESTONE_PLANNING，不生成 L3 执行审查链；
historian_records 记录确认事实；
task_events 记录 task_approved；
tool_calls 记录 cli.approve；
GitHub Actions 已验证审批流。
```

### 2.7 审计链

已完成三条 v3 审计链：

```text
task_events：状态事件流；
tool_calls：工具调用审计；
artifacts：交付证据元数据。
```

并已进入 CI 门禁。

### 2.8 数据边界门禁

已完成：

```text
scripts/data_boundary_check.py：检查 .env、Secret、私钥、Token、data/postgres、logs、.venv 等边界；
scripts/schema_check.py：检查表、视图、vector 扩展、默认 storage_policies；
GitHub Actions 中已接入 data-boundary check 与 schema check。
data-boundary report 输出模板已落地：.ai-agents/templates/data-boundary-report.md。
pgvector ingest 白名单 / 禁止范围策略已落地：docs/15-pgvector-ingest-policy-v3.md。
```

### 2.9 工程质量门禁

已完成：

```text
ruff check；
ruff format check；
pytest；
compileall；
CLI smoke test；
PostgreSQL + pgvector service；
Schema check；
Data boundary check；
Secret scan；
L1 / L2 / L3 smoke test；
L3 approval smoke test；
task_events / tool_calls / artifacts / data_assets 持久化检查。
```

## 3. 当前 CI 能力

GitHub Actions 已覆盖：

```text
Python gates；
Secret scan；
PostgreSQL + pgvector 初始化；
db/init/001_init.sql 初始化；
Schema check；
Data boundary check；
Ruff；
Pytest；
Compile；
CLI status；
L1 / L2 / L3 任务创建；
L3 审批；
tasks / historian_records / confirmations 持久化；
task_events / tool_calls / artifacts / data_assets 持久化；
Markdown 史官记录生成。
```

## 4. 当前尚未完成

```text
MCP 工具权限运行时；
tool permission policy 的真实拦截；
Skills 路由和执行机制；
pgvector ingest 白名单、chunk、脱敏和检索；
GitHub Issue / PR / Commit / CI 结果与 task 绑定；
Agent Runner / Sandbox 的分支创建、scope 阻断、patch artifact 和失败回流；
状态机持久化 checkpoint；
L3 / L4 治理 artifact 的人工审核命令与状态推进；
Web Console。
```

## 5. 当前风险与注意事项

```text
1. 当前工具调用审计还是 CLI 层模拟，不是真实 MCP 工具拦截；
2. 当前 data_assets 已登记任务 Markdown、治理 artifact 和 ingest 来源，但尚未覆盖所有未来数据来源；
3. pgvector 只启用扩展，尚未实现 ingest；
4. L3 approve 后已进入 DESIGNING，后续 REVIEWING / SCHEDULING 仍待完善；
5. 当前状态机尚未启用 LangGraph checkpoint 持久化；
6. Codex 接管前必须确保完整 docs 和 .ai-agents 文件已入仓。
```

## 6. 当前建议操作

```text
1. 将完整 v3 文档包上传到 GitHub；
2. Ubuntu 中 git pull；
3. 在 WSL Ubuntu 项目目录启动 Codex；
4. 让 Codex 先阅读 AGENTS.md、docs/00、docs/01、docs/11、.ai-agents/router、.ai-agents/gates；
5. 后续开发以 Codex 改代码、ChatGPT 做审查和路线规划为主。
```
