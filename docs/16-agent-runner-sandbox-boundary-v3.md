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
H2 分支创建策略已接入：执行型任务生成 codex/ 前缀分支计划；
L4 任务不生成执行分支；
H3 allowed scope 阻断已接入策略运行时和工部节点；
H4 刑部验证计划和失败阻断已接入；
H5 patch artifact 已接入，记录分支计划、变更范围和验证证据；
后续 H6 将基于验证结果处理失败回流。
```

## 6. 分支创建策略

```text
执行型任务必须使用 codex/ 前缀分支；
分支名格式为 codex/<task-code-slug>-<title-slug>；
默认 base_ref 为 HEAD，可由调用方指定为 main 或其他安全基线；
策略层只生成 create_command，不直接执行 git 命令；
main / master / trunk、路径穿越、空格、反斜杠和异常 ref 语法必须拒绝。
```

## 7. Allowed Scope 阻断

```text
Runner 在执行前必须提供拟修改文件列表；
所有路径必须位于 allowed_change_roots；
任何 forbidden_change_roots 命中都会拒绝执行；
任何未知路径都会拒绝执行；
工部节点必须调用 require_change_scope_allowed 后才能返回 implementation_result。
```

## 8. 刑部验证

```text
刑部节点必须根据 required_gates 生成验证计划；
每个 gate 必须映射到明确命令或人工验证要求；
任何验证命令失败时 deliverable 必须为 false；
验证失败必须抛出错误或保持 VALIDATION_FAILED，不能进入 DELIVERED。
```

## 9. Patch Artifact

```text
执行型任务必须生成 runner_patch artifact；
runner_patch artifact 必须记录分支计划、changed_files、工部结果和刑部验证结果；
L4 任务不得生成 runner_patch artifact；
当前 MVP 未生成真实 diff patch，后续真实 Runner 必须附加实际 patch 内容。
```
