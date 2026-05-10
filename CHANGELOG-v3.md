# 朝 v3 变更说明

## 1. v3 版本定位

v2.1 解决“运行协议化”；v2.2 解决“状态机、MCP、PostgreSQL、工程闭环化”；v3 解决“统一目标、工程内核、可安装、可执行、可演进”。

v3 的核心不是增加更多 Agent，而是明确：

```text
Agent 不是组织图上的职位，而是状态机中的执行节点；
三省六部不是主架构，而是治理语义；
Skills 不是附属文档，而是可复用能力单元；
工程门禁不是建议，而是交付底线。
```

## 2. v3 相对 v2.2 的核心变化

| 方向 | v2.2 | v3 |
|---|---|---|
| 总定位 | 智能体工程操作系统 | Agent DevOps 工程内核 |
| 设计重心 | 架构分层 | 可安装、可执行、可审计 |
| 三省六部 | 治理模型 | 治理语义层，不再作为主运行架构 |
| Agent | 常驻 Agent + 模式 | Agent / Mode / Skill 三分法 |
| 编排 | LangGraph 状态机 | 状态机优先，Agent 仅作为状态节点 |
| 工具 | MCP 工具层 | MCP + 权限策略 + 工具审计 |
| 数据 | PostgreSQL 控制平面 | PostgreSQL + Markdown 双写 + pgvector 检索 |
| 交付 | PR / CI / 归档 | 证据化交付：代码、验证、风险、记录齐全 |
| 实施 | MVP 文件 | 仓库级 .ai-agents 标准目录 |

## 3. v3 保留的 v2.1 / v2.2 原则

```text
一口进入，先判再做；
小事快闭，大事严治；
风险升级，流程升级；
失败回流，不假完成；
上下文按需，不全量灌入；
六部按需启用，不默认全员参与；
没有验证，不得宣称完成；
制度必须落到工具和仓库。
```

## 4. v3 新增原则

```text
状态机优先于角色扮演；
权限策略优先于工具自由；
结构化记录优先于聊天历史；
Skills 优先于新增 Agent；
仓库原生优先于外部平台；
证据交付优先于口头总结；
可回滚优先于快速上线；
低风险轻治理，高风险强阻断。
```

## v3 数据存储边界补充

- 新增 `docs/11-data-storage-boundary-v3.md`。
- 新增 `.ai-agents/rules/data-storage-boundary.md`。
- 新增 `.ai-agents/gates/data-boundary.md`。
- 更新总纲、朝纲、三省、六部、Agent、实施方案、技术架构、数据与记忆架构、MCP、Skills、工程门禁。
- 更新数据库 schema，新增 data_assets、storage_policies、artifact_records。
- 在 AGENTS.md 和 PR Checklist 中加入数据边界硬性规则。
