alter table context_chunks
add column if not exists source_type text not null default 'markdown',
add column if not exists source_hash text,
add column if not exists data_classification text not null default 'D1',
add column if not exists redacted boolean not null default false,
add column if not exists ingest_allowed boolean not null default false,
add column if not exists retention_policy text not null default 'project_default',
add column if not exists created_by text not null default 'system';

create index if not exists idx_context_chunks_source_hash
on context_chunks(source_hash);

create index if not exists idx_context_chunks_ingest_allowed
on context_chunks(ingest_allowed);
