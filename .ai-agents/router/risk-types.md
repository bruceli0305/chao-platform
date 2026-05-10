# 风险类型 v3

| 风险类型 | 说明 | 默认归口 |
|---|---|---|
| requirement | 需求不清、范围变化 | 中书省 |
| api | 接口路径、参数、响应变化 | 中书省 + 门下省 |
| data | 数据模型、迁移、备份、回滚 | 中书省 + 户部 + 门下省 |
| permission | 权限、角色、越权风险 | 门下省 + 刑部 |
| dependency | 新增、删除、升级依赖 | 户部 |
| deployment | 部署、CI/CD、Nginx、Docker | 兵部 |
| security | Secret、敏感字段、注入风险 | 户部 + 兵部 + 刑部 |
| documentation | 正式文档、接口说明、发布说明 | 礼部 |
| bugfix | Bug 复现、根因、回归 | 刑部 + 工部 |
| implementation | 代码实现、修复、重构 | 工部 |
| architecture | 架构边界、模块职责、技术路线 | 中书省 + 门下省 |
| cost | 云资源、API 调用、付费服务 | 户部 + 皇帝确认 |

## data_storage

涉及以下情况时标记 `data_storage` 风险：

```text
新增或修改 PostgreSQL 表；
新增或修改 pgvector ingest 来源；
新增 artifact 存储；
新增日志保留策略；
新增 Secret 注入；
处理生产数据；
改变数据保留期限；
改变数据删除策略。
```

默认归口：中书省 + 户部 + 门下省；涉及部署时增加兵部。
