# 朝 v3 技术架构设计

## 1. 总体技术路线

v3 推荐主线：

```text
LangGraph / 状态机
+ PostgreSQL / 控制平面
+ pgvector / 检索记忆
+ MCP / 工具协议
+ Agent Runner / Sandbox
+ GitHub Actions / 工程门禁
+ .ai-agents / 仓库原生规则
+ Obsidian / 人类知识图谱
```

Dify、LiteLLM、FastGPT 可以保留，但不做核心：

| 工具 | v3 定位 |
|---|---|
| Dify | 外围入口、Demo、运营式问答 |
| LiteLLM | 多模型网关、成本统计、fallback |
| FastGPT | 知识问答前台 |
| Obsidian | 人类知识图谱和长期设计笔记 |
| PostgreSQL | 运行控制平面 |
| pgvector | Agent 检索记忆 |

## 2. 分层架构

```text
入口层
  CLI / Console / GitHub Issue / PR Comment

控制平面
  Task Router / State Machine / PostgreSQL / Policy

治理层
  三省六部 / Agent / Mode / Skill

执行层
  Agent Runner / Sandbox / Workspace / Branch

工具层
  MCP Servers

工程闭环
  GitHub Actions / PR / Review / Merge / Release

记忆层
  Historian Records / pgvector / Obsidian / Markdown
```

## 3. 控制平面

控制平面负责：

```text
任务创建；
任务路由；
任务状态；
Agent 运行记录；
工具调用审计；
门禁结果；
风险和阻塞；
确认事项；
交付归档。
```

控制平面必须是系统事实源，不能只依赖聊天上下文。

## 4. 执行层

执行层负责在受控环境中完成代码改动。

建议执行环境：

```text
本地 Workspace；
Docker Sandbox；
Dev Container；
GitHub Codespaces；
远程 Runner。
```

执行层必须遵守：

```text
先创建分支；
只改允许范围；
每次改动生成 diff；
每次验证保存输出；
失败时停止交付；
必要时生成 PR。
```

## 5. 工具层

MCP 工具层包括：

| MCP | 用途 |
|---|---|
| filesystem | 读写允许范围内文件 |
| shell | 执行验证命令 |
| github | Issue、PR、Review、Actions |
| postgres | 读写任务状态和记录 |
| obsidian | 读取 / 写入设计笔记 |
| browser-docs | 查阅官方文档 |
| secret-scan | gitleaks / secret scanning |
| dependency-review | npm audit / cargo audit / license |

## 6. 数据层

推荐第一版：

```text
PostgreSQL + pgvector
```

不建议第一版上独立向量数据库，除非已有明确的多项目检索压力。

## 7. GitHub 集成

v3 应与 GitHub 原生闭环：

```text
Issue 创建任务；
Branch 承载改动；
Commit 绑定任务编号；
PR 展示任务等级、风险、验证；
GitHub Actions 执行门禁；
PR Review 触发门下省终审；
Merge 后史官归档。
```

Commit 示例：

```text
fix(TASK-20260509-001): 修复用户列表分页异常
feat(TASK-20260509-002): 新增用户导出接口
```

## 8. 安全边界

```text
Agent 默认无生产权限；
Agent 默认不能读取真实 Secret；
Secret 只通过环境注入，不进入日志；
Shell 命令必须记录；
数据库修改必须经过确认；
部署操作必须由兵部模式触发；
L3 / L4 必须有人类确认。
```

## 9. 推荐技术选型

| 模块 | 推荐 |
|---|---|
| 编排 | LangGraph / 自研轻量状态机 |
| 后端 | Python 或 Node.js，第一版偏 Python |
| 数据库 | PostgreSQL |
| 向量 | pgvector |
| 工具协议 | MCP |
| 执行环境 | Docker / Dev Container |
| CI | GitHub Actions |
| Secret Scan | gitleaks |
| 依赖审查 | npm audit / cargo audit / dependency review |
| 文档 | Markdown / Obsidian |
| 仓库规则 | .ai-agents / AGENTS.md |

## 10. 数据存储边界在技术架构中的位置

v3 技术架构中，数据边界属于控制平面的基础能力：

```text
Task Router：识别数据类型和分级；
LangGraph：按状态控制数据写入时机；
PostgreSQL：保存运行状态和审计事实；
MCP：按权限暴露存储和工具；
Agent Runner：在 Sandbox 内处理临时数据；
GitHub Actions：产生验证证据；
pgvector：只索引脱敏知识；
Secret Manager：隔离密钥。
```

任何工具接入前必须声明：可读数据、可写数据、禁止数据、输出是否持久化、是否进入向量库。
