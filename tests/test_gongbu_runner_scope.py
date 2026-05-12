import pytest

from app.chao.nodes import gongbu


def test_gongbu_checks_changed_files_scope(monkeypatch):
    checked_paths = []

    def fake_require_change_scope_allowed(paths):
        checked_paths.extend(paths)
        return {"allowed": True, "checked_paths": paths, "errors": []}

    monkeypatch.setattr(
        gongbu,
        "require_change_scope_allowed",
        fake_require_change_scope_allowed,
    )

    result = gongbu.gongbu_execute(
        {
            "task_id": "task-1",
            "task_code": "TASK-TEST",
            "title": "修复文案",
            "raw_request": "把首页标题从系统管理改成项目管理",
            "task_level": "L1",
            "status": "CLASSIFIED",
        }
    )

    assert result["status"] == "IMPLEMENTING"
    assert checked_paths == []


def test_gongbu_blocks_out_of_scope_changed_files(monkeypatch):
    def fake_require_change_scope_allowed(paths):
        raise PermissionError("路径不在 Agent Runner 允许修改范围内：README.md")

    monkeypatch.setattr(
        gongbu,
        "require_change_scope_allowed",
        fake_require_change_scope_allowed,
    )

    with pytest.raises(PermissionError, match="README.md"):
        gongbu.gongbu_execute(
            {
                "task_id": "task-1",
                "task_code": "TASK-TEST",
                "title": "修复文案",
                "raw_request": "把首页标题从系统管理改成项目管理",
                "task_level": "L1",
                "status": "CLASSIFIED",
            }
        )
