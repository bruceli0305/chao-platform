from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_llm_egress_audit_workflow_runs_scheduled_apply_audit():
    workflow = (ROOT / ".github/workflows/llm-egress-audit.yml").read_text(encoding="utf-8")

    assert "schedule:" in workflow
    assert "workflow_dispatch:" in workflow
    assert "issues: write" in workflow
    assert "CHAO_AUDIT_DATABASE_URL" in workflow
    assert "llm-egress-audit-result.json" in workflow
    assert "expired_count=$EXPIRED_COUNT" in workflow
    assert "uv run python main.py audit-llm-egress-authorizations --apply --by xingbu" in workflow
    assert "select count(*) from llm_egress_authorizations" in workflow
    assert 'gh issue create --title "$TITLE" --body-file "$BODY_FILE"' in workflow
    assert 'gh issue comment "$EXISTING_ISSUE" --body-file "$BODY_FILE"' in workflow
    assert "db/init/001_init.sql" in workflow


def test_github_task_sync_workflow_records_issue_pr_and_ci_events():
    workflow = (ROOT / ".github/workflows/github-task-sync.yml").read_text(encoding="utf-8")

    assert "issues:" in workflow
    assert "pull_request:" in workflow
    assert "workflow_run:" in workflow
    assert "CHAO_SYNC_DATABASE_URL" in workflow
    assert "scripts/record_github_delivery.py" in workflow
    assert "issues: write" in workflow
    assert "pull-requests: read" in workflow
    assert "actions: read" in workflow
    assert "Create GitHub task sync failure issue" in workflow
    assert 'gh issue create --title "$TITLE" --body-file "$BODY_FILE"' in workflow
    assert 'gh issue comment "$EXISTING_ISSUE" --body-file "$BODY_FILE"' in workflow
