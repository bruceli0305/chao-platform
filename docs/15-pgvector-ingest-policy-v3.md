# pgvector Ingest Policy v3

> 本文定义 `chao-platform` 第一版 pgvector 知识 ingest 的白名单、禁止范围、脱敏要求和审计要求。
> 本阶段只落地策略，不实现 ingest 脚本，不改变数据库 schema。

## 1. 目标

第一版 pgvector ingest 只服务于 Agent 检索项目规则、架构说明、史官摘要和工程经验。

目标：

```text
只索引低风险、可复用、可审计的工程知识；
只从明确白名单读取；
只写入脱敏后的知识块；
只保存来源、哈希、分级、脱敏状态和保留策略；
禁止为了检索方便扩大数据边界。
```

## 2. 数据分级

允许进入 ingest 候选集的数据最低必须可归为 D0 或 D1。

```text
D0：公开知识，例如 README、公开文档、公开架构说明。
D1：内部工程知识，例如 ADR、接口说明、Agent 规范、脱敏史官摘要。
```

以下分级默认不得进入向量库：

```text
D2：敏感工程数据，除非另有专项审批和脱敏方案。
D3：Secret、Token、私钥、生产数据、个人隐私，禁止进入。
D4：临时执行数据、scratchpad、工具原始输出，禁止进入。
```

## 3. Ingest 白名单

第一版只允许读取以下路径：

```text
AGENTS.md
README.md
CHANGELOG-v3.md
docs/**/*.md
.ai-agents/**/*.md
```

其中 `.ai-agents/records/tasks/TASK-*.md` 只能 ingest 脱敏摘要，不能 ingest 原始长日志、工具完整输出、未确认聊天记录或含敏感信息的内容。

## 4. 禁止 Ingest 范围

以下路径和内容禁止进入 ingest：

```text
.env
.env.*
.venv/**
data/**
logs/**
node_modules/**
dist/**
build/**
__pycache__/**
.pytest_cache/**
CI 原始长日志
构建产物
测试输出目录
Agent scratchpad
工具原始长输出
数据库备份
生产数据导出
个人隐私数据
Secret / Token / 私钥 / 密码
```

即使文件位于白名单路径内，只要内容命中 Secret、生产数据、个人隐私或未脱敏长日志，也必须阻断 ingest。

## 5. Chunk 规则

第一版 chunk 必须保持可追溯和可删除：

```text
每个 chunk 必须记录 source_uri；
每个 chunk 必须记录 source_hash；
每个 chunk 必须记录 source_type；
每个 chunk 必须记录 data_classification；
每个 chunk 必须记录 redacted / desensitized；
每个 chunk 必须记录 ingest_allowed；
每个 chunk 必须记录 retention_policy；
每个 chunk 必须记录 created_by；
```

禁止只保存向量而丢失来源元数据。

## 6. 脱敏要求

进入 pgvector 前必须完成：

```text
Secret pattern scan；
.env / 私钥 / Token 检查；
生产数据和个人隐私检查；
任务记录脱敏检查；
长日志裁剪为摘要；
失败输出只保留摘要、哈希或证据链接；
```

无法确认是否敏感时，默认不得 ingest。

## 7. Data Asset 登记

每次 ingest 必须登记或更新 data_assets：

```text
asset_name：来源路径或任务记录编号；
asset_type：context_chunk_source / historian_summary / documentation；
classification：D0 或 D1；
primary_storage：Git / Markdown；
allowed_copies：PostgreSQL、pgvector；
forbidden_storages：Secret Manager、logs、unapproved artifact；
allow_vectorization：true；
desensitized：true；
task_id：如来源为任务记录则必须关联；
notes：说明来源、脱敏策略和保留策略。
```

## 8. 工程门禁

实现 ingest 前必须补齐以下门禁：

```text
scripts/data_boundary_check.py 检查禁止路径不会被 ingest；
scripts/schema_check.py 检查 context_chunks 必要元数据字段；
pytest 覆盖白名单、禁止路径、Secret 阻断、任务摘要 ingest；
CI 执行 ingest dry-run 和最小写入 smoke test；
```

当前 dry-run 命令：

```bash
uv run python scripts/ingest_markdown.py --pretty
```

当前写入命令：

```bash
uv run python scripts/ingest_markdown.py --write --pretty
```

当前只读搜索命令：

```bash
uv run python scripts/search_context.py "数据边界" --pretty
```

## 9. 阶段拆分

```text
C1：设计 ingest 白名单，已由本文定义。
C2：明确禁止 ingest 范围，已由本文定义。
C3：设计 context_chunks 元数据字段，已落地到 db/migrations/007_context_chunks_metadata.sql。
C4：实现 scripts/ingest_markdown.py，dry-run 已接入，不写数据库、不生成 embedding。
C5：实现 scripts/search_context.py，只读搜索骨架已接入。
C6：将 ingest 结果写入 context_chunks，并同步登记 data_assets。
C7：增加 schema_check 和 data_boundary_check 对 ingest 的校验，白名单 / 禁止路径基础校验与 CI 写入 smoke test 已接入。
```

## 10. 结论

第一版 pgvector ingest 必须以白名单为入口，以数据边界为硬门禁，以来源元数据为审计基础。
任何新增 ingest 来源、放宽禁止路径、处理 D2 / D3 / D4 数据，
必须重新路由为 L3 并完成 A 级确认。
