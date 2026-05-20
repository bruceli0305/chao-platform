create table if not exists llm_egress_authorizations (
  id uuid primary key,
  task_id uuid not null references tasks(id),
  provider text not null,
  model text not null,
  data_classification text not null,
  status text not null,
  authorized_by text not null,
  reason text,
  expires_at timestamptz not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_llm_egress_authorizations_task_id
  on llm_egress_authorizations(task_id);

create index if not exists idx_llm_egress_authorizations_active
  on llm_egress_authorizations(task_id, provider, model, status, expires_at);
