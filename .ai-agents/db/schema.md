# 数据库 Schema 说明 v3

## 核心表

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
```

## 设计原则

```text
任务状态结构化；
工具调用可审计；
史官记录可检索；
Markdown 和 PostgreSQL 双写；
CI / PR / Issue 可关联。
```

## 数据边界扩展表

新增三类表：

```text
data_assets：记录数据资产、分级、主存储位置、是否脱敏、是否允许向量化。
storage_policies：记录不同分级数据允许和禁止的存储位置。
artifact_records：记录构建产物、截图、报告、长日志等 artifact 的路径、哈希、访问权限和保留期限。
```

原则：数据库只保存元数据、摘要、引用和哈希，不保存 Secret、生产数据、个人隐私原文和大体积二进制。
