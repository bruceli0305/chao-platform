# 后续开发计划 v3

> 本文件作为 `chao-platform` 后续开发路线图。优先级以“先让 Codex / Agent 可接管、再补可审计能力、最后做自动化和可视化”为原则。

## 1. 总体路线

```text
阶段 A：文档入仓与 Codex 接管
阶段 B：数据边界闭环
阶段 C：pgvector 知识检索
阶段 D：Skills 最小执行机制
阶段 E：MCP 工具权限原型
阶段 F：GitHub Issue / PR 绑定
阶段 G：L3 / L4 完整治理
阶段 H：Agent Runner / Sandbox
阶段 I：Console 可视化
```

## 2. 阶段 A：文档入仓与 Codex 接管

目标：让 Codex 能在仓库中读取完整上下文，而不是依赖 ChatGPT 对话历史。

任务：

```text
A1. 上传完整 docs/ 与 .ai-agents/ 到 GitHub；
A2. 增加根目录 AGENTS.md；
A3. 增加 docs/12-current-project-progress-v3-alpha.md；
A4. 增加 docs/13-next-development-plan-v3.md；
A5. Ubuntu 中 git pull；
A6. Codex 首次接管并运行 ./scripts/check.sh；
A7. 使用 Codex 完成一个小型代码任务，验证接管质量。
```

验收：

```text
Codex 能说明项目定位；
Codex 能遵守数据边界；
Codex 能运行本地门禁；
GitHub Actions 通过。
```

## 3. 阶段 B：数据边界闭环

目标：让数据资产、存储策略、artifact 和任务详情形成完整可审计链。

任务：

```text
B1. show TASK-xxx 输出 data_assets；
B2. CI 中 Verify data assets persisted 增加 task_id 非空检查；
B3. data_assets 增加 source_uri / source_hash 可选字段；
B4. data_boundary_check.py 增强：检查 Markdown 记录是否包含疑似 Secret；
B5. artifacts 增强：检查 artifact_uri 对应文件存在性；
B6. 新增 data-boundary report 输出模板。
```

验收：

```text
每个任务至少有 Markdown artifact；
每个 Markdown artifact 对应一个 D1 data_asset；
data_asset 必须关联 task_id；
CI 可阻断数据边界违规。
```

## 4. 阶段 C：pgvector 知识检索

目标：实现第一版知识 ingest，为后续 Agent 检索历史决策、规则和史官记录做准备。

任务：

```text
C1. 设计 ingest 白名单：docs、.ai-agents、README、史官摘要；
C2. 明确禁止 ingest：.env、logs、data、CI 长日志、Secret、生产数据；
C3. 增加 context_chunks 字段：source_type、source_hash、classification、desensitized；
C4. 实现 scripts/ingest_markdown.py；
C5. 实现 scripts/search_context.py；
C6. 将 ingest 结果登记到 data_assets；
C7. 增加 schema_check 和 data_boundary_check 对 ingest 的校验。
```

当前状态：

```text
C1 / C2 已进入策略设计：docs/15-pgvector-ingest-policy-v3.md。
C3 context_chunks 元数据字段已落地：db/migrations/007_context_chunks_metadata.sql。
C7 的 ingest 白名单 / 禁止路径基础校验已接入 scripts/data_boundary_check.py。
C4 dry-run 已接入 scripts/ingest_markdown.py，不写数据库、不生成 embedding。
后续实现 ingest 前，必须补充 context_chunks 写入验证。
```

验收：

```text
可以检索 docs/11-data-storage-boundary-v3.md；
可以检索 AGENTS.md；
可以检索指定 TASK 的史官摘要；
禁止文件不会被 ingest。
```

## 5. 阶段 D：Skills 最小执行机制

目标：从“角色说明”进入“可复用能力包”。

第一批 Skill：

```text
bugfix；
frontend-feature；
api-development；
database-migration；
security-review；
docs-generation；
release-validation。
```

任务：

```text
D1. 定义 skills registry；
D2. 路由器输出 required_skills；
D3. CLI show 显示 required_skills；
D4. 新增 tests/test_skills.py；
D5. Codex 根据 Skill 执行任务前必须读取对应 SKILL.md；
D6. GitHub PR 模板增加 Skill 字段。
```

验收：

```text
L2 前端页面任务能命中 frontend-feature；
Bug 修复任务能命中 bugfix；
数据库变更任务能命中 database-migration 并升级 L3。
```

## 6. 阶段 E：MCP 工具权限原型

目标：实现工具调用前的权限策略判断，即使暂时不用完整 MCP 服务，也要先有 policy runtime。

任务：

```text
E1. 定义 tool permission policy 数据结构；
E2. 建立 role + level + risk → allowed_tools 映射；
E3. 将 cli.new、cli.approve、schema_check、data_boundary_check 作为第一批工具；
E4. tool_calls 增加 permission_decision 字段；
E5. 高风险工具调用必须要求 approval；
E6. CI 验证 tool_calls 中 permission_policy 不为空。
```

验收：

```text
所有工具调用有 agent_name、tool_name、permission_policy、result_status；
高风险任务不能调用未授权工具；
tool_calls 可按 task_id 查询。
```

## 7. 阶段 F：GitHub Issue / PR 绑定

目标：让 GitHub 成为工程闭环的一部分。

任务：

```text
F1. 新增 github_links 表；
F2. CLI 支持绑定 issue / PR；
F3. PR 模板强制填写 task_code；
F4. CI 检查 PR 是否绑定任务；
F5. 合并后写入 historian_records；
F6. 记录 commit hash、CI run id、PR URL。
```

验收：

```text
任意 PR 可追溯到 TASK；
任意 TASK 可追溯到 PR / commit / CI；
交付证据进入 artifacts。
```

## 8. 阶段 G：L3 / L4 完整治理

目标：让高风险任务不只是被 approve，而是进入完整治理流程。

任务：

```text
G1. L3 approve 后进入 DESIGNING / REVIEWING / SCHEDULING；
G2. 中书省输出方案 artifact；
G3. 门下省输出审核 artifact；
G4. 户部审查数据 / 依赖 / Secret；
G5. 兵部审查部署 / CI / rollback；
G6. L4 只生成里程碑，不直接执行。
```

验收：

```text
L3 数据库变更有方案、审批、验证、回滚说明；
L4 任务会拆解成多个 L2 / L3 子任务。
```

## 9. 阶段 H：Agent Runner / Sandbox

目标：让工部真正能在受控环境中修改代码。

任务：

```text
H1. 定义 workspace/sandbox 边界；
H2. 实现 branch 创建策略；
H3. 工部只允许改 allowed scope；
H4. 刑部执行验证；
H5. 生成 patch artifact；
H6. 失败回流到工部。
```

验收：

```text
Agent 修改发生在分支或沙箱；
无关文件改动会被阻断；
验证失败不能交付。
```

## 10. 阶段 I：Console 可视化

目标：降低使用门槛，用 Web 查看任务、审批、门禁、记录和审计链。

页面：

```text
任务列表；
任务详情；
审批中心；
事件流；
工具调用；
Artifacts；
Data Assets；
Schema / Data Boundary Gate；
CI / PR 绑定；
风险和阻塞。
```

暂缓到前面阶段稳定后再做。

## 11. 近期推荐任务队列

按当前进度，建议接下来优先做：

```text
1. 完成文档入仓并让 Codex 接管；
2. show TASK 输出 data_assets；
3. CI 验证 data_assets.task_id 非空；
4. 增加 GitHub 网页上传后的 Ubuntu pull 验证流程；
5. 增加 docs/14-codex-handoff-guide.md；
6. 开始 pgvector ingest 白名单设计。
```
