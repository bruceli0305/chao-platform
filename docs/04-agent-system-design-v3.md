# Agent 体系设计 v3

## 1. 设计原则

v3 的 Agent 设计原则：

```text
少设常驻 Agent；
多用 Mode；
多沉淀 Skill；
工具调用受权限控制；
所有 Agent 必须有输入、输出、边界、禁令。
```

Agent 不是人格角色，而是状态机节点。

## 2. Agent 分层

```text
控制类 Agent：Router、Scheduler、Historian
治理类 Agent：Planner、Reviewer
执行类 Agent：Builder、Validator
专项 Mode：Libu、Hubu、Libu Docs、Bingbu
技术能力池：通过 Skill / Expert Profile 调用，不默认常驻
```

## 3. v3 核心 Agent

| Agent | 中文名 | 职责 | 是否 MVP 常驻 |
|---|---|---|---|
| task-router | 任务路由器 | 定级、识险、分流、门禁判断 | 是 |
| historian | 史官 | 记录事实、决策、验证、事故 | 是 |
| shangshu-scheduler | 尚书省 / 调度器 | 状态管理、调度、回流、汇总 | 可与 router 合并 |
| zhongshu-planner | 中书省 / 方案 | 澄清、方案、契约、选型 | L2+ 启用 |
| menxia-reviewer | 门下省 / 审核 | 审核、驳回、风险裁断 | 按风险启用，L3 必启 |
| gongbu-builder | 工部 / 实现 | 代码实现、Bug 修复、局部重构 | 是 |
| xingbu-validator | 刑部 / 验证 | 测试、回归、质量结论 | 是 |

MVP 可将 task-router 与 shangshu-scheduler 合并，完整 v3 建议拆分。

## 4. Agent 通用契约

每个 Agent 必须声明：

```text
1. Role：职责；
2. Inputs：输入材料；
3. Outputs：输出物；
4. Tools：可用工具；
5. Permissions：工具权限；
6. Constraints：硬性限制；
7. Escalation：何时升级；
8. Record：何时通知史官记录。
```

## 5. 任务路由器 Agent

### Role

把用户需求转为结构化任务路由结果。

### Inputs

```text
用户原始需求；
当前仓库上下文摘要；
历史相关决策；
AGENTS.md；
任务等级规则；
风险类型规则；
确认规则。
```

### Outputs

```text
task_level；
risk_types；
confirmation_level；
required_agents；
required_modes；
required_skills；
required_gates；
allowed_scope；
forbidden_scope；
next_action。
```

### Forbidden

```text
不改写用户原始需求；
不直接写代码；
不绕过 A 级确认；
不把高风险降级；
不把低风险复杂化。
```

## 6. 史官 Agent

### Role

记录关键事实，形成长期可检索的项目记忆。

### Inputs

```text
任务路由结果；
澄清和确认；
方案和审核；
实现摘要；
验证结果；
PR / CI / 发布结果；
事故和回滚记录。
```

### Outputs

```text
records/current.md；
records/progress.md；
records/decisions.md；
records/changes.md；
records/validations.md；
records/incidents.md；
PostgreSQL historian_records；
pgvector context_chunks。
```

### Forbidden

```text
不记录无意义流水；
不把推测写成事实；
不覆盖原始需求；
不删除历史决策；
不将失败包装成成功。
```

## 7. 尚书省 / Scheduler Agent

### Role

负责状态管理、任务分派、失败回流和交付汇总。

### Outputs

```text
调度单；
任务状态更新；
失败回流决策；
交付汇总；
需要终审的清单。
```

### Forbidden

```text
不跳过路由；
不绕过门下省；
不允许无验证交付；
不允许越权修改范围。
```

## 8. 中书省 / Planner Agent

### Role

负责需求澄清、方案设计、接口契约、数据契约和技术选型。

### Outputs

```text
轻量澄清；
L2 简案；
L3 完整方案；
L4 里程碑方案；
ADR。
```

### Forbidden

```text
不直接写代码；
不替门下省作审核结论；
不把未确认需求写成已确认；
不把 L1 小任务复杂化。
```

## 9. 门下省 / Reviewer Agent

### Role

负责审核、驳回和风险裁断。

### Outputs

```text
审核报告；
通过 / 有条件通过 / 驳回；
必须修改项；
是否允许进入下一步。
```

### Forbidden

```text
不只提建议不给结论；
不用 L3 标准审 L1；
不为了进度放过高风险；
不替工部写代码。
```

## 10. 工部 / Builder Agent

### Role

负责最小可验证实现。

### Tools

```text
filesystem read/write；
shell limited；
git branch / diff；
package manager read；
unit test / build command。
```

### Forbidden

```text
不新增未审查依赖；
不扩大修改范围；
不吞异常；
不返回假成功；
不无验证宣称完成。
```

## 11. 刑部 / Validator Agent

### Role

负责复现、测试、回归、安全边界、质量结论。

### Outputs

```text
验证报告；
正常路径验证；
异常路径验证；
未覆盖内容；
残余风险；
质量结论。
```

## 12. 专项 Mode

| Mode | 触发 | 产物 |
|---|---|---|
| libu-agent-governance | Agent / Prompt / 规范变化 | 职责边界与越权审查 |
| hubu-resource-secret | 依赖 / 数据库 / Secret / 成本 | 资源与安全审查 |
| libu-docs | README / API / 发布说明 | 文档一致性结果 |
| bingbu-deploy | 部署 / CI / 回滚 / 线上故障 | 部署与回滚报告 |

## 13. 技术能力池

技术能力池不默认作为长期 Agent。

推荐实现为 Skill：

```text
frontend-feature；
api-development；
database-migration；
bugfix；
release-validation；
docs-generation；
security-review；
ui-review。
```

## 14. Agent 新增规则

新增 Agent 必须经过吏部审查，满足至少两个条件：

```text
职责长期存在；
不能通过现有 Agent + Mode 解决；
不能通过 Skill 解决；
需要独立工具权限；
需要独立状态机节点；
会产生独立交付物。
```

否则应优先新增 Skill 或 Mode。

## 11. Agent 数据存储边界

每个 Agent 的输出必须声明：

```text
写入位置；
数据分级；
是否脱敏；
是否可向量化；
是否长期保存；
责任归口。
```

Agent 禁止：

```text
把内部 scratchpad 写入史官；
把工具原始长输出全部写入 PostgreSQL；
把 Secret 写入任何长期记忆；
把未经确认的聊天内容当成事实源；
绕过任务路由器自行选择存储位置。
```
