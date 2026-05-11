# AGENTS.md — chao-platform 仓库级智能体规则

> 本文件是 Codex / Agent 在本仓库工作的第一入口。进入任务前必须先阅读本文件，再按需阅读 `.ai-agents/AGENTS.md`、`docs/00-chao-v3-design-overview.md`、`docs/01-chao-principles-v3.md`、`docs/11-data-storage-boundary-v3.md`。

## 1. 项目定位

本仓库是“朝”v3 的本地 MVP / Alpha 运行内核，目标是把 AI 协助开发从“聊天生成代码”推进到：

```text
需求可追溯；
任务可路由；
权限可控制；
执行可隔离；
结果可验证；
失败可回流；
知识可沉淀；
交付可复盘。
```

运行骨架：

```text
CLI / GitHub Actions
+ LangGraph 状态机
+ PostgreSQL 控制平面
+ Markdown 史官双写
+ pgvector 检索基础
+ task_events / tool_calls / artifacts / data_assets 审计链
+ data-boundary / schema / secret scan / pytest / ruff 工程门禁
```

## 2. 强制执行规则

任何开发任务必须遵守：

```text
凡任务，先路由；
凡风险，必归口；
凡 A 级，必须确认；
凡修改，必须验证；
凡失败，必须回流；
凡交付，必须有证据；
凡数据，先分级再存储；
凡工具调用，必须可审计。
```

禁止：

```text
不得未定级直接改代码；
不得未确认 A 级事项直接执行；
不得新增未审查依赖；
不得修改无关文件；
不得无验证宣称完成；
不得吞异常或返回假成功；
不得读取、输出或提交真实 Secret；
不得提交 .env、data/postgres、logs、.venv；
不得把生产数据、隐私、Token、私钥写入 PostgreSQL、Markdown、日志或向量库；
不得绕过 CI / PR / Review 合入高风险改动。
```

## 3. Codex 工作方式

Codex 接任务后先执行：

```bash
pwd
git status
./scripts/check.sh
```

然后根据任务类型阅读相关文件：

```text
总规则：AGENTS.md、.ai-agents/AGENTS.md
架构：docs/00-chao-v3-design-overview.md、docs/06-technical-architecture-v3.md
朝纲：docs/01-chao-principles-v3.md
数据边界：docs/11-data-storage-boundary-v3.md、.ai-agents/rules/data-storage-boundary.md
任务规则：.ai-agents/router/*
门禁规则：.ai-agents/gates/*
角色职责：.ai-agents/roles/*
Skills：.ai-agents/skills/*/SKILL.md
当前进度：docs/12-current-project-progress-v3-alpha.md
后续计划：docs/13-next-development-plan-v3.md
```

如果任务路由结果包含 `required_skill_paths`，执行前必须逐一阅读对应
`SKILL.md`，并在交付说明或 PR 中列出实际使用的 Skill。

## 4. 修改约束

### 4.1 数据库变更

涉及数据库结构时必须：

```text
1. 新增 db/migrations/xxx_*.sql；
2. 同步追加到 db/init/001_init.sql；
3. 更新 scripts/schema_check.py；
4. 本地应用迁移并验证；
5. 运行 ./scripts/check.sh；
6. CI 必须通过。
```

### 4.2 数据边界变更

涉及以下情况必须按 L3 / A 级处理：

```text
新增存储位置；
新增向量化来源；
新增 Secret 注入方式；
改变日志 / artifact 保留策略；
新增对象存储或外部知识库；
处理生产数据或个人隐私。
```

必须保证：

```bash
uv run python scripts/data_boundary_check.py
uv run python scripts/schema_check.py
```

均通过。

### 4.3 代码变更

每次有效代码变更至少运行：

```bash
uv run ruff check app tests main.py --fix
uv run ruff format app tests main.py
uv run pytest -q
./scripts/check.sh
```

## 5. 当前优先级

当前项目处于：

```text
chao-v3-local-mvp-alpha
```

优先继续完成：

```text
P0：data_assets 与任务详情、CI 的闭环；
P0：Codex 接管所需文档入仓；
P1：pgvector ingest 白名单与脱敏索引；
P1：Skills 最小执行机制；
P1：MCP / tool permission policy 原型；
P2：GitHub Issue / PR 绑定；
P2：Agent Runner / Sandbox；
P3：Web Console。
```

## 6. 交付格式

Codex 完成任务后必须输出：

```text
1. 修改文件清单；
2. 每个文件修改目的；
3. 执行过的验证命令；
4. 验证结果；
5. 未覆盖内容；
6. 残余风险；
7. 是否建议提交 / 推送。
```
