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
