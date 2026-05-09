# Current

## 当前阶段

朝 v2.2 local MVP 已完成数据库层与基础状态机。

## 已完成

- Docker Desktop 可用
- PostgreSQL + pgvector 已启动
- tasks / task_routes / historian_records / gate_results / context_chunks 表已创建
- Task Router 可判断 L1 / L2 / L3
- LangGraph 可执行基础流程
- L3 可进入 NEED_CONFIRMATION
- 任务结果已写入 PostgreSQL

## 下一步

- 增加 CLI 查询任务能力
- 增加 Markdown 史官双写
- 增加 GitHub Actions
- 增加 PostgreSQL checkpoint
- 增加真实项目接入能力

## 当前限制

- 不自动修改真实代码
- 不自动执行工程命令
- 不自动创建 PR
