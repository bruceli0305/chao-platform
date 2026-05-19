# 后续开发计划 v3

> 本文件作为 `chao-platform` 后续开发路线图。优先级以“先让 Codex / Agent 可接管、再补可审计能力、最后做自动化和可视化”为原则。

## 1. 总体路线

```text
阶段 A：文档入仓与 Codex 接管
阶段 B：数据边界闭环
阶段 C：pgvector 知识检索
阶段 D：Skills 最小执行机制
阶段 E：MCP 工具权限原型
阶段 F：GitHub Issue / PR 绑定
阶段 G：L3 / L4 完整治理
阶段 H：Agent Runner / Sandbox
阶段 I：Console 可视化
```

## 2. 阶段 A：文档入仓与 Codex 接管

目标：让 Codex 能在仓库中读取完整上下文，而不是依赖 ChatGPT 对话历史。

任务：

```text
A1. 上传完整 docs/ 与 .ai-agents/ 到 GitHub；
A2. 增加根目录 AGENTS.md；
A3. 增加 docs/12-current-project-progress-v3-alpha.md；
A4. 增加 docs/13-next-development-plan-v3.md；
A5. Ubuntu 中 git pull；
A6. Codex 首次接管并运行 ./scripts/check.sh；
A7. 使用 Codex 完成一个小型代码任务，验证接管质量。
```

验收：

```text
Codex 能说明项目定位；
Codex 能遵守数据边界；
Codex 能运行本地门禁；
GitHub Actions 通过。
```

## 3. 阶段 B：数据边界闭环

目标：让数据资产、存储策略、artifact 和任务详情形成完整可审计链。

任务：

```text
B1. show TASK-xxx 输出 data_assets；
B2. CI 中 Verify data assets persisted 增加 task_id 非空检查；
B3. data_assets 增加 source_uri / source_hash 可选字段；
B4. data_boundary_check.py 增强：检查 Markdown 记录是否包含疑似 Secret；
B5. artifacts 增强：检查 artifact_uri 对应文件存在性；
B6. 新增 data-boundary report 输出模板。
```

验收：

```text
每个任务至少有 Markdown artifact；
每个 Markdown artifact 对应一个 D1 data_asset；
data_asset 必须关联 task_id；
CI 可阻断数据边界违规。
```

## 4. 阶段 C：pgvector 知识检索

目标：实现第一版知识 ingest，为后续 Agent 检索历史决策、规则和史官记录做准备。

任务：

```text
C1. 设计 ingest 白名单：docs、.ai-agents、README、史官摘要；
C2. 明确禁止 ingest：.env、logs、data、CI 长日志、Secret、生产数据；
C3. 增加 context_chunks 字段：source_type、source_hash、classification、desensitized；
C4. 实现 scripts/ingest_markdown.py；
C5. 实现 scripts/search_context.py；
C6. 将 ingest 结果登记到 data_assets；
C7. 增加 schema_check 和 data_boundary_check 对 ingest 的校验。
C8. 为 context_chunks 增加 embedding 写入与向量相似度搜索。
```

当前状态：

```text
C1 / C2 已进入策略设计：docs/15-pgvector-ingest-policy-v3.md。
C3 context_chunks 元数据字段已落地：db/migrations/007_context_chunks_metadata.sql。
C7 的 ingest 白名单 / 禁止路径基础校验已接入 scripts/data_boundary_check.py。
C4 dry-run 已接入 scripts/ingest_markdown.py，不写数据库。
C4 dry-run 已接入 GitHub Actions。
C5 只读搜索骨架已接入 scripts/search_context.py。
C6 显式 --write 写入 context_chunks 与 data_assets 已接入 scripts/ingest_markdown.py。
C6 / C7 的 GitHub Actions 写入 smoke test 已接入，验证 context_chunks 与 context_chunk_source data_assets。
C8 local-hash-v1 本地 embedding 已接入 scripts/ingest_markdown.py，写入 context_chunks.embedding。
C8 scripts/search_context.py 已支持 --mode vector，通过 pgvector 距离排序返回 vector_distance。
```

验收：

```text
可以检索 docs/11-data-storage-boundary-v3.md；
可以检索 AGENTS.md；
可以检索指定 TASK 的史官摘要；
禁止文件不会被 ingest。
```

## 5. 阶段 D：Skills 最小执行机制

目标：从“角色说明”进入“可复用能力包”。

第一批 Skill：

```text
bugfix；
frontend-feature；
api-development；
database-migration；
security-review；
docs-generation；
release-validation。
```

任务：

```text
D1. 定义 skills registry；
D2. 路由器输出 required_skills；
D3. CLI show 显示 required_skills；
D4. 新增 tests/test_skills.py；
D5. Codex 根据 Skill 执行任务前必须读取对应 SKILL.md；
D6. GitHub PR 模板增加 Skill 字段。
```

当前状态：

```text
D1 skills registry 已接入 app/chao/skills.py，登记第一批 7 个 Skill 与 SKILL.md 路径。
D2 路由器已输出 required_skills / required_skill_paths，并写入 route_result。
D3 CLI show 已从 task_routes.route_json 返回 required_skills / required_skill_paths。
D4 tests/test_skills.py 已覆盖 registry、匹配规则和 L1 / L2 / L3 / L4 限制。
D5 AGENTS.md 已要求执行前读取 required_skill_paths 对应的 SKILL.md。
D6 GitHub PR 模板已增加 Skill 字段和 SKILL.md 阅读确认项。
```

验收：

```text
L2 前端页面任务能命中 frontend-feature；
Bug 修复任务能命中 bugfix；
数据库变更任务能命中 database-migration 并升级 L3。
```

## 6. 阶段 E：MCP 工具权限原型

目标：实现工具调用前的权限策略判断，即使暂时不用完整 MCP 服务，也要先有 policy runtime。

任务：

```text
E1. 定义 tool permission policy 数据结构；
E2. 建立 role + level + risk → allowed_tools 映射；
E3. 将 cli.new、cli.approve、schema_check、data_boundary_check 作为第一批工具；
E4. tool_calls 增加 permission_decision 字段；
E5. 高风险工具调用必须要求 approval；
E6. CI 验证 tool_calls 中 permission_policy 不为空。
E7. 将 permission policy 下沉到工具协议网关，未授权时不执行 handler。
E8. 接入外部工具 adapter。
E9. 注册首批真实外部工具 handler。
E10. 接入 MCP Server stdio 外壳。
E11. 声明官方 MCP Python SDK 依赖并暴露 SDK 安装状态。
```

当前状态：

```text
E1 tool permission policy 数据结构已接入 app/chao/permissions.py。
E2 role + level + tool risk 的允许/拒绝判断已接入 evaluate_tool_permission。
E3 cli.new、cli.approve、schema_check、data_boundary_check 已进入第一批工具登记。
E4 tool_calls.permission_decision 已通过 db/migrations/008_tool_calls_permission_decision.sql 落地。
E5 require_tool_permission 已接入，未授权工具调用会被拒绝。
E6 CI 已验证 tool_calls.permission_policy 非空且 permission_decision 非空。
E7 app/chao/tool_gateway.py 已接入协议层拦截入口，denied 时不会执行工具 handler，并返回可写入 tool_calls 的 audit 字段。
E8 app/chao/tool_gateway_server.py 已接入 JSON Lines stdio adapter，支持 health、tools.list、tool.evaluate、tool.execute 和 tool.execute.echo。
E9 app/chao/tool_gateway_handlers.py 已注册 schema_check 与 data_boundary_check，tool.execute 仅在权限允许后调用真实 handler。
E10 app/chao/mcp_server.py 已接入 MCP 风格 stdio JSON-RPC 外壳，支持 initialize、tools/list 和 tools/call。
E11 pyproject.toml 已声明 mcp 依赖，app/chao/mcp_sdk.py 可检测官方 SDK 安装状态。
```

验收：

```text
所有工具调用有 agent_name、tool_name、permission_policy、result_status；
高风险任务不能调用未授权工具；
tool_calls 可按 task_id 查询。
```

## 7. 阶段 F：GitHub Issue / PR 绑定

目标：让 GitHub 成为工程闭环的一部分。

任务：

```text
F1. 新增 github_links 表；
F2. CLI 支持绑定 issue / PR；
F3. PR 模板强制填写 task_code；
F4. CI 检查 PR 是否绑定任务；
F5. 合并后写入 historian_records；
F6. 记录 commit hash、CI run id、PR URL。
```

当前状态：

```text
F1 github_links 表已通过 db/migrations/009_github_links.sql 落地。
F1 最小数据层 app/chao/services/github_links.py 已接入，CLI show 已输出 github_links。
F2 CLI bind-github 已接入，可绑定 issue / pull_request / commit / ci_run。
F3 PR 模板已要求填写 Task Code。
F4 CI 已通过 scripts/check_pr_task_binding.py 检查 PR body 是否包含 Task Code。
F5 scripts/record_github_delivery.py 已可向 historian_records 写入 GitHub 交付记录。
F6 scripts/record_github_delivery.py 已可记录 PR URL、commit hash、CI run URL 到 github_links。
```

验收：

```text
任意 PR 可追溯到 TASK；
任意 TASK 可追溯到 PR / commit / CI；
交付证据进入 artifacts。
```

## 8. 阶段 G：L3 / L4 完整治理

目标：让高风险任务不只是被 approve，而是进入完整治理流程。

任务：

```text
G1. L3 approve 后进入 DESIGNING / REVIEWING / SCHEDULING；
G2. 中书省输出方案 artifact；
G3. 门下省输出审核 artifact；
G4. 户部审查数据 / 依赖 / Secret；
G5. 兵部审查部署 / CI / rollback；
G6. L4 只生成里程碑，不直接执行。
```

当前状态：

```text
G1 approve_task 已将 L3 审批后任务状态从 NEED_CONFIRMATION 推进到 DESIGNING。
G2 approve_task 已在进入 DESIGNING 后生成中书省方案 Markdown artifact，并登记 D1 data_asset。
G3 approve_task 已在生成方案后生成门下省审核 Markdown artifact，并登记 D1 data_asset。
G4 approve_task 已在生成门下省审核后生成户部数据 / 依赖 / Secret 审查 Markdown artifact，并登记 D1 data_asset。
G5 approve_task 已在生成户部审查后生成兵部部署 / CI / rollback 审查 Markdown artifact，并登记 D1 data_asset。
G6 L4 已路由为里程碑规划任务，创建后只生成 l4_milestone_plan，不进入工部执行。
```

验收：

```text
L3 数据库变更有方案、审批、验证、回滚说明；
L4 任务会拆解成多个 L2 / L3 子任务。
```

## 9. 阶段 H：Agent Runner / Sandbox

目标：让工部真正能在受控环境中修改代码。

任务：

```text
H1. 定义 workspace/sandbox 边界；
H2. 实现 branch 创建策略；
H3. 工部只允许改 allowed scope；
H4. 刑部执行验证；
H5. 生成 patch artifact；
H6. 失败回流到工部。
H7. 真实创建 / 检查 codex/ 执行分支；
H8. 引入隔离工作区最小执行流；
H9. 引入 Docker Sandbox 最小执行流。
```

当前状态：

```text
H1 Agent Runner / Sandbox 边界已定义：docs/16-agent-runner-sandbox-boundary-v3.md。
H1 最小策略运行时已接入 app/chao/runner_policy.py，覆盖 allowed scope、forbidden scope、分支前缀、沙箱根和 L4 禁执行规则。
H2 分支创建策略已接入 app/chao/runner_policy.py：执行型任务生成 codex/ 前缀 branch plan，L4 不生成执行分支。
H3 allowed scope 阻断已接入 app/chao/runner_policy.py 与工部节点，越界路径会被拒绝。
H4 刑部验证计划和失败阻断已接入 app/chao/runner_validation.py 与刑部节点。
H5 runner_patch artifact 已接入，记录分支计划、变更范围和验证证据。
H6 runner_failure_feedback artifact 已接入，验证失败会回流给工部且禁止交付。
H7 runner-branch CLI 已接入，默认 dry-run，显式 --apply 才真实创建并切换 codex/ 执行分支。
H8 runner-workspace CLI 已接入，默认 dry-run，显式 --apply 才在 .chao/sandboxes 下创建隔离 git worktree。
H9 runner-sandbox CLI 已接入，默认 dry-run，显式 --apply 才用 Docker 执行 allowlist gate。
```

验收：

```text
Agent 修改发生在分支或沙箱；
无关文件改动会被阻断；
验证失败不能交付。
```

## 10. 阶段 I：Console 可视化

目标：降低使用门槛，用 Web 查看任务、审批、门禁、记录和审计链。

页面：

```text
任务列表；
任务详情；
审批中心；
事件流；
工具调用；
Artifacts；
Data Assets；
Schema / Data Boundary Gate；
CI / PR 绑定；
风险和阻塞。
```

阶段 I 已进入只读 Web Console Alpha，后续继续补齐查询、过滤、空态和必要操作入口。

当前状态：

```text
I1 只读 Console 总览已接入：app/chao/services/console.py 与 CLI console 命令。
I1 输出任务状态统计、等级统计、最近任务、artifact/data_asset 数量和失败工具调用数量。
I2 只读任务详情视图已接入：CLI console-task 命令输出单任务审计链摘要。
I3 只读审批中心已接入：CLI console-approvals 命令输出待确认任务队列。
I4 只读审计视图已接入：CLI console-audit 命令输出事件、工具调用、Artifacts、Data Assets、GitHub links。
I5 只读 Gate 视图已接入：CLI console-gates 命令输出 gate_results、工具权限和数据边界摘要。
I6 只读风险视图已接入：CLI console-risks 命令输出阻塞任务、失败 gate、工具风险、数据边界风险和 GitHub 风险。
I7 Runner 失败回流视图已接入：CLI console-risks 命令输出 runner_failure_feedback artifact。
I8 Web Console JSON API 基座已接入：CLI web-console 命令提供只读 console API。
I9 Web Console 任务详情 API 已接入：`/api/console/tasks/{task_code}` 返回单任务审计链。
I10 Web Console 最小页面已接入：根路径展示 overview、risks 和任务详情查询。
I11 Web Console 最近任务列表已接入：根路径可点击最近任务加载详情。
I12 Web Console 审批队列已接入：根路径展示 NEED_CONFIRMATION 任务并可点击详情。
I13 Web Console 风险明细已接入：根路径展示阻塞任务、Runner 失败、失败 gate、工具风险和 GitHub 风险。
I14 Web Console Gate / Data Boundary 面板已接入：根路径展示 gate 状态、工具权限审计和数据边界审计。
I15 Web Console 审计链面板已接入：根路径展示事件、工具调用、Artifacts、Data Assets 和 GitHub links。
I16 Web Console 刷新控制已接入：根路径可调整查询数量并手动刷新页面数据。
I17 Web Console 任务详情摘要已接入：根路径展示任务基础字段和审计对象计数。
I18 Web Console 任务详情审计表已接入：根路径展示单任务事件、工具调用、Artifacts、Data Assets、GitHub links 和 gate 结果。
I19 Web Console 页面导航已接入：根路径可快速跳转各只读面板。
I20 Web Console 任务详情深链接已接入：根路径支持 URL task 参数自动加载任务详情。
I21 Web Console 任务详情链接已接入：加载任务后可直接复制当前任务 URL。
I22 Web Console 任务搜索 / 状态过滤 / 等级过滤已接入：根路径支持筛选 recent tasks 并保留 URL query。
I23 Web Console 空态 / 错误态已接入：API 数据读取失败返回 503，页面显示分面板可读提示。
产品化 Web UI、审批写操作和复杂过滤尚未实现。
```

## 11. 近期推荐任务队列

按当前进度，建议接下来优先做：

```text
1. 官方 MCP SDK 客户端联调；
2. 真实 LLM 调用 client 与模型调用审计；
3. Skills 自动读取、执行和交付记录闭环。
```
