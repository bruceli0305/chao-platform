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
