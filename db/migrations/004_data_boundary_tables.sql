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
