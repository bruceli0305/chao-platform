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

## 5. 后续

```text
按任务等级限制可用 Provider 和模型；
为 D2 / D3 数据增加脱敏与禁止外发策略。
```
