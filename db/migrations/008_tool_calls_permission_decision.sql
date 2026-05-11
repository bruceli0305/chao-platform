alter table tool_calls
add column if not exists permission_decision jsonb not null default '{}';
