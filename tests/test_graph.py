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
    assert len(result["historian_records"]) == 2


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
