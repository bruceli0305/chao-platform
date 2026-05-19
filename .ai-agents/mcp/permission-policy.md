# MCP: permission-policy

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

## 2.1 协议层拦截

```text
工具适配器必须先构造 ToolGatewayRequest；
工具 handler 必须交给 execute_tool_gateway_request 包裹；
权限 denied 时不得调用真实工具；
工具失败时必须返回 failed 审计结果，不得返回假成功；
返回 audit 字段必须写入 tool_calls 或等价审计位置。
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
