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

## 2.2 外部 adapter 入口

```text
uv run python main.py tool-gateway-serve
```

该命令通过 stdin/stdout 接收 JSON Lines：

```json
{"jsonrpc":"2.0","id":"1","method":"tool.evaluate","params":{"request":{"protocol":"jsonl","agent_name":"gongbu","tool_name":"cli.runner_patch","task_level":"L2","required_confirmation":"B","current_status":"DELIVERED","arguments_summary":"path=app/chao/demo.py"}}}
```

当前支持：

```text
health；
tool.evaluate；
tool.execute.echo。
```

`tool.execute.echo` 只用于验证 adapter 拦截行为；真实工具 handler 必须后续显式注册。

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
