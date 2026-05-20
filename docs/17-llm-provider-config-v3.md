# LLM Provider Config v3

本文定义“朝”本地 Alpha 的模型 Provider 配置边界。

## 1. 目标

```text
默认支持 DeepSeek；
保留 OpenAI / Anthropic / OpenAI-compatible 扩展入口；
不在代码、日志、Markdown、PostgreSQL 或 pgvector 中保存 API Key 明文；
Provider 配置只输出安全摘要。
```

## 2. 当前 Provider

```text
deepseek：
  api_style = openai-compatible
  base_url = https://api.deepseek.com
  api_key_env = DEEPSEEK_API_KEY
  model_env = DEEPSEEK_MODEL
  default_model = deepseek-chat

openai：
  api_style = openai
  base_url = https://api.openai.com/v1
  api_key_env = OPENAI_API_KEY
  model_env = OPENAI_MODEL

anthropic：
  api_style = anthropic
  base_url = https://api.anthropic.com
  api_key_env = ANTHROPIC_API_KEY
  model_env = ANTHROPIC_MODEL

openai-compatible：
  api_style = openai-compatible
  base_url = CHAO_LLM_BASE_URL
  api_key_env = CHAO_LLM_API_KEY
  model_env = CHAO_LLM_MODEL
```

## 3. CLI

```bash
uv run python main.py llm-providers
uv run python main.py llm-providers --provider deepseek
uv run python main.py llm-providers --provider openai-compatible
uv run python main.py llm-chat TASK-xxxx "summarize this task"
uv run python main.py llm-chat TASK-xxxx "summarize this task" --execute
uv run python main.py llm-chat TASK-xxxx "summarize this task" --data-classification D1 --execute
uv run python main.py authorize-llm-egress TASK-xxxx --provider deepseek --model deepseek-chat --ttl-hours 24
uv run python main.py llm-chat TASK-xxxx "summarize this task" --execute --allow-governed-egress
uv run python main.py audit-llm-egress-authorizations
uv run python main.py audit-llm-egress-authorizations --apply
```

`llm-chat` 会根据 `TASK_CODE` 读取任务详情，并将任务标题、原始需求、路由、
事件、artifact、data asset、gate 和 GitHub link 摘要拼成任务上下文后发送给
Provider。上下文只包含审计摘要和元数据，不读取 artifact 正文。

输出中只包含：

```text
provider 名称；
API 风格；
base_url；
API Key 环境变量名；
模型名；
api_key_set 布尔值。
```

禁止输出 API Key 明文。

## 4. 调用审计

`llm-chat` 默认 dry-run，不调用外部 Provider。显式 `--execute` 后才会发起
真实 HTTP 请求。

每次 `llm-chat` 会写入 `tool_calls`：

```text
tool_name = llm.chat_completion；
permission_policy = llm-provider-chat-completion；
arguments_summary 只记录 provider、model、user_prompt_chars、llm_prompt_chars 和 execute；
output_summary 只记录 provider、model、status、dry_run 和 error；
不保存 prompt 正文、API Key 或完整响应正文。
```

外发前会对常见 Secret 形态进行脱敏：

```text
private key；
GitHub token；
OpenAI-style sk token；
AWS access key；
api_key / apikey / secret / token / password 赋值片段。
```

允许调用角色：

```text
zhongshu
```

## 5. 外发策略

`llm-chat` 在真实外发前执行 LLM egress policy：

```text
dry-run：允许，不调用外部 Provider；
--execute：仅允许 L1 / L2 任务；
--execute：仅允许 D0 / D1 数据；
--execute：仅允许已登记的 provider / model 组合；
L3 / L4：必须显式传入 --allow-governed-egress，且存在未过期的 APPROVED llm_egress_authorizations 记录；
任务 data_assets 中出现更高分级时，以最高分级为准；
D2 / D3 / D4、未授权的 L3 / L4、未知分级或未登记模型会被拒绝外发，并写入 tool_calls 审计。
```

当前真实外发 allowlist：

```text
deepseek / deepseek-chat；
openai / gpt-4.1-mini；
anthropic / claude-3-5-sonnet-latest。
```

`--data-classification` 用于声明本次 prompt 中包含的最高数据分级，默认 `D1`。

## 6. 后续

```text
`.github/workflows/llm-egress-audit.yml` 已支持 schedule / workflow_dispatch。
如需审计外部数据库，在 GitHub Secrets 中配置 `CHAO_AUDIT_DATABASE_URL`；
未配置时 workflow 只使用 Actions 内置 pgvector 数据库做安全冒烟。

下一步：为审计失败或发现异常补充告警 / issue 回流。
```
