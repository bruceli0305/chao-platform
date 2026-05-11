from scripts import check_pr_task_binding


def test_extract_task_codes_accepts_current_and_legacy_codes():
    assert check_pr_task_binding.extract_task_codes(
        "Task Code: TASK-20260511-120000-123456 and TASK-20260511-120001"
    ) == [
        "TASK-20260511-120000-123456",
        "TASK-20260511-120001",
    ]


def test_check_pull_request_body_accepts_task_code():
    errors = check_pr_task_binding.check_pull_request_body(
        {
            "pull_request": {
                "body": "Task Code: TASK-20260511-120000-123456",
            }
        }
    )

    assert errors == []


def test_check_pull_request_body_rejects_missing_task_code():
    errors = check_pr_task_binding.check_pull_request_body(
        {
            "pull_request": {
                "body": "Task Code: TBD",
            }
        }
    )

    assert errors == [
        "PR description must include a valid Task Code, for example TASK-20260511-120000."
    ]


def test_main_skips_non_pull_request(monkeypatch, capsys):
    monkeypatch.setenv("GITHUB_EVENT_NAME", "push")

    assert check_pr_task_binding.main() == 0
    assert "skipped" in capsys.readouterr().out
