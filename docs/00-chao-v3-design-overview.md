# “朝”智能体协同开发架构设计总纲 v3

## 1. 最高定位

“朝”v3 是面向真实软件开发的 **Agent DevOps 工程内核**。

它不是：

```text
不是单个聊天机器人；
不是 Prompt 集合；
不是多 Agent 角色扮演；
不是只有文档没有执行的制度；
不是让所有 Agent 都参与所有任务的组织架构。
```

它是：

```text
以任务路由器为入口；
以状态机为运行中枢；
以 PostgreSQL 为控制平面；
以 MCP 为工具协议层；
以 Agent Runner / Sandbox 为执行层；
以 GitHub / CI / PR 为工程闭环；
以史官记录 / pgvector / Obsidian 为知识沉淀；
以三省六部为治理语义；
以 Skills 为可复用能力单元；
以工程门禁为交付底线。
```

## 2. 统一目标

```text
让程序员在真实项目中使用 AI 协助开发时，做到：
需求可追溯、任务可路由、权限可控制、执行可隔离、结果可验证、失败可回流、知识可沉淀、交付可复盘。
```

这个目标拆成八个可验证目标：

| 目标 | 可验证表现 |
|---|---|
| 需求可追溯 | 每个任务保留原始需求、澄清记录、确认事项 |
| 任务可路由 | 每个任务有等级、风险、启用角色、门禁 |
| 权限可控制 | Agent 调用工具前必须受角色、等级、风险约束 |
| 执行可隔离 | 代码改动发生在分支、沙箱或受控工作区 |
| 结果可验证 | 每个有效改动至少有一种验证证据 |
| 失败可回流 | 构建、测试、部署、审核失败有明确回流对象 |
| 知识可沉淀 | 决策、验证、事故、交付进入史官记录和检索层 |
| 交付可复盘 | PR、CI、变更、风险、文档形成完整交付包 |

## 3. v3 总架构

```text
用户 / 皇帝
  ↓
入口层：CLI / Console / GitHub Issue / PR Comment
  ↓
任务路由器 Task Router
  ↓
控制平面 Control Plane
  ├── 状态机 State Machine
  ├── 任务表 / 路由表 / 状态表
  ├── 风险 / 阻塞 / 确认事项
  ├── 工程门禁结果
  └── 史官记录索引
  ↓
治理语义层 Governance Layer
  ├── 三省：中书省 / 门下省 / 尚书省
  ├── 六部：吏户礼兵刑工
  └── 技术能力池 / Skills
  ↓
执行层 Execution Layer
  ├── Agent Runner
  ├── Sandbox / Workspace
  ├── Git Branch / Patch
  └── Tool Permission Controller
  ↓
MCP 工具层 Tool Layer
  ├── Filesystem
  ├── Shell
  ├── GitHub
  ├── PostgreSQL
  ├── Browser / Docs
  ├── Obsidian / Markdown
  ├── Secret Scan
  └── Dependency Review
  ↓
工程闭环 Engineering Loop
  ├── typecheck / lint / test / build
  ├── secret scan / dependency review
  ├── PR / Review / CI
  ├── deploy / rollback / healthcheck
  └── archive / retrospective
```

## 4. 三省六部在 v3 中的位置

v3 明确：三省六部不再是运行主架构，而是治理语义层。

```text
状态机决定任务怎么流转；
任务路由器决定谁参与；
MCP 权限决定能调用什么工具；
三省六部决定职责如何归口；
工程门禁决定能否交付。
```

因此：

```text
不为形式启用角色；
不为角色制造文档；
不让 Agent 自由越权；
不让高风险任务绕过审核；
不让低风险任务被大流程拖死。
```

## 5. Agent / Mode / Skill 三分法

v3 用三分法控制复杂度：

| 类型 | 定义 | 示例 | 是否常驻 |
|---|---|---|---|
| Agent | 状态机中的执行节点，有明确输入输出 | 路由器、史官、工部、刑部 | 核心 Agent 常驻 |
| Mode | 某个 Agent 的专项审查模式 | 户部模式、兵部模式 | 按风险启用 |
| Skill | 可复用能力包，提供步骤、检查清单、工具规范 | bugfix、frontend-feature、api-development | 按任务调用 |

优先级：

```text
能用 Skill 解决，不新增 Mode；
能用 Mode 解决，不新增 Agent；
能用工具门禁解决，不写人工长文；
能轻量闭环，不进入完整治理。
```

## 6. v3 第一原则

```text
先路由，再执行；
先定级，再授权；
先确认，再高风险变更；
先验证，再交付；
先记录事实，再总结判断；
先回流失败，再继续推进；
先复用 Skill，再新增 Agent。
```

## 7. v3 交付定义

一个任务只有同时满足以下条件，才允许声明交付：

```text
1. 原始需求已记录；
2. 任务等级和风险类型已明确；
3. 修改范围未越界；
4. A 级事项已确认；
5. 必要工程门禁已通过，或说明无法验证原因；
6. 残余风险已说明；
7. 史官已记录关键事实；
8. PR / 文档 / 变更说明已按任务等级生成。
```

## 12. 数据存储边界总原则

v3 必须把“数据存到哪里”作为架构硬约束，而不是实现细节。

```text
PostgreSQL：只存任务状态、路由、事件、Agent 执行摘要、工具调用摘要、门禁结果、史官结构化事实和 artifact 元数据。
Git / Markdown：只存源码、制度文件、ADR、正式文档和史官人类可读归档。
pgvector：只存经过批准和脱敏的知识索引，不存原始敏感数据。
Secret Manager / GitHub Secrets：只存密钥、Token、私钥和生产密码。
Workspace / Sandbox：只存临时执行数据，不作为长期事实源。
```

禁止把 Secret、生产数据、个人隐私、完整 CI 长日志、完整 Agent scratchpad、未经确认的长聊天记录写入 PostgreSQL、Markdown 或向量库。

凡新增存储位置、向量索引来源、日志保留策略、Secret 注入方式、生产数据处理方式，最低按 L3 处理，由中书省设计、户部审查、门下省审核，必要时皇帝 A 级确认。
