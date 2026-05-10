alter table data_assets
add column if not exists task_id uuid references tasks(id);

create index if not exists idx_data_assets_task_id
on data_assets(task_id);
