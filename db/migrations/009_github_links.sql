create table if not exists github_links (
  id uuid primary key,
  task_id uuid not null references tasks(id),
  link_type text not null,
  external_id text not null,
  url text not null,
  title text,
  status text,
  metadata jsonb not null default '{}',
  created_by text not null default 'system',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (task_id, link_type, external_id)
);

create index if not exists idx_github_links_task_id
on github_links(task_id);

create index if not exists idx_github_links_type_external_id
on github_links(link_type, external_id);
