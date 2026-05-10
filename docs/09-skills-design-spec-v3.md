# Skills 设计规范 v3

## 1. Skill 定义

Skill 是可复用能力包，不是 Agent。

Skill 描述一个可重复执行的工程能力，包括：触发条件、输入材料、执行步骤、工具需求、验证方式、输出模板和升级规则。

## 2. Skill 与 Agent 的关系

```text
Agent 负责判断和执行；
Skill 负责提供方法和检查清单；
Mode 负责专项治理；
工具负责真实动作。
```

示例：

```text
工部 Agent + bugfix Skill + filesystem/shell 工具 = Bug 修复执行能力
刑部 Agent + release-validation Skill + CI 工具 = 发布验证能力
中书省 Agent + api-development Skill = API 方案和契约能力
```

## 3. Skill 文件结构

每个 Skill 使用 `SKILL.md`：

```md
# Skill 名称

## 1. 适用场景
## 2. 不适用场景
## 3. 输入材料
## 4. 执行步骤
## 5. 工具需求
## 6. 工程门禁
## 7. 输出模板
## 8. 升级规则
## 9. 常见错误
```

## 4. 第一批 Skill

| Skill | 用途 |
|---|---|
| bugfix | Bug 复现、定位、修复、回归 |
| frontend-feature | 前端页面 / 组件 / 交互开发 |
| api-development | API 契约、实现、接口验证 |
| database-migration | 数据库结构和迁移治理 |
| docs-generation | README、API、用户说明生成 |
| release-validation | 发布前验证、回滚检查 |
| security-review | 权限、安全、Secret、越权检查 |

## 5. Skill 新增规则

新增 Skill 必须满足：

```text
能在多个任务中复用；
有明确触发条件；
有明确输入输出；
能绑定工程门禁；
能减少 Agent 膨胀；
不会与现有 Skill 重复。
```

## 6. Skill 调用规则

任务路由器负责选择 Skill。

```text
L1：最多 1 个 Skill；
L2：允许 1-3 个 Skill；
L3：允许多个 Skill，但必须由尚书省调度；
L4：不直接调用 Skill，先拆子任务。
```

## 7. Skill 输出要求

Skill 输出必须可被 Agent 汇总：

```text
做了什么；
改了什么；
验证了什么；
没覆盖什么；
风险是什么；
是否建议交付。
```

## 8. Skill 数据输入输出边界

每个 Skill 必须在 `SKILL.md` 中声明：

```text
允许读取的数据；
允许写入的数据；
禁止处理的数据；
是否会产生 artifact；
是否会写入史官；
是否会进入 pgvector；
是否需要脱敏；
需要哪些门禁。
```

Skill 不得把临时推理、scratchpad、Secret、生产数据或完整日志写入长期记忆。
