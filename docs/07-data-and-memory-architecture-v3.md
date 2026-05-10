# 数据与记忆架构 v3

## 1. 总原则

v3 的数据与记忆系统分为五类：

```text
运行控制数据：任务状态、路由、事件、Agent 执行、工具调用、门禁结果。
事实归档数据：史官记录、关键决策、确认事项、验证结论、事故复盘。
工程证据数据：PR、CI、diff、artifact、日志摘要、构建结果。
知识检索数据：文档、ADR、接口说明、Bug 经验、脱敏史官摘要。
敏感受控数据：Secret、Token、私钥、生产数据、个人隐私。
```

运行控制数据以 PostgreSQL 为主。  
事实归档数据以 PostgreSQL + Markdown 双写为主。  
工程证据数据以 GitHub / CI / Artifact Store 为主，PostgreSQL 只存索引和摘要。  
知识检索数据以 Markdown + pgvector 为主。  
敏感受控数据只能存在于 Secret Manager / GitHub Secrets / 受控生产系统。

## 2. 数据分级

| 分级 | 名称 | 示例 | 默认存储 | 是否可向量化 |
|---|---|---|---|---|
| D0 | 公开知识 | README、公开说明 | Git / Markdown / pgvector | 可以 |
| D1 | 内部工程知识 | ADR、接口文档、史官摘要 | Git / PostgreSQL / pgvector | 脱敏后可以 |
| D2 | 敏感工程数据 | CI 日志、部署记录、权限设计 | PostgreSQL 摘要 / GitHub / Artifact Store | 默认不可 |
| D3 | 严格敏感数据 | Secret、Token、私钥、生产数据、个人隐私 | Secret Manager / GitHub Secrets / 生产库 | 禁止 |
| D4 | 临时执行数据 | scratchpad、构建缓存、工具原始输出 | Workspace / Sandbox / CI 临时目录 | 禁止 |

## 3. 存储边界

| 存储位置 | 应该存什么 | 禁止存什么 |
|---|---|---|
| PostgreSQL | task、route、state、event、agent_run、tool_call 摘要、gate_result、confirmation、risk、blocker、artifact 元数据 | Secret 明文、完整源码、大体积日志、生产数据、隐私、完整 scratchpad |
| Git / Markdown | 源码、制度文件、ADR、正式文档、史官归档摘要 | .env、Token、私钥、生产数据导出、未脱敏日志、构建产物 |
| `.ai-agents/records` | 关键事实、人类可读归档、决策、验证摘要、事故复盘 | 低价值 trace、Secret、完整日志、无关聊天记录 |
| pgvector | 已批准文档块、脱敏史官摘要、ADR、接口说明、Bug 经验 | Secret、生产数据、隐私、完整聊天、CI 原始日志、构建产物 |
| Obsidian | 架构思考、制度演进、ADR 草案、复盘 | 运行状态、未脱敏日志、Secret、生产数据 |
| GitHub Issue / PR / Actions | 任务讨论、PR diff、CI 结果、Review、工程证据 | Secret 明文、生产数据、私钥 |
| Artifact Store | 截图、报告、构建产物、长日志归档 | Secret 明文、未授权生产数据 |
| Workspace / Sandbox | 临时代码、测试输出、构建缓存、scratchpad、patch 草稿 | 长期事实源、正式决策源、Secret 明文持久化 |
| Secret Manager / GitHub Secrets | API Key、Token、私钥、生产密码 | 普通文档、任务状态、业务说明 |

## 4. PostgreSQL 核心表

```text
tasks
task_routes
task_states
task_events
agent_runs
tool_calls
historian_records
confirmations
gate_results
github_links
context_chunks
embeddings
risks
blockers
artifacts
data_assets
storage_policies
```

PostgreSQL 允许存敏感事项的引用，不允许存敏感明文：

```text
允许：secret_name、secret_scope、rotation_required、rotation_at、output_hash、artifact_uri、redacted_summary。
禁止：secret_value、.env 原文、私钥、生产数据导出、个人隐私原文。
```

## 5. 史官记录类型

| 类型 | 内容 | 示例 | 存储边界 |
|---|---|---|---|
| trace | 临时尝试摘要 | 某命令失败 | PostgreSQL，可短期保存 |
| progress | 阶段进度 | 已完成实现 | PostgreSQL + 必要 Markdown |
| decision | 决策 | 选择 PostgreSQL + pgvector | PostgreSQL + Markdown，长期保存 |
| change | 变更 | 新增环境变量名 | PostgreSQL + Markdown，不存真实值 |
| validation | 验证 | typecheck 通过 | PostgreSQL + 必要证据链接 |
| incident | 事故 | Secret 泄露、部署失败 | PostgreSQL + Markdown + 受控证据 |

## 6. Markdown 双写规则

必须双写：

```text
A 级确认；
技术选型；
数据结构变化；
权限变化；
部署和回滚；
验证结论；
事故复盘；
数据边界变更。
```

可只写数据库：

```text
临时工具调用；
低价值 trace；
重复验证日志；
中间状态变化；
可由 GitHub / CI 链接追溯的长日志。
```

## 7. 上下文投喂策略

| 等级 | 上下文 |
|---|---|
| L1 | 当前需求 + 相关文件片段 + 必要规范 + 最近验证结果 |
| L2 | 原始需求 + 简案 / 契约 + 相关代码摘要 + 当前任务状态 |
| L3 | 确认记录 + 架构文档 + 决策记录 + 数据 / 权限 / 部署历史 |
| L4 | 当前里程碑目标 + 项目级摘要 + 本阶段直接相关历史 |

禁止：

```text
默认投喂全部历史；
让旧结论覆盖新需求；
让无关历史污染当前任务；
把聊天记录当作唯一事实源；
把 Secret、生产数据、完整日志投喂给非授权 Agent。
```

## 8. pgvector 检索边界

第一版允许索引：

```text
.ai-agents/**/*.md；
docs/**/*.md；
README.md；
CHANGELOG.md；
ADR；
Obsidian 导出的已批准 Markdown；
GitHub Issue / PR 摘要；
脱敏史官 records 摘要。
```

禁止索引：

```text
node_modules；
dist / build；
大体积日志；
包含 Secret 的文件；
.env；
生产数据；
用户隐私；
无结构的长聊天记录；
Agent scratchpad。
```

进入向量库前必须记录：

```text
source_uri；
source_hash；
data_classification；
redacted；
ingest_allowed；
retention_policy；
created_by。
```

## 9. 数据写入决策规则

任何 Agent 在写入数据前必须确认：

```text
这是什么数据；
分级是什么；
主存储位置是什么；
是否允许副本；
是否允许向量化；
是否包含 Secret / 隐私 / 生产数据；
是否需要脱敏；
保留期限是什么；
删除方式是什么；
责任归口是谁。
```

无法确认时，不得写入长期存储。

## 10. 记录质量要求

好的史官记录应满足：

```text
事实明确；
来源明确；
任务编号明确；
结论和证据分开；
存储位置清楚；
数据分级清楚；
不夸大；
不遗漏失败；
不泄露 Secret；
能被后续 Agent 检索复用。
```
