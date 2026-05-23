from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_bootstrap_db_script_uses_docker_without_destructive_reset():
    script = (REPO_ROOT / "scripts" / "bootstrap_db.sh").read_text(encoding="utf-8")

    assert "docker compose up -d postgres" in script
    assert 'docker exec "$CONTAINER_NAME" pg_isready' in script
    assert "< db/init/001_init.sql" in script
    assert "for migration in db/migrations/*.sql" in script
    assert "uv run python scripts/schema_check.py" in script
    assert "docker compose down -v" not in script
    assert "rm -rf" not in script


def test_first_run_smoke_covers_doctor_and_self_upgrade_commands():
    script = (REPO_ROOT / "scripts" / "first_run_smoke.sh").read_text(encoding="utf-8")

    assert "uv run python main.py doctor --json" in script
    assert "uv run python scripts/schema_check.py" in script
    assert "uv run python scripts/data_boundary_check.py" in script
    assert "uv run python main.py agents-validate --json" in script
    assert "uv run python main.py skills-validate --json" in script
    assert "uv run python main.py self-upgrade --help" in script
    assert "uv run python main.py self-upgrade-status --help" in script
    assert "uv run python main.py self-upgrade-watch --help" in script
    assert "uv run python main.py governance-check --help" in script
    assert "bash scripts/self_upgrade_e2e_smoke.sh --help" in script


def test_self_upgrade_e2e_smoke_defaults_to_dry_run_and_guards_apply():
    script = (REPO_ROOT / "scripts" / "self_upgrade_e2e_smoke.sh").read_text(encoding="utf-8")

    assert "uv run python main.py doctor --json" in script
    assert "uv run python main.py agents-validate --json" in script
    assert "uv run python main.py skills-validate --json" in script
    assert "apply=false" in script
    assert 'if [[ "${apply}" == "true" ]]; then' in script
    assert 'uv run python main.py self-upgrade "${task_code}" "${request}" \\' in script
    assert "--execute" in script
    assert "--apply" in script
    assert "--branch" in script
    assert "--commit" in script
    assert "--push" in script
    assert "--create-pr" in script
    assert "--check-ci" in script
    assert 'uv run python main.py self-upgrade-watch "${task_code}"' in script
    assert 'uv run python main.py self-upgrade "${task_code}" "${request}"' in script


def test_first_run_runbook_documents_bootstrap_smoke_and_upgrade_flow():
    runbook = (REPO_ROOT / "docs" / "18-first-run-self-upgrade-runbook.md").read_text(
        encoding="utf-8"
    )

    assert "bash scripts/bootstrap_db.sh" in runbook
    assert "uv run python main.py doctor --json" in runbook
    assert "bash scripts/first_run_smoke.sh" in runbook
    assert "bash scripts/self_upgrade_e2e_smoke.sh" in runbook
    assert "--execute --apply --branch --commit --push --create-pr --check-ci" in runbook
