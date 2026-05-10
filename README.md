# 朝 v3 文档包

> v3 目标：把“朝”从一套智能体协同设想，收敛为可以放进真实代码仓库、可以执行、可以审计、可以回滚、可以长期演进的 **Agent DevOps 工程内核**。

## 统一目标

```text
让程序员在真实项目中使用 AI 协助开发时，做到：
需求可追溯、任务可路由、权限可控制、执行可隔离、结果可验证、失败可回流、知识可沉淀、交付可复盘。
```

v3 不再把“三省六部”当作系统主架构，而是把它降级为 **治理语义层**。真正的运行骨架是：

```text
任务路由器
+ 状态机
+ PostgreSQL 控制平面
+ MCP 工具权限层
+ Agent Runner / Sandbox 执行层
+ GitHub / CI / PR 工程门禁
+ 史官记录 / pgvector / Obsidian 知识层
+ Skills 能力包
```

## 文档目录

```text
chao-v3
├── README.md
├── CHANGELOG-v3.md
├── docs
│   ├── 00-chao-v3-design-overview.md
│   ├── 01-chao-principles-v3.md
│   ├── 02-three-departments-responsibilities-v3.md
│   ├── 03-six-ministries-responsibilities-v3.md
│   ├── 04-agent-system-design-v3.md
│   ├── 05-implementation-plan-v3.md
│   ├── 06-technical-architecture-v3.md
│   ├── 07-data-and-memory-architecture-v3.md
│   ├── 08-mcp-tool-permission-design-v3.md
│   ├── 09-skills-design-spec-v3.md
│   ├── 10-engineering-gates-quality-system-v3.md
│   └── 99-file-index.md
└── .ai-agents
    ├── AGENTS.md
    ├── chao-v3.md
    ├── router
    ├── roles
    ├── modes
    ├── experts
    ├── workflows
    ├── gates
    ├── mcp
    ├── skills
    ├── templates
    ├── records
    └── db
```

## v3 第一阶段建议

第一阶段不要做完整 Web Console，也不要追求全自动多 Agent。

优先完成：

```text
1. .ai-agents 目录落地。
2. AGENTS.md 作为仓库级制度入口。
3. 任务路由器模板。
4. L1 / L2 / L3 / L4 定级规则。
5. A / B / C 人类确认规则。
6. 工部 / 刑部执行与验证模板。
7. 史官 records 文件。
8. GitHub Actions 基础门禁。
9. Secret Scan / Dependency Review 最小接入。
10. 后续再接 PostgreSQL、MCP、LangGraph 状态机。
```

## v3 数据存储边界

v3 已补充强制数据边界：PostgreSQL 存状态和事实，Git 存代码和制度，Markdown 存人类可读归档，pgvector 存脱敏索引，Secret Manager / GitHub Secrets 存密钥，Workspace / Sandbox 存临时执行物。详见 `docs/11-data-storage-boundary-v3.md` 与 `.ai-agents/rules/data-storage-boundary.md`。
