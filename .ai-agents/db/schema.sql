create table tasks (
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

create table task_routes (
  id uuid primary key,
  task_id uuid references tasks(id),
  risk_types jsonb not null default '[]',
  confirmation_level text not null default 'none',
  required_agents jsonb not null default '[]',
  required_modes jsonb not null default '[]',
  required_skills jsonb not null default '[]',
  required_gates jsonb not null default '[]',
  allowed_scope jsonb not null default '[]',
  forbidden_scope jsonb not null default '[]',
  next_action text not null,
  created_at timestamptz not null default now()
);

create table task_events (
  id uuid primary key,
  task_id uuid references tasks(id),
  event_type text not null,
  from_status text,
  to_status text,
  content text,
  created_by text,
  created_at timestamptz not null default now()
);

create table historian_records (
  id uuid primary key,
  task_id uuid references tasks(id),
  record_type text not null,
  content text not null,
  source text,
  created_by text,
  created_at timestamptz not null default now()
);

create table gate_results (
  id uuid primary key,
  task_id uuid references tasks(id),
  gate_name text not null,
  status text not null,
  command text,
  output text,
  created_at timestamptz not null default now()
);

create table tool_calls (
  id uuid primary key,
  task_id uuid references tasks(id),
  agent_name text not null,
  tool_name text not null,
  arguments_summary text,
  permission_policy text,
  result_status text,
  output_hash text,
  risk_flag text,
  started_at timestamptz not null default now(),
  finished_at timestamptz
);


-- Data storage boundary extensions

create table data_assets (
  id uuid primary key,
  task_id uuid references tasks(id),
  asset_name text not null,
  asset_type text not null,
  data_classification text not null,
  primary_storage text not null,
  storage_uri text,
  contains_secret boolean not null default false,
  contains_personal_data boolean not null default false,
  contains_production_data boolean not null default false,
  redacted boolean not null default false,
  vector_ingest_allowed boolean not null default false,
  retention_policy text not null default 'project_default',
  checksum text,
  created_at timestamptz not null default now()
);

create table storage_policies (
  id uuid primary key,
  policy_name text unique not null,
  data_classification text not null,
  allowed_storage jsonb not null default '[]',
  forbidden_storage jsonb not null default '[]',
  vector_ingest_allowed boolean not null default false,
  default_retention text not null,
  requires_approval boolean not null default false,
  owner_role text not null,
  created_at timestamptz not null default now()
);

create table artifact_records (
  id uuid primary key,
  task_id uuid references tasks(id),
  artifact_type text not null,
  storage_uri text not null,
  data_classification text not null,
  access_policy text not null,
  retention_policy text not null,
  checksum text,
  redacted boolean not null default false,
  created_at timestamptz not null default now()
);
