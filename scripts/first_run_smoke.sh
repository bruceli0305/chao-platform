#!/usr/bin/env bash
set -euo pipefail

echo "== CLI status =="
uv run python main.py status

echo "== Doctor =="
uv run python main.py doctor --json

echo "== Schema check =="
uv run python scripts/schema_check.py

echo "== Data boundary check =="
uv run python scripts/data_boundary_check.py

echo "== Agent registry =="
uv run python main.py agents-validate --json

echo "== Skill registry =="
uv run python main.py skills-validate --json

echo "== Ruff check =="
uv run ruff check app tests main.py

echo "== Compile =="
uv run python -m compileall app tests main.py

echo "== Self-upgrade commands are available =="
uv run python main.py self-upgrade --help >/dev/null
uv run python main.py self-upgrade-status --help >/dev/null
uv run python main.py self-upgrade-watch --help >/dev/null
uv run python main.py governance-check --help >/dev/null
bash scripts/self_upgrade_e2e_smoke.sh --help >/dev/null

echo "== First-run smoke passed =="
