# Agent Runner Execution v3

This document records the J1 minimal execution step for the local MVP.

## Scope

J1 introduces a controlled text patch executor. It is deliberately narrow:

```text
Only explicit runner_patch_operations are executed.
Each operation targets one repository-relative file.
Each old_text must match exactly once.
Changed paths must pass the Agent Runner allowed scope policy.
Execution results store changed_files and text hashes, not raw replaced text.
Default CLI task creation still does not modify repository files automatically.
```

## Runtime Entry Points

```text
app/chao/runner_executor.py
app/chao/nodes/gongbu.py
app/chao/cli.py runner-patch
app/chao/cli.py runner-validate
app/chao/cli.py runner-attempt
tests/test_runner_executor.py
tests/test_gongbu_runner_scope.py
tests/test_cli_runner_patch.py
tests/test_cli_runner_validate.py
tests/test_cli_runner_attempt.py
```

## Operation Shape

```json
{
  "path": "app/chao/example.py",
  "old_text": "before",
  "new_text": "after"
}
```

## Safety Rules

```text
Reject empty old_text.
Reject path traversal and absolute paths.
Reject paths outside Runner allowed scope.
Reject missing files.
Reject old_text matches of zero or more than one.
Support dry_run for validation without writing.
```

## Next Step

J2 adds a controlled CLI command:

```bash
uv run python main.py runner-patch TASK-xxx app/chao/example.py \
  --old-text "before" \
  --new-text "after"
```

By default the command is dry-run only. Passing `--apply` writes the patch to
disk. The command records `task_events` and `tool_calls` after successful
validation or application.

The next J-stage step should connect applied patches to validation execution and
persist runner_patch / runner_failure_feedback artifacts from the patch attempt.

J3 adds an allowlisted validation command executor:

```bash
uv run python main.py runner-validate TASK-xxx --gate compile --timeout 60
```

The command runs only known executable gates from `app/chao/runner_validation.py`.
Manual or external gates fail explicitly instead of being treated as passed.
Successful and failed validation attempts are written to `task_events` and
`tool_calls`.

J4 adds a combined patch + validation attempt command:

```bash
uv run python main.py runner-attempt TASK-xxx app/chao/example.py \
  --old-text "before" \
  --new-text "after" \
  --gate compile \
  --apply
```

Without `--apply`, the command validates the patch and runs the gates but does
not write files or record patch artifacts. With `--apply`, it writes the patch,
runs validation, and records:

```text
runner_patch when validation passes;
runner_failure_feedback when validation fails.
```

J5 keeps the control plane status aligned with applied runner attempts:

```text
dry-run attempts record audit evidence but do not update tasks.status;
applied attempts update tasks.status to DELIVERED when validation passes;
applied attempts update tasks.status to VALIDATION_FAILED when validation fails.
```
