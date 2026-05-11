# Agent Runner / Sandbox 边界 v3

> 本文件定义阶段 H1 的最小边界：Agent Runner 可以在哪里工作、哪些路径禁止修改、以及 L4 任务为什么不能直接执行。

## 1. 执行环境

```text
Agent Runner 必须运行在分支或沙箱中；
默认分支前缀为 codex/；
默认沙箱根目录为 .chao/sandboxes；
patch artifact 根目录为 .ai-agents/records/patches；
禁止直接在 main 上执行修改型任务。
```

## 2. 允许修改范围

```text
.ai-agents/records/
.ai-agents/templates/
.github/workflows/
app/
db/init/
db/migrations/
docs/
main.py
scripts/
tests/
```

## 3. 禁止修改范围

```text
.env
.env.*
.venv/
__pycache__/
data/
logs/
```

任何路径穿越仓库边界的写入都必须拒绝。

## 4. L4 执行限制

```text
L4 任务只能生成里程碑规划；
L4 任务不得直接进入工部执行；
L4 任务必须拆解为多个 L2 / L3 子任务后分别执行。
```

## 5. 当前落地

```text
app/chao/runner_policy.py 提供最小策略运行时；
tests/test_runner_policy.py 覆盖允许路径、禁止路径、路径穿越和 L4 禁执行规则；
后续 H2 / H3 将基于该策略实现分支创建和 allowed scope 阻断。
```
