# 朝 v3 落地实施方案

## 1. 落地原则

v3 落地必须遵守：

```text
先仓库原生，后平台化；
先模板和门禁，后自动编排；
先人工可控，后半自动；
先 L1 / L2，后 L3 / L4；
先记录事实，后做知识检索；
先本地 CLI，后 Web Console。
```

## 2. 第一阶段：文档与仓库制度落地

目标：让任何项目接入 `.ai-agents` 后，立即具备任务定级、角色边界、验证和记录规则。

交付：

```text
.ai-agents/AGENTS.md
.ai-agents/chao-v3.md
.ai-agents/router/*.md
.ai-agents/roles/*.md
.ai-agents/modes/*.md
.ai-agents/templates/*.md
.ai-agents/records/*.md
.ai-agents/gates/*.md
```

验收标准：

```text
1. 新任务能套用 task-route 模板；
2. 能判定 L1 / L2 / L3 / L4；
3. 能列出风险类型；
4. 能列出需要启用和不启用的角色；
5. 能形成交付模板；
6. 能记录 decisions / validations。
```

## 3. 第二阶段：CLI 最小入口

目标：提供本地命令行入口，避免一切流程停留在文档。

建议命令：

```bash
chao init
chao new "修复用户列表分页异常"
chao route TASK-20260509-001
chao status TASK-20260509-001
chao record decision TASK-20260509-001
chao validate TASK-20260509-001
chao archive TASK-20260509-001
```

交付：

```text
CLI；
任务编号生成；
路由结果写入 records/current.md；
验证结果写入 records/validations.md；
PR Checklist 输出。
```

验收标准：

```text
1. 能从命令创建任务；
2. 能生成任务路由 Markdown；
3. 能生成执行模板；
4. 能写入史官记录；
5. 能读取 AGENTS.md 和规则文件。
```

## 4. 第三阶段：GitHub / CI 工程门禁

目标：让“没有验证不得交付”落到工具。

交付：

```text
GitHub Actions 基础流水线；
PR Template；
Secret Scan；
Dependency Review；
typecheck / lint / test / build；
PR Comment 验证摘要。
```

验收标准：

```text
1. PR 必须关联任务编号；
2. CI 失败不能合并；
3. Secret Scan 失败不能合并；
4. 新增依赖必须说明原因；
5. L3 任务必须有回滚说明。
```

## 5. 第四阶段：PostgreSQL 控制平面

目标：从 Markdown 记录升级为结构化状态。

核心表：

```text
tasks；
task_routes；
task_states；
task_events；
agent_runs；
tool_calls；
historian_records；
confirmations；
gate_results；
github_links；
risks；
blockers；
artifacts。
```

交付：

```text
schema.sql；
任务状态读写；
路由结果持久化；
门禁结果持久化；
史官记录持久化；
Markdown 双写。
```

验收标准：

```text
1. 每个任务有唯一 task_code；
2. 每次状态变化有 task_event；
3. 每次工具调用有 tool_call；
4. 每次验证有 gate_result；
5. 每条重要记录能回查到任务。
```

## 6. 第五阶段：LangGraph 状态机

目标：让任务从文档流程进入可执行状态机。

第一版只实现 L1 / L2：

```text
RAW
→ ROUTING
→ CLASSIFIED
→ CONTEXT_PREPARED
→ IMPLEMENTING
→ VALIDATING
→ INTEGRATING
→ DELIVERED / FAILED_VALIDATION
```

L3 / L4 暂时只做规划，不做全自动执行。

验收标准：

```text
1. L1 可自动走完路由、实现、验证、记录；
2. L2 可插入中书省简案；
3. 验证失败能回流工部；
4. 需要确认时能进入 WAITING_HUMAN_APPROVAL；
5. 每个节点输入输出可追踪。
```

## 7. 第六阶段：MCP 工具权限层

目标：Agent 不直接访问系统资源，所有工具调用受权限约束。

第一批 MCP：

```text
filesystem；
shell；
github；
postgres；
obsidian / markdown；
browser-docs；
secret-scan；
dependency-review。
```

验收标准：

```text
1. L1 不能调用部署类工具；
2. 工部不能直接修改生产配置；
3. 刑部默认只读代码和执行验证；
4. 户部可执行依赖审查和 Secret 检查；
5. 兵部才可操作部署和回滚相关工具；
6. 所有工具调用进入 tool_calls 表。
```

## 8. 第七阶段：Skills 能力包

目标：把可复用开发能力沉淀为 Skill，而不是不断新增 Agent。

第一批 Skill：

```text
bugfix；
frontend-feature；
api-development；
database-migration；
docs-generation；
release-validation；
security-review。
```

验收标准：

```text
1. 每个 Skill 有 SKILL.md；
2. 每个 Skill 有触发条件、输入、步骤、门禁、输出；
3. 路由器能选择 Skill；
4. 工部 / 刑部能按 Skill 执行；
5. Skill 能被多个项目复用。
```

## 9. 第八阶段：Console 可视化

目标：给人类查看状态、审批 A 级事项、查看记录和门禁。

暂缓到前七阶段稳定后再做。

核心页面：

```text
任务列表；
任务详情；
状态流转；
审批中心；
门禁结果；
史官记录；
风险和阻塞；
Agent 执行日志。
```

## 10. 里程碑建议

| 里程碑 | 内容 | 优先级 |
|---|---|---|
| M0 | 文档包和目录规范 | 必做 |
| M1 | CLI + Markdown 记录 | 必做 |
| M2 | GitHub Actions 门禁 | 必做 |
| M3 | PostgreSQL 控制平面 | 必做 |
| M4 | L1 / L2 状态机 | 必做 |
| M5 | MCP 工具权限 | 必做 |
| M6 | Skills 能力包 | 必做 |
| M7 | L3 / L4 治理 | 后续 |
| M8 | Console | 后续 |

## 11. 第一版 MVP 范围

第一版只做：

```text
1. .ai-agents 目录；
2. AGENTS.md；
3. 路由器模板；
4. 工部 / 刑部角色；
5. L1 / L2 工作流；
6. 史官 records；
7. PR Template；
8. GitHub Actions：typecheck、build、secret scan；
9. bugfix 和 frontend-feature 两个 Skill。
```

不做：

```text
复杂 Web Console；
全自动多 Agent；
跨项目统一平台；
生产部署自动化；
复杂权限系统；
独立向量数据库。
```

## 11. 数据存储边界落地步骤

第一阶段必须同时落地数据边界，而不是后补：

```text
1. 建立 data_storage_boundary 规则文档；
2. 在 task_routes 中增加 data_classification / storage_policy 字段；
3. 在 context_chunks 中增加 source_type、data_classification、redacted、ingest_allowed；
4. 在 artifacts 中增加 artifact_type、storage_uri、retention_policy、checksum；
5. 在 PR Checklist 中加入数据边界检查；
6. 在 Secret Scan 之外增加 .env / 日志 / artifact 检查；
7. pgvector ingest 只能读取白名单路径；
8. 史官只写关键事实摘要，不写完整工具日志。
```

MVP 阶段的最低要求：

```text
PostgreSQL 存状态，不存 Secret；
Git 存代码，不存 .env；
pgvector 只索引 docs、.ai-agents、ADR 和脱敏史官摘要；
CI 日志只保存链接和摘要；
artifact 只保存路径、哈希和保留策略。
```
