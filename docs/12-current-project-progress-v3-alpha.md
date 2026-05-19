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
已具备任务路由、状态机、审批、审计、数据边界、CI 门禁、Runner 原型和只读 Console；
尚未具备完整 MCP 协议层拦截、Skills 自动执行、真实 Sandbox、GitHub 双向同步和语义向量检索。
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
uv run python main.py bind-github TASK-xxxx pull_request 123 https://github.com/org/repo/pull/123
uv run python main.py console --json
uv run python main.py console-task TASK-xxxx --json
uv run python main.py console-approvals --json
uv run python main.py console-audit --json
uv run python main.py console-gates --json
uv run python main.py console-risks --json
uv run python main.py web-console --host 127.0.0.1 --port 8765
uv run python main.py runner-patch TASK-xxxx app/example.py --old-text "old" --new-text "new"
uv run python main.py runner-validate TASK-xxxx --gate compile
uv run python main.py runner-attempt TASK-xxxx app/example.py --old-text "old" --new-text "new" --gate compile
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
Agent Runner 分支创建策略已定义，执行型任务生成 codex/ 前缀 branch plan；
Agent Runner allowed scope 阻断已定义，工部节点执行前会校验 changed_files；
Agent Runner 刑部验证计划已定义，验证失败不能进入 DELIVERED；
Agent Runner patch artifact 已定义，执行型任务会生成 runner_patch 交付证据；
Agent Runner 失败回流已定义，验证失败会生成 runner_failure_feedback 反馈给工部；
Agent Runner 受控文本 patch 执行器已定义，显式 runner_patch_operations 可在 allowed scope 内真实修改文件；
Agent Runner runner-patch CLI 已定义，默认 dry-run，显式 --apply 才真实写文件，并写入 tool_calls 审计；
Agent Runner runner-validate CLI 已定义，可执行 allowlist 验证 gate，并写入 task_events / tool_calls；
Agent Runner runner-attempt CLI 已定义，可串联 patch、validation，并在 --apply 后登记 runner_patch 或 runner_failure_feedback；
Agent Runner runner-attempt 状态回写已定义，dry-run 不改状态，--apply 后按验证结果更新为 DELIVERED 或 VALIDATION_FAILED；
Agent Runner runner-branch CLI 已定义，默认 dry-run，显式 --apply 才创建并切换 codex/ 执行分支；
Agent Runner runner-workspace CLI 已定义，默认 dry-run，显式 --apply 才在 .chao/sandboxes 下创建隔离 git worktree；
Agent Runner runner-sandbox CLI 已定义，默认 dry-run，显式 --apply 才用 Docker 执行 allowlist gate；
Tool Gateway 协议层拦截已定义，未授权工具不会执行 handler，并输出可写入 tool_calls 的审计字段；
Tool Gateway 外部 adapter 已定义，tool-gateway-serve 可通过 JSON Lines 提供 health、tool.evaluate 和测试 handler；
Tool Gateway 真实 handler registry 已定义，tool.execute 可在权限允许后执行 schema_check 和 data_boundary_check；
MCP Server stdio 外壳已定义，mcp-serve 支持 initialize、tools/list 和 tools/call，并复用权限网关；
Console 只读总览已定义，CLI 可输出任务、artifact、data_asset 和工具调用概览；
Console 只读任务详情已定义，CLI 可输出单任务审计链摘要；
Console 只读审批中心已定义，CLI 可输出 NEED_CONFIRMATION 任务队列；
Console 只读审计视图已定义，CLI 可输出事件、工具调用、Artifacts、Data Assets 和 GitHub links；
Console 只读 Gate 视图已定义，CLI 可输出 gate_results、工具权限和数据边界摘要；
Console 只读风险视图已定义，CLI 可输出阻塞任务、失败 gate、工具风险、数据边界风险和 GitHub 风险；
Console 风险视图已接入 runner_failure_feedback 回流证据，可直接定位 Runner 失败 artifact；
Web Console JSON API 基座已定义，CLI web-console 可提供只读 console API；
Web Console 任务详情 API 已定义，可按 task_code 返回单任务审计链；
Web Console 最小页面已定义，根路径可查看 overview、risks 并查询任务详情；
Web Console 最近任务列表已定义，可点击任务加载详情；
Web Console 审批队列已定义，可查看 NEED_CONFIRMATION 任务并点击加载详情；
Web Console 风险明细已定义，可查看阻塞任务、Runner 失败、失败 gate、工具风险和 GitHub 风险；
Web Console Gate / Data Boundary 面板已定义，可查看 gate 状态、工具权限审计和数据边界审计；
Web Console 审计链面板已定义，可查看事件、工具调用、Artifacts、Data Assets 和 GitHub links；
Web Console 刷新控制已定义，可调整查询数量并手动刷新页面数据；
Web Console 任务详情摘要已定义，可查看基础字段和审计对象计数；
Web Console 任务详情审计表已定义，可查看单任务事件、工具调用、Artifacts、Data Assets、GitHub links 和 gate 结果；
Web Console 页面导航已定义，可快速跳转各只读面板；
Web Console 任务详情深链接已定义，可通过 URL task 参数自动加载任务详情；
Web Console 任务详情链接已定义，加载任务后可直接复制当前任务 URL；
Web Console 任务搜索 / 状态过滤 / 等级过滤已定义，可通过 URL query 保留筛选条件；
Web Console 空态 / 错误态已定义，数据库或接口不可用时返回 503 并在页面显示可读提示；
pgvector local-hash-v1 embedding 写入已定义，scripts/ingest_markdown.py --write 会写入 context_chunks.embedding；
pgvector 向量检索已定义，scripts/search_context.py --mode vector 会按 pgvector 距离返回 vector_distance；
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
官方 MCP SDK 包接入与客户端联调；
Skills 自动读取、执行和交付记录闭环；
GitHub Issue / PR / Commit / CI 结果与 task 的自动双向同步；
Docker Sandbox 的镜像固化、缓存策略和真实流水线接入；
状态机持久化 checkpoint；
L3 / L4 治理 artifact 的人工审核命令与状态推进；
Web Console 的审批操作和产品化 UI。
```

## 5. 当前风险与注意事项

```text
1. 当前已有本地 Tool Gateway 拦截入口、首批真实 handler 和 MCP stdio 外壳，但尚未接入官方 MCP SDK 包并完成客户端联调；
2. 当前 data_assets 已登记任务 Markdown、治理 artifact 和 ingest 来源，但尚未覆盖所有未来数据来源；
3. pgvector 已有本地 embedding 写入和向量搜索原型，但尚未接入真实 embedding provider；
4. L3 approve 后已进入 DESIGNING，后续 REVIEWING / SCHEDULING 仍待完善；
5. 当前状态机尚未启用 LangGraph checkpoint 持久化；
6. Agent Runner 仍是受控文本 patch 原型，不等同于完整 Sandbox；
7. Web Console 当前为只读 Alpha，不具备审批写操作。
```

## 6. 当前建议操作

```text
1. 接入官方 MCP SDK 包并完成客户端联调；
2. Skills 自动读取、执行和交付记录闭环；
3. 持续使用 Ubuntu + Docker 作为最终验证环境，数据库变更统一通过 Docker psql 执行。
```
