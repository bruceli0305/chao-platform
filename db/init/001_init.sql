create extension if not exists vector;

create table if not exists tasks (
  id uuid primary key,
  task_code text unique not null,
  title text not null,
  raw_request text not null,
  task_level text not null,
  status text not null,
  owner text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists task_routes (
  id uuid primary key,
  task_id uuid references tasks(id),
  route_json jsonb not null,
  created_at timestamptz not null default now()
);

create table if not exists historian_records (
  id uuid primary key,
  task_id uuid references tasks(id),
  record_type text not null,
  content text not null,
  source text,
  created_by text,
  created_at timestamptz not null default now()
);

create table if not exists gate_results (
  id uuid primary key,
  task_id uuid references tasks(id),
  gate_name text not null,
  status text not null,
  command text,
  output text,
  created_at timestamptz not null default now()
);

create table if not exists context_chunks (
  id uuid primary key,
  source_path text not null,
  content text not null,
  embedding vector(1536),
  created_at timestamptz not null default now()
);

create table if not exists confirmations (
  id uuid primary key,
  task_id uuid references tasks(id),
  confirmation_level text not null,
  status text not null,
  confirmed_by text,
  note text,
  created_at timestamptz not null default now()
);
create table if not exists task_events (
  id uuid primary key,
  task_id uuid references tasks(id),
  event_type text not null,
  from_status text,
  to_status text,
  summary text not null,
  created_by text not null,
  created_at timestamptz not null default now()
);

create table if not exists tool_calls (
  id uuid primary key,
  task_id uuid references tasks(id),
  agent_name text not null,
  tool_name text not null,
  arguments_summary text,
  permission_policy text,
  result_status text not null,
  output_hash text,
  risk_flag text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);

create table if not exists artifacts (
  id uuid primary key,
  task_id uuid references tasks(id),
  artifact_type text not null,
  artifact_uri text not null,
  artifact_hash text,
  access_level text not null default 'internal',
  retention_days integer,
  summary text,
  created_at timestamptz not null default now()
);
create table if not exists data_assets (
  id uuid primary key,
  asset_name text not null,
  asset_type text not null,
  classification text not null,
  primary_storage text not null,
  allowed_copies text[] not null default '{}',
  forbidden_storages text[] not null default '{}',
  allow_vectorization boolean not null default false,
  desensitized boolean not null default false,
  retention_days integer,
  owner text not null,
  notes text,
  created_at timestamptz not null default now()
);

create table if not exists storage_policies (
  id uuid primary key,
  policy_name text unique not null,
  classification text not null,
  allowed_storages text[] not null default '{}',
  forbidden_storages text[] not null default '{}',
  allow_vectorization boolean not null default false,
  require_desensitization boolean not null default true,
  retention_days integer,
  owner text not null,
  notes text,
  created_at timestamptz not null default now()
);

create or replace view artifact_records as
select
  id,
  task_id,
  artifact_type,
  artifact_uri,
  artifact_hash,
  access_level,
  retention_days,
  summary,
  created_at
from artifacts;
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
alter table data_assets
add column if not exists task_id uuid references tasks(id);

create index if not exists idx_data_assets_task_id
on data_assets(task_id);
