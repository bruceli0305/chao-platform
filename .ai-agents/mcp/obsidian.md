# MCP: obsidian

## 1. 用途

为 Agent 提供受控工具能力。

## 2. 权限原则

```text
按角色授权；
按任务等级限制；
按风险类型升级；
所有调用必须记录；
高风险操作必须确认。
```

## 3. 审计字段

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
