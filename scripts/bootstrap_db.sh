#!/usr/bin/env bash
set -euo pipefail

CONTAINER_NAME="${CHAO_POSTGRES_CONTAINER:-chao-postgres}"
DB_USER="${CHAO_POSTGRES_USER:-chao}"
DB_NAME="${CHAO_POSTGRES_DB:-chao}"

echo "== Start PostgreSQL container =="
docker compose up -d postgres

echo "== Wait for PostgreSQL readiness =="
for attempt in $(seq 1 30); do
  if docker exec "$CONTAINER_NAME" pg_isready -U "$DB_USER" -d "$DB_NAME" >/dev/null 2>&1; then
    echo "PostgreSQL is ready"
    break
  fi

  if [[ "$attempt" == "30" ]]; then
    echo "PostgreSQL did not become ready in time" >&2
    exit 1
  fi

  sleep 1
done

echo "== Apply init schema =="
docker exec -i "$CONTAINER_NAME" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" \
  < db/init/001_init.sql

echo "== Apply migrations =="
for migration in db/migrations/*.sql; do
  echo "Applying $migration"
  docker exec -i "$CONTAINER_NAME" psql -v ON_ERROR_STOP=1 -U "$DB_USER" -d "$DB_NAME" \
    < "$migration"
done

echo "== Schema check =="
uv run python scripts/schema_check.py

echo "== Database bootstrap complete =="
