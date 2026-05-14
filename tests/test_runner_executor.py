import pytest

from app.chao.runner_executor import apply_text_patch_operations


def test_apply_text_patch_operations_writes_allowed_file(tmp_path):
    target = tmp_path / "app" / "chao" / "demo.txt"
    target.parent.mkdir(parents=True)
    target.write_text("title = old\n", encoding="utf-8")

    result = apply_text_patch_operations(
        [
            {
                "path": "app/chao/demo.txt",
                "old_text": "title = old",
                "new_text": "title = new",
            }
        ],
        repo_root=tmp_path,
    )

    assert target.read_text(encoding="utf-8") == "title = new\n"
    assert result["applied"] is True
    assert result["changed_files"] == ["app/chao/demo.txt"]
    assert result["operations"][0]["replacement_count"] == 1
    assert "old_text" not in result["operations"][0]
    assert "new_text" not in result["operations"][0]


def test_apply_text_patch_operations_dry_run_does_not_write(tmp_path):
    target = tmp_path / "tests" / "demo.txt"
    target.parent.mkdir(parents=True)
    target.write_text("status = old\n", encoding="utf-8")

    result = apply_text_patch_operations(
        [
            {
                "path": "tests/demo.txt",
                "old_text": "status = old",
                "new_text": "status = new",
            }
        ],
        repo_root=tmp_path,
        dry_run=True,
    )

    assert target.read_text(encoding="utf-8") == "status = old\n"
    assert result["applied"] is False
    assert result["dry_run"] is True


def test_apply_text_patch_operations_applies_multiple_operations_per_file(tmp_path):
    target = tmp_path / "app" / "chao" / "demo.txt"
    target.parent.mkdir(parents=True)
    target.write_text("first = old\nsecond = old\n", encoding="utf-8")

    apply_text_patch_operations(
        [
            {
                "path": "app/chao/demo.txt",
                "old_text": "first = old",
                "new_text": "first = new",
            },
            {
                "path": "app/chao/demo.txt",
                "old_text": "second = old",
                "new_text": "second = new",
            },
        ],
        repo_root=tmp_path,
    )

    assert target.read_text(encoding="utf-8") == "first = new\nsecond = new\n"


def test_apply_text_patch_operations_rejects_out_of_scope_path(tmp_path):
    target = tmp_path / "README.md"
    target.write_text("old\n", encoding="utf-8")

    with pytest.raises(PermissionError, match="README.md"):
        apply_text_patch_operations(
            [
                {
                    "path": "README.md",
                    "old_text": "old",
                    "new_text": "new",
                }
            ],
            repo_root=tmp_path,
        )


def test_apply_text_patch_operations_requires_single_match(tmp_path):
    target = tmp_path / "app" / "chao" / "demo.txt"
    target.parent.mkdir(parents=True)
    target.write_text("same\nsame\n", encoding="utf-8")

    with pytest.raises(ValueError, match="matched 2 times"):
        apply_text_patch_operations(
            [
                {
                    "path": "app/chao/demo.txt",
                    "old_text": "same",
                    "new_text": "changed",
                }
            ],
            repo_root=tmp_path,
        )

    assert target.read_text(encoding="utf-8") == "same\nsame\n"
