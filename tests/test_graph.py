from app.chao.graph.main_graph import build_graph


def test_graph_l1_delivered():
    graph = build_graph()

    result = graph.invoke(
        {
            "task_id": "test-l1",
            "task_code": "TASK-TEST-L1",
            "title": "修复文案",
            "raw_request": "把首页标题从系统管理改成项目管理",
            "status": "RAW",
        }
    )

    assert result["task_level"] == "L1"
    assert result["status"] == "DELIVERED"
    assert len(result["historian_records"]) == 3
    assert result["skill_usage"][0]["name"] == "bugfix"
    assert result["historian_records"][1]["type"] == "skill_usage"


def test_graph_l2_delivered():
    graph = build_graph()

    result = graph.invoke(
        {
            "task_id": "test-l2",
            "task_code": "TASK-TEST-L2",
            "title": "新增页面",
            "raw_request": "新增后台应用管理页面，包含列表、搜索和新增弹窗",
            "status": "RAW",
        }
    )

    assert result["task_level"] == "L2"
    assert result["status"] == "DELIVERED"
    assert "validation_result" in result
    assert result["validation_result"]["deliverable"] is True
    assert result["validation_result"]["plan"]
    assert result["skill_usage"]


def test_graph_l3_needs_confirmation():
    graph = build_graph()

    result = graph.invoke(
        {
            "task_id": "test-l3",
            "task_code": "TASK-TEST-L3",
            "title": "数据库迁移",
            "raw_request": "给用户表新增 status 字段，并迁移历史数据",
            "status": "RAW",
        }
    )

    assert result["task_level"] == "L3"
    assert result["status"] == "NEED_CONFIRMATION"
    assert result["required_confirmation"] == "A"
    assert result["skill_usage"][0]["name"] == "database-migration"


def test_graph_l4_needs_confirmation_without_execution():
    graph = build_graph()

    result = graph.invoke(
        {
            "task_id": "test-l4",
            "task_code": "TASK-TEST-L4",
            "title": "平台级路线图",
            "raw_request": "规划完整平台路线图，拆解成多个子任务",
            "status": "RAW",
        }
    )

    assert result["task_level"] == "L4"
    assert result["status"] == "NEED_CONFIRMATION"
    assert result["required_confirmation"] == "A"
    assert "implementation_result" not in result
    assert "validation_result" not in result
