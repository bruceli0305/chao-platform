# MCP 工具权限设计 v3

## 1. 总原则

v3 中，Agent 不直接随意访问系统资源，所有工具调用必须经过 MCP 工具层和权限策略。

```text
角色决定能做什么；
任务等级决定能做到什么程度；
风险类型决定是否需要审批；
工具调用必须可记录、可审计、可回放。
```

## 2. 工具分类

| 工具 | 风险等级 | 说明 |
|---|---|---|
| filesystem.read | 低 | 读取项目文件 |
| filesystem.write | 中 | 修改允许范围内文件 |
| shell.safe | 中 | typecheck、lint、test、build |
| shell.unrestricted | 高 | 任意 Shell，默认禁用 |
| github.issue | 低 | Issue 读取和创建 |
| github.pr | 中 | PR 创建和评论 |
| github.merge | 高 | 合并，默认人工控制 |
| postgres.read | 低 | 读取任务状态 |
| postgres.write | 中 | 写入状态和记录 |
| secret.scan | 中 | Secret 扫描 |
| dependency.review | 中 | 依赖审查 |
| deploy | 高 | 部署和回滚 |
| production.config | 极高 | 生产配置修改 |

## 3. 按角色授权

| 角色 | 默认工具 |
|---|---|
| task-router | postgres.read、filesystem.read、context.search |
| historian | postgres.read/write、markdown.write、context.index |
| zhongshu | filesystem.read、context.search、docs.browser |
| menxia | filesystem.read、postgres.read、github.pr.read、gate.read |
| shangshu | postgres.read/write、github.issue、github.pr.comment |
| gongbu | filesystem.read/write、shell.safe、git.diff |
| xingbu | filesystem.read、shell.safe、gate.write |
| hubu mode | dependency.review、secret.scan、postgres.read |
| bingbu mode | ci.read、deploy.plan、healthcheck、rollback.plan |
| libu mode | AGENTS.md read/write、templates.write |
| libu-docs mode | docs.write、release-note.write |

## 4. 按任务等级授权

| 等级 | 权限 |
|---|---|
| L1 | 只读 + 局部写入 + 轻量验证 |
| L2 | 项目文件写入 + 测试 / 构建 + PR 创建 |
| L3 | 需要确认后才能改数据库、依赖、部署、Secret |
| L4 | 不直接执行，只生成里程碑和子任务 |

## 5. 禁止规则

```text
L1 不得调用部署工具；
工部不得直接修改生产配置；
刑部不得修改业务代码，除非被显式授权修复测试夹具；
中书省不得写代码；
门下省不得执行实现；
任何 Agent 不得读取真实 Secret 明文；
任何 Agent 不得将 Secret 写入日志；
任何 Agent 不得绕过 CI 声称完成。
```

## 6. 工具调用审计

每次工具调用必须记录：

```text
task_id；
agent_name；
tool_name；
arguments_summary；
permission_policy；
result_status；
started_at；
finished_at；
output_hash；
risk_flag。
```

当前最小实现：

```text
app/chao/permissions.py 定义 TOOL_REGISTRY、ROLE_ALLOWED_TOOLS、LEVEL_ALLOWED_RISKS；
evaluate_tool_permission 负责输出 allowed、permission_policy、requires_confirmation 和 risk_flag；
第一批登记工具：cli.new、cli.approve、schema_check、data_boundary_check；
当前仍复用 tool_calls.permission_policy 字段记录策略名，尚未新增 permission_decision 字段。
```

## 7. 升级触发

以下情况必须暂停并升级：

```text
工具权限不足；
尝试访问禁止范围；
Shell 命令超出安全名单；
发现 Secret；
发现生产配置改动；
发现数据库迁移；
发现不可回滚操作；
工具执行结果与任务范围冲突。
```

## 9. MCP 数据边界

每个 MCP Server 必须声明：

```text
可读取的数据类型；
可写入的数据类型；
禁止读取的数据类型；
禁止写入的数据类型；
是否可能返回 Secret；
是否持久化工具输出；
是否允许结果进入 pgvector；
默认脱敏策略。
```

Shell、Filesystem、PostgreSQL、GitHub、Obsidian、Browser Docs MCP 均不得默认返回或保存 Secret 明文。涉及 D2 / D3 数据时，必须由任务路由器提升等级，并由户部 / 兵部 / 门下省介入。
