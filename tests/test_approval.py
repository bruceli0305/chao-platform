from app.chao.graph.main_graph import build_graph


def test_graph_l3_waits_for_confirmation():
    graph = build_graph()

    result = graph.invoke(
        {
            "task_id": "test-l3-approval",
            "task_code": "TASK-TEST-L3-APPROVAL",
            "title": "数据库迁移",
            "raw_request": "给用户表新增 status 字段，并迁移历史数据",
            "status": "RAW",
        }
    )

    assert result["task_level"] == "L3"
    assert result["required_confirmation"] == "A"
    assert result["status"] == "NEED_CONFIRMATION"
    assert "menxia" in result["required_agents"]
    assert "secret_scan" in result["required_gates"]
