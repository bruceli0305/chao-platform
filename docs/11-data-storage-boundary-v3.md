# 数据存储边界 v3

> 本文是“朝”v3 的强制性数据边界规范。任何 Agent、Mode、Skill、MCP 工具、工作流和工程门禁都必须遵守本文。  
> 核心目标：**每一种数据都有唯一主存储位置、允许副本、禁止位置、保留期限和责任归口。**

---

## 1. 最高原则

```text
数据先分类，再存储；
事实可入库，Secret 不入库；
代码归仓库，状态归数据库；
证据可索引，原文不滥存；
知识可向量化，敏感不向量化；
临时工作留痕，临时数据不过夜；
存储位置变更，必须重新路由和审核。
```

v3 中，PostgreSQL 是**运行控制平面**，不是万能数据湖。  
Git 是**代码和制度文档源**，不是运行状态库。  
Obsidian 是**人类知识图谱**，不是任务事实源。  
pgvector 是**检索索引**，不是原始资料库。  
Secret Manager / GitHub Secrets / 本地 `.env` 是**密钥唯一合法存储边界**。

---

## 2. 数据分级

| 分级 | 名称 | 示例 | 默认存储 | 是否可向量化 | 处理原则 |
|---|---|---|---|---|---|
| D0 | 公开知识 | README、公开文档、公开架构说明 | Git / Markdown / pgvector | 可以 | 可检索、可归档 |
| D1 | 内部工程知识 | ADR、接口说明、Agent 规范、史官摘要 | Git / PostgreSQL / pgvector | 可以，但需脱敏 | 作为项目知识长期保存 |
| D2 | 敏感工程数据 | CI 日志、部署记录、故障复盘、权限设计 | PostgreSQL 摘要 / GitHub / 私有对象存储 | 默认不可，审批后脱敏索引 | 只存必要摘要和证据指针 |
| D3 | 严格敏感数据 | Secret、Token、私钥、生产数据、个人隐私 | Secret Manager / GitHub Secrets / 受控生产库 | 禁止 | 只允许存引用名、哈希、轮换记录 |
| D4 | 临时执行数据 | Agent scratchpad、工具原始输出、构建中间物、sandbox 文件 | Workspace / Sandbox / CI 临时目录 | 禁止 | 默认短期清理，不进入长期记忆 |

---

## 3. 存储位置边界总表

| 存储位置 | 应该存什么 | 不得存什么 | 主责任方 |
|---|---|---|---|
| PostgreSQL | task、route、state、event、agent_run、tool_call 摘要、gate_result、confirmation、risk、blocker、artifact 元数据 | Secret 明文、完整源码副本、大体积日志、生产数据、个人隐私、未经确认的长聊天全文 | 尚书省 + 史官 + 户部 |
| Git 仓库 | 源码、`.ai-agents` 制度文件、Markdown 记录、ADR、模板、Skills | `.env`、Token、私钥、生产数据导出、大体积构建产物、运行时状态流水 | 工部 + 吏部 + 礼部 |
| `.ai-agents/records` | 关键事实、人类可读归档、决策、验证摘要、事故复盘 | 低价值 trace、Secret、完整日志、无关聊天记录 | 史官 |
| pgvector | 已批准文档块、史官摘要、ADR、接口说明、Bug 修复经验 | Secret、生产数据、原始聊天全文、大体积日志、未脱敏 CI 输出 | 史官 + 户部 |
| Obsidian | 架构思考、长期知识、制度演进、复盘、ADR 草案 | 运行状态、未脱敏日志、Secret、生产数据 | 皇帝 / 人类维护者 |
| GitHub Issue / PR / Actions | 任务讨论、PR diff、CI 结果、Review、工程证据 | Secret 明文、生产数据、私钥 | 尚书省 + 兵部 |
| 对象存储 / Artifact Store | 截图、报告、构建产物、长日志归档 | Secret 明文、未授权生产数据 | 兵部 + 户部 |
| Workspace / Sandbox | 临时代码修改、命令输出、构建缓存、Agent scratchpad | 长期事实源、正式决策源、Secret 明文持久化 | 工部 + 刑部 |
| Secret Manager / GitHub Secrets | API Key、Token、私钥、生产密码 | 普通文档、任务状态、业务说明 | 户部 + 兵部 |

---

## 4. PostgreSQL 存储边界

PostgreSQL 只存“运行控制与审计事实”，包括：

```text
tasks：任务基本信息；
task_routes：路由、等级、风险、启用角色、门禁；
task_events：状态变化和关键事件；
agent_runs：Agent 执行摘要；
tool_calls：工具调用摘要、权限策略、输出哈希；
historian_records：史官结构化事实；
confirmations：A / B / C 确认事项；
gate_results：门禁结果摘要；
github_links：Issue / PR / Commit / CI 指针；
artifacts：产物元数据、路径、哈希、保留策略；
context_chunks：可检索文本块元数据；
embeddings：向量索引；
risks / blockers：风险和阻塞项。
```

PostgreSQL 禁止存：

```text
Secret 明文；
.env 内容；
私钥；
生产数据库导出；
用户隐私原文；
完整源码镜像；
完整 CI 长日志；
完整 Agent scratchpad；
未经确认的长聊天记录；
大体积二进制文件。
```

允许存敏感事项的**引用**：

```text
secret_name：如 GITHUB_TOKEN、OPENAI_API_KEY；
secret_scope：repo / org / env；
rotation_required：是否需要轮换；
rotation_at：轮换时间；
output_hash：输出哈希；
artifact_uri：产物路径；
redacted_summary：脱敏摘要。
```

---

## 5. Git / Markdown 存储边界

Git 是代码与制度源，应该存：

```text
源码；
测试；
配置模板；
.env.example；
AGENTS.md；
.ai-agents 规则；
Skills；
ADR；
正式文档；
史官归档摘要。
```

Git 禁止存：

```text
.env；
真实 Token；
真实私钥；
生产数据；
数据库备份；
未脱敏日志；
大体积构建产物；
Agent 临时 scratchpad。
```

`.ai-agents/records` 只能保存**关键事实摘要**，不保存低价值流水。

---

## 6. Secret 存储边界

Secret 只允许存在于：

```text
GitHub Secrets；
云厂商 Secret Manager；
本地开发机未提交的 .env；
受控部署环境变量；
受控生产配置中心。
```

任何 Agent 不得：

```text
读取后输出 Secret 明文；
把 Secret 写入 PostgreSQL；
把 Secret 写入 Markdown；
把 Secret 写入日志；
把 Secret 写入 pgvector；
把 Secret 写入 Issue / PR 评论；
把 Secret 编进构建产物。
```

允许记录：

```text
Secret 名称；
用途；
所属环境；
是否存在；
是否轮换；
最后轮换时间；
权限范围；
脱敏校验结果。
```

---

## 7. pgvector / 检索索引边界

pgvector 只能索引：

```text
已确认的项目文档；
脱敏后的史官摘要；
ADR；
接口说明；
架构说明；
Bug 修复经验；
测试策略；
发布说明。
```

禁止索引：

```text
Secret；
.env；
生产数据；
用户隐私；
完整聊天全文；
完整 CI 原始日志；
构建产物；
node_modules / dist / build；
临时 scratchpad。
```

进入向量库前必须经过：

```text
1. 数据分级；
2. 脱敏检查；
3. 来源记录；
4. chunk 范围确认；
5. 可删除标记；
6. 版本号或来源 hash。
```

---

## 8. 临时执行数据边界

Workspace / Sandbox / CI 临时目录可以保存：

```text
临时代码修改；
构建缓存；
测试输出；
工具原始输出；
Agent scratchpad；
patch 草稿；
截图临时文件。
```

但这些数据默认不是长期事实源。

必须长期保留时，只允许转存为：

```text
脱敏摘要；
输出哈希；
artifact_uri；
PR 链接；
CI 链接；
验证结论；
失败原因摘要。
```

---

## 9. 聊天记录与原始需求边界

用户的原始需求可以进入 `tasks.raw_request`。  
但完整聊天记录不得默认进入长期数据库或向量库。

允许长期保存的是：

```text
已确认需求；
A 级确认事项；
关键决策；
范围变更；
验收标准；
失败和回流原因；
最终交付结论。
```

不得长期保存的是：

```text
无关闲聊；
重复讨论；
未经确认的中间猜测；
包含敏感信息的原始文本；
Agent 内部 scratchpad。
```

---

## 10. 数据写入决策规则

任何 Agent 在写入数据前必须回答：

```text
1. 这是什么数据？
2. 分级是 D0 / D1 / D2 / D3 / D4 哪一类？
3. 主存储位置是什么？
4. 是否允许副本？
5. 是否允许向量化？
6. 是否包含 Secret / 隐私 / 生产数据？
7. 是否需要脱敏？
8. 保留期限是什么？
9. 删除方式是什么？
10. 责任归口是谁？
```

无法回答时，不得写入长期存储。

---

## 11. 任务等级与数据边界升级

| 情况 | 最低等级 | 必须启用 | 说明 |
|---|---|---|---|
| 只新增普通文档 | L1 / L2 | 礼部按需 | 不涉及敏感数据 |
| 新增 PostgreSQL 表 | L3 | 中书省 + 户部 + 门下省 | 改变控制平面 |
| 新增向量索引来源 | L3 | 史官 + 户部 + 门下省 | 可能引入敏感数据 |
| 新增 Secret | L3 | 户部 + 兵部 + 门下省 | 必须确认注入边界 |
| 改变日志保留策略 | L2 / L3 | 户部 + 兵部 | 视敏感程度升级 |
| 引入对象存储 | L3 | 户部 + 兵部 + 门下省 | 涉及成本、权限、生命周期 |
| 存储生产数据 | L3 / 阻塞 | 户部 + 门下省 + 皇帝确认 | 默认禁止，必须专项审批 |
| Secret 泄露 | 高风险阻断 | 户部 + 兵部 + 刑部 + 门下省 | 停止执行，进入事故流程 |

---

## 12. 各角色边界责任

| 角色 | 数据边界责任 |
|---|---|
| 任务路由器 | 判断任务是否涉及存储位置、数据分级、Secret、生产数据、向量化 |
| 史官 | 只记录关键事实；不得把流水、Secret、原始长日志写入长期记录 |
| 中书省 | 设计数据模型、存储位置、生命周期、删除策略 |
| 门下省 | 审核是否越界存储、是否过度采集、是否错误向量化 |
| 尚书省 | 调度执行时明确允许写入位置和禁止写入位置 |
| 工部 | 实现时不得把数据写到错误边界，不得为了方便落库敏感信息 |
| 刑部 | 验证存储边界、脱敏、日志、Secret Scan、越权访问 |
| 户部 | 管依赖、配置、数据库、成本、Secret、存储资源 |
| 兵部 | 管部署、CI、环境变量注入、artifact、日志保留、回滚 |
| 礼部 | 文档不得暴露敏感信息，发布说明不得泄露内部细节 |
| 吏部 | 维护规则、Agent 权限和越权处理 |

---

## 13. 工程门禁

涉及数据边界的任务，至少执行：

```text
secret scan；
.env / config 检查；
日志脱敏检查；
artifact 内容检查；
pgvector ingest 白名单检查；
数据库 schema review；
权限和最小化写入检查。
```

PR Checklist 必须增加：

```text
- [ ] 已标明新增 / 修改的数据类型；
- [ ] 已标明主存储位置；
- [ ] 未把 Secret / 生产数据 / 隐私写入 PostgreSQL、Markdown、日志或向量库；
- [ ] 如新增向量索引来源，已完成脱敏和白名单审查；
- [ ] 如新增 artifact，已标明保留期限和访问权限；
- [ ] 如新增环境变量，已更新 .env.example 且未提交真实值。
```

---

## 14. 一句话边界

```text
PostgreSQL 存状态和事实，Git 存代码和制度，Markdown 存人类可读归档，pgvector 存脱敏索引，Secret Manager 存密钥，Workspace 存临时执行物；任何数据不得因为方便而跨越边界。
```
