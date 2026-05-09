insert into storage_policies (
  id,
  policy_name,
  classification,
  allowed_storages,
  forbidden_storages,
  allow_vectorization,
  require_desensitization,
  retention_days,
  owner,
  notes
)
values
(
  gen_random_uuid(),
  'D0_PUBLIC_KNOWLEDGE',
  'D0',
  array['Git', 'Markdown', 'PostgreSQL', 'pgvector'],
  array['Secret Manager'],
  true,
  false,
  3650,
  'historian',
  '公开知识，可长期归档和检索。'
),
(
  gen_random_uuid(),
  'D1_INTERNAL_ENGINEERING_KNOWLEDGE',
  'D1',
  array['Git', 'Markdown', 'PostgreSQL', 'pgvector'],
  array['Secret Manager'],
  true,
  true,
  3650,
  'historian',
  '内部工程知识，可脱敏后进入检索索引。'
),
(
  gen_random_uuid(),
  'D2_SENSITIVE_ENGINEERING_DATA',
  'D2',
  array['PostgreSQL', 'GitHub', 'Artifact Store'],
  array['Git', 'Markdown', 'pgvector'],
  false,
  true,
  365,
  'hubu',
  '敏感工程数据，只保存摘要、哈希、引用和证据指针。'
),
(
  gen_random_uuid(),
  'D3_STRICT_SECRET_DATA',
  'D3',
  array['Secret Manager', 'GitHub Secrets', 'Local .env'],
  array['PostgreSQL', 'Git', 'Markdown', 'pgvector', 'logs', 'Artifact Store'],
  false,
  true,
  null,
  'hubu',
  'Secret、Token、私钥、生产密码等严格敏感数据，不得进入长期记录和索引。'
),
(
  gen_random_uuid(),
  'D4_TEMP_EXECUTION_DATA',
  'D4',
  array['Workspace', 'Sandbox', 'CI Temp'],
  array['PostgreSQL', 'Git', 'Markdown', 'pgvector'],
  false,
  true,
  1,
  'gongbu',
  '临时执行数据默认短期保留，不进入长期记忆。'
)
on conflict (policy_name) do update set
  classification = excluded.classification,
  allowed_storages = excluded.allowed_storages,
  forbidden_storages = excluded.forbidden_storages,
  allow_vectorization = excluded.allow_vectorization,
  require_desensitization = excluded.require_desensitization,
  retention_days = excluded.retention_days,
  owner = excluded.owner,
  notes = excluded.notes;
