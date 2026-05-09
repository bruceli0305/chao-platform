create table if not exists confirmations (
  id uuid primary key,
  task_id uuid references tasks(id),
  confirmation_level text not null,
  status text not null,
  confirmed_by text,
  note text,
  created_at timestamptz not null default now()
);
