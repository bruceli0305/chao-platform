# .ai-agents/AGENTS.md — 朝 v3 规则入口

> 根目录 `AGENTS.md` 是 Codex / Agent 的第一入口；本文件是 `.ai-agents` 制度目录的详细规则入口。执行任务前还必须阅读 `docs/12-current-project-progress-v3-alpha.md` 与 `docs/13-next-development-plan-v3.md`。

---

# AGENTS.md

## 项目智能体制度

本项目采用“朝”v3。

任何任务必须先经过任务路由器，完成：

```text
1. 保留原始需求；
2. 判断 L1 / L2 / L3 / L4；
3. 识别风险类型；
4. 判断是否需要 A / B / C / none 确认；
5. 判断需要启用哪些 Agent / Mode / Skill；
6. 明确不启用项及原因；
7. 明确允许修改范围和禁止修改范围；
8. 明确工程门禁；
9. 完成必要验证后才能声明交付。
```

当路由器输出 `required_skill_paths` 时，执行 Agent 必须在改动前阅读每个路径对应的
`SKILL.md`，并把实际使用的 Skill 写入史官记录、交付说明或 PR 模板。

## 禁止项

```text
不得未定级直接修改代码；
不得未确认 A 级事项直接执行；
不得新增未审查依赖；
不得修改无关文件；
不得无验证宣称完成；
不得用 UI 层掩盖后端错误；
不得吞异常或返回假成功；
不得读取或输出真实 Secret；
不得绕过 CI / PR / Review 合入高风险改动。
```

## 默认启用

```text
L1：任务路由器 + 工部 + 刑部轻验证 + 史官轻记录。
L2：任务路由器 + 中书省简案 + 工部 + 刑部 + 按需门下省。
L3：任务路由器 + 中书省完整方案 + 门下省审核 + 皇帝确认 + 分阶段执行。
L4：只做里程碑拆解，不直接执行。
```

## 验证要求

每次有效改动至少完成一种验证：

```text
typecheck；
lint；
test；
build；
manual validation；
secret scan；
dependency review。
```

无法验证时必须说明原因、替代检查和残余风险。

## 数据存储边界

任何 Agent 写入数据前必须判断数据分级和存储位置。

```text
PostgreSQL：任务状态、路由、事件、执行摘要、门禁结果、史官结构化事实、artifact 元数据。
Git / Markdown：源码、制度、ADR、正式文档、史官归档摘要。
pgvector：脱敏后的知识索引。
Secret Manager / GitHub Secrets：Secret、Token、私钥、生产密码。
Workspace / Sandbox：临时执行数据。
```

禁止：

```text
Secret 入 PostgreSQL；
Secret 入 Git；
Secret 入日志；
Secret 入向量库；
生产数据入史官；
完整聊天记录默认入长期记忆；
Agent scratchpad 入长期归档。
```

凡新增存储位置、向量化来源、Secret 注入、日志保留策略、artifact 存储策略，必须重新路由并按风险升级。
