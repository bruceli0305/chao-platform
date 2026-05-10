# Task Router v3

## 1. 输入

```text
用户原始需求；
当前项目上下文；
AGENTS.md；
任务等级规则；
风险类型规则；
确认规则；
工程门禁规则。
```

## 2. 输出模板

```md
# 任务路由结果 v3

## 任务编号
TASK-YYYYMMDD-001

## 原始需求

## 任务等级
L1 / L2 / L3 / L4

## 定级依据

## 风险类型
requirement / api / data / permission / dependency / deployment / security / documentation / bugfix / implementation / architecture / cost

## 确认等级
A / B / C / none

## 确认事项

## 需要启用的 Agent

## 需要启用的 Mode

## 需要启用的 Skill

## 不启用项及原因

## 允许修改范围

## 禁止修改范围

## 工程门禁

## 下一步状态
execute / clarify / design / review / block

## 阻塞问题
```

## 3. 路由规则

```text
小事快闭；
大事严治；
风险升级；
工具受控；
没有验证不得交付。
```

## 数据存储边界判断

任务路由器必须判断：

```text
是否新增 / 修改存储位置；
是否新增数据库表或字段；
是否新增向量索引来源；
是否涉及 Secret / Token / 私钥；
是否涉及生产数据或个人隐私；
是否涉及日志、artifact、CI 输出保留；
是否需要数据脱敏；
是否需要户部、兵部、门下省介入。
```

输出中必须包含 `data_classification` 与 `storage_policy`。
