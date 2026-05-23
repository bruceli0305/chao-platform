# Chao First-Run and Self-Upgrade Runbook

This runbook is the first-version operating path for running Chao locally or on a server.

## 1. Prerequisites

Install and configure:

```bash
uv --version
docker --version
docker compose version
gh auth status
```

Required environment:

```bash
export DATABASE_URL="postgresql://chao:chao_dev_password@localhost:5432/chao"
export DEEPSEEK_API_KEY="..."
```

Do not commit `.env`, real tokens, private keys, `data/postgres`, `logs`, or `.venv`.

## 2. Bootstrap Database

Use Docker for database operations:

```bash
bash scripts/bootstrap_db.sh
```

The script starts `chao-postgres`, waits for readiness, applies `db/init/001_init.sql`, applies
all SQL files in `db/migrations/`, then runs:

```bash
uv run python scripts/schema_check.py
```

If Docker data was lost or a fresh server is used, run `bash scripts/bootstrap_db.sh` again.

## 3. Doctor

Check whether the first version can run:

```bash
uv run python main.py doctor
uv run python main.py doctor --json
```

Doctor checks:

- `uv`
- Docker PostgreSQL container and readiness
- database schema
- GitHub CLI authentication
- `DEEPSEEK_API_KEY`
- repository configuration
- repository workspace cleanliness

## 4. Smoke Test

Run the first-run smoke:

```bash
bash scripts/first_run_smoke.sh
```

This checks CLI status, doctor, schema, data boundary, ruff, compile, and self-upgrade command
availability.

## 5. Self-Upgrade Flow

Create or choose a task, then run:

```bash
uv run python main.py self-upgrade "$TASK_CODE" "upgrade request" \
  --execute \
  --apply \
  --branch \
  --commit \
  --push \
  --create-pr \
  --check-ci
```

If CI is still pending, re-check once:

```bash
uv run python main.py self-upgrade-status "$TASK_CODE"
```

Or watch until passed, failed, or timed out:

```bash
uv run python main.py self-upgrade-watch "$TASK_CODE" --interval 30 --attempts 20
```

You can pass a PR explicitly:

```bash
uv run python main.py self-upgrade-watch "$TASK_CODE" --pr-ref 42
uv run python main.py self-upgrade-watch "$TASK_CODE" --pr-ref https://github.com/ORG/REPO/pull/42
```

## 6. Normal Validation

Before pushing changes to this repository:

```bash
uv run ruff check app tests main.py
uv run ruff format --check app tests main.py
uv run pytest -q
./scripts/check.sh
```

## 7. Failure Triage

Common blockers:

- `doctor` reports missing `uv`: install uv on the machine running Chao.
- `doctor` reports Docker/PostgreSQL blocked: run `bash scripts/bootstrap_db.sh`.
- `schema_check` reports missing tables: run `bash scripts/bootstrap_db.sh`.
- `doctor` reports GitHub auth blocked: run `gh auth login`.
- `self-upgrade` LLM execution fails: verify `DEEPSEEK_API_KEY`.
- `self-upgrade-watch` exits `ci_pending`: increase `--attempts` or run it again later.
- `self-upgrade-watch` exits `ci_failed`: inspect the PR checks, fix, then rerun validation.
