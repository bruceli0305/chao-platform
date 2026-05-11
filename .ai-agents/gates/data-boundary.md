# data-boundary gate

## 目标

检查本次任务是否违反数据存储边界。

## 必检项

```text
1. 是否提交 .env、Token、私钥或 Secret 明文；
2. 是否把 Secret 写入 PostgreSQL、Markdown、日志或向量库；
3. 是否把生产数据或个人隐私写入测试、日志、文档或史官；
4. 是否新增数据库表、字段、artifact、日志保留策略或向量索引来源；
5. 是否已声明数据分级、主存储位置、保留期限和删除策略；
6. 是否完成日志脱敏和 artifact 内容检查；
7. 是否更新 .env.example 且未提交真实值。
8. 如涉及 pgvector ingest，是否符合 docs/15-pgvector-ingest-policy-v3.md。
```

## 结论

只能输出：

```text
通过；
有条件通过；
不通过。
```

## 输出报告

涉及数据存储、日志、artifact、Secret、向量化或生产数据的任务，必须按以下模板输出检查报告：

```text
.ai-agents/templates/data-boundary-report.md
```

报告必须明确：

```text
任务编号；
检查范围；
数据分级；
主存储位置；
允许副本；
禁止位置；
是否脱敏；
是否允许向量化；
保留策略；
执行过的检查；
发现问题；
未覆盖内容；
残余风险；
结论；
是否允许交付。
```
