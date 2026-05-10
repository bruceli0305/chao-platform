# 朝 v3 项目运行说明

## 1. 定位

“朝”v3 是仓库级 Agent DevOps 工程内核。

它以 `.ai-agents` 目录为项目内制度入口，以任务路由器、状态机、工程门禁和史官记录保证 AI 协助开发可控、可验、可复盘。

## 2. 目录职责

```text
router：任务定级、风险、确认、升级规则。
roles：核心 Agent 职责。
modes：按需专项模式。
experts：技术能力池说明。
workflows：L1-L4 和失败回流流程。
gates：工程门禁。
mcp：工具权限策略。
skills：可复用能力包。
templates：交付和记录模板。
records：史官记录。
db：数据库控制平面设计。
```

## 3. 最小执行流程

```text
用户需求
  ↓
router/task-router.md
  ↓
判断等级、风险、确认、角色、门禁
  ↓
按 workflows 进入 L1 / L2 / L3 / L4
  ↓
工部实现
  ↓
刑部验证
  ↓
史官记录
  ↓
交付
```
