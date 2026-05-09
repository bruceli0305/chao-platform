from app.chao.state import ChaoState

def task_router(state: ChaoState) -> ChaoState:
    raw = state["raw_request"]

    l3_keywords = [
        "数据库", "迁移", "权限", "登录", "认证", "鉴权",
        "部署", "生产", "第三方", "Secret", "密钥",
        "架构", "技术栈", "回滚"
    ]

    l2_keywords = [
        "新增页面", "新增接口", "接口", "API", "前后端",
        "表单", "列表", "模块", "字段", "状态"
    ]

    if any(k in raw for k in l3_keywords):
        task_level = "L3"
        level_reason = "命中数据库 / 权限 / 部署 / Secret / 架构等高风险关键词。"
        required_confirmation = "A"
        required_agents = ["historian", "shangshu", "zhongshu", "menxia", "gongbu", "xingbu"]
        required_gates = ["build", "test", "secret_scan", "manual_validation"]
    elif any(k in raw for k in l2_keywords):
        task_level = "L2"
        level_reason = "命中普通功能 / 接口 / 多文件协作关键词。"
        required_confirmation = "B"
        required_agents = ["historian", "shangshu", "zhongshu", "gongbu", "xingbu"]
        required_gates = ["typecheck", "lint", "build", "manual_validation"]
    else:
        task_level = "L1"
        level_reason = "低风险单点任务。"
        required_confirmation = "none"
        required_agents = ["historian", "shangshu", "gongbu", "xingbu"]
        required_gates = ["manual_validation"]

    return {
        **state,
        "task_level": task_level,
        "level_reason": level_reason,
        "risk_types": ["implementation"],
        "required_confirmation": required_confirmation,
        "required_agents": required_agents,
        "required_gates": required_gates,
        "status": "CLASSIFIED",
        "route_result": {
            "task_level": task_level,
            "level_reason": level_reason,
            "risk_types": ["implementation"],
            "required_confirmation": required_confirmation,
            "required_agents": required_agents,
            "required_gates": required_gates,
        },
    }
