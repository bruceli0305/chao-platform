#!/usr/bin/env bash
set -euo pipefail

echo "== Ruff check =="
uv run ruff check app tests main.py

echo "== Ruff format check =="
uv run ruff format --check app tests main.py

echo "== Pytest =="
uv run pytest -q

echo "== Schema check =="
uv run python scripts/schema_check.py

echo "== Data boundary check =="
uv run python scripts/data_boundary_check.py

echo "== Compile =="
uv run python -m compileall app tests main.py

echo "== CLI status =="
uv run python main.py status

echo "== Done =="
