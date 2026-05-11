from app.chao.skills import describe_required_skills, select_required_skills
from app.chao.state import ChaoState


def task_router(state: ChaoState) -> ChaoState:
    raw = state["raw_request"]

    l4_keywords = [
        "L4",
        "里程碑",
        "路线图",
        "多阶段",
        "跨阶段",
        "整体规划",
        "完整平台",
        "平台级",
        "多个子任务",
        "拆解成多个",
    ]

    l3_keywords = [
        "数据库",
        "迁移",
        "权限",
        "登录",
        "认证",
        "鉴权",
        "部署",
        "生产",
        "第三方",
        "Secret",
        "密钥",
        "架构",
        "技术栈",
        "回滚",
    ]

    l2_keywords = [
        "新增页面",
        "新增接口",
        "接口",
        "API",
        "前后端",
        "表单",
        "列表",
        "模块",
        "字段",
        "状态",
    ]

    if any(k in raw for k in l4_keywords):
        task_level = "L4"
        level_reason = "命中 L4 / 里程碑 / 多阶段 / 平台级规划关键词。"
        required_confirmation = "A"
        required_agents = ["historian", "shangshu", "zhongshu", "menxia"]
        required_gates = ["milestone_review", "manual_validation"]
        risk_types = ["milestone_planning"]
    elif any(k in raw for k in l3_keywords):
        task_level = "L3"
        level_reason = "命中数据库 / 权限 / 部署 / Secret / 架构等高风险关键词。"
        required_confirmation = "A"
        required_agents = [
            "historian",
            "shangshu",
            "zhongshu",
            "menxia",
            "gongbu",
            "xingbu",
        ]
        required_gates = ["build", "test", "secret_scan", "manual_validation"]
        risk_types = ["implementation"]
    elif any(k in raw for k in l2_keywords):
        task_level = "L2"
        level_reason = "命中普通功能 / 接口 / 多文件协作关键词。"
        required_confirmation = "B"
        required_agents = ["historian", "shangshu", "zhongshu", "gongbu", "xingbu"]
        required_gates = ["typecheck", "lint", "build", "manual_validation"]
        risk_types = ["implementation"]
    else:
        task_level = "L1"
        level_reason = "低风险单点任务。"
        required_confirmation = "none"
        required_agents = ["historian", "shangshu", "gongbu", "xingbu"]
        required_gates = ["manual_validation"]
        risk_types = ["implementation"]

    required_skills = select_required_skills(raw, task_level)
    required_skill_details = describe_required_skills(required_skills)
    required_skill_paths = [skill["path"] for skill in required_skill_details]

    return {
        **state,
        "task_level": task_level,
        "level_reason": level_reason,
        "risk_types": risk_types,
        "required_confirmation": required_confirmation,
        "required_agents": required_agents,
        "required_gates": required_gates,
        "required_skills": required_skills,
        "required_skill_paths": required_skill_paths,
        "required_skill_details": required_skill_details,
        "status": "CLASSIFIED",
        "route_result": {
            "task_level": task_level,
            "level_reason": level_reason,
            "risk_types": risk_types,
            "required_confirmation": required_confirmation,
            "required_agents": required_agents,
            "required_gates": required_gates,
            "required_skills": required_skills,
            "required_skill_paths": required_skill_paths,
            "required_skill_details": required_skill_details,
        },
    }
