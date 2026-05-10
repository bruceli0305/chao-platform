# Codex 接管说明

## 1. 启动位置

Codex 必须在 WSL Ubuntu 的项目目录中启动：

```bash
cd ~/workspace/chao-platform
codex --auto-edit
```

不要在 Windows 原生 PowerShell 中直接操作本项目。

## 2. 接管前检查

```bash
git status
./scripts/check.sh
```

若本地有未提交改动，先确认是否属于当前任务。不得覆盖用户未提交改动。

## 3. 首次阅读文件

Codex 首次进入项目必须阅读：

```text
AGENTS.md
.ai-agents/AGENTS.md
README.md
docs/00-chao-v3-design-overview.md
docs/01-chao-principles-v3.md
docs/11-data-storage-boundary-v3.md
docs/12-current-project-progress-v3-alpha.md
docs/13-next-development-plan-v3.md
.ai-agents/router/*
.ai-agents/gates/*
.ai-agents/skills/*/SKILL.md
```

## 4. 推荐 Codex 任务提示模板

```text
你正在开发 chao-platform 项目，这是“朝”v3 local MVP。

请先阅读 AGENTS.md、docs/12-current-project-progress-v3-alpha.md、docs/13-next-development-plan-v3.md 和 docs/11-data-storage-boundary-v3.md。

当前任务：<填写任务>

约束：
- 不要修改 .env、data/postgres、logs、.venv；
- 不要提交 Secret、Token、私钥；
- 涉及数据库结构时必须新增 db/migrations 文件，并同步 db/init/001_init.sql；
- 涉及数据边界时必须保证 scripts/data_boundary_check.py 通过；
- 修改后必须运行 ./scripts/check.sh；
- 输出修改文件、验证结果、未覆盖内容和残余风险。
```

## 5. Codex 完成后的人工审查

开发者需要检查：

```bash
git diff --stat
git diff
./scripts/check.sh
```

确认后再提交：

```bash
git add .
git commit -m "<message>"
git push
```
