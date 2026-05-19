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
```

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
arguments_summary 只记录 provider、model、prompt_chars 和 execute；
output_summary 只记录 provider、model、status、dry_run 和 error；
不保存 prompt 正文、API Key 或完整响应正文。
```

允许调用角色：

```text
zhongshu
```

## 5. 后续

```text
按任务等级限制可用 Provider 和模型；
为 D2 / D3 数据增加脱敏与禁止外发策略。
```
