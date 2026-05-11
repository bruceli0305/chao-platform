from app.chao.nodes.router import task_router


def test_router_classifies_l1():
    result = task_router(
        {
            "task_id": "test-l1",
            "task_code": "TASK-TEST-L1",
            "title": "修复文案",
            "raw_request": "把首页标题从系统管理改成项目管理",
            "status": "RAW",
        }
    )

    assert result["task_level"] == "L1"
    assert result["status"] == "CLASSIFIED"
    assert result["required_confirmation"] == "none"
    assert "gongbu" in result["required_agents"]
    assert "xingbu" in result["required_agents"]
    assert result["required_skills"] == ["bugfix"]
    assert result["route_result"]["required_skills"] == ["bugfix"]


def test_router_classifies_l2():
    result = task_router(
        {
            "task_id": "test-l2",
            "task_code": "TASK-TEST-L2",
            "title": "新增页面",
            "raw_request": "新增后台应用管理页面，包含列表、搜索和新增弹窗",
            "status": "RAW",
        }
    )

    assert result["task_level"] == "L2"
    assert result["required_confirmation"] == "B"
    assert "zhongshu" in result["required_agents"]
    assert "build" in result["required_gates"]
    assert "frontend-feature" in result["required_skills"]


def test_router_classifies_l3():
    result = task_router(
        {
            "task_id": "test-l3",
            "task_code": "TASK-TEST-L3",
            "title": "数据库迁移",
            "raw_request": "给用户表新增 status 字段，并迁移历史数据",
            "status": "RAW",
        }
    )

    assert result["task_level"] == "L3"
    assert result["required_confirmation"] == "A"
    assert "menxia" in result["required_agents"]
    assert "secret_scan" in result["required_gates"]
    assert "database-migration" in result["required_skills"]
