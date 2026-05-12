from datetime import datetime

from app.chao.state import ChaoState


def historian_record_raw(state: ChaoState) -> ChaoState:
    return {
        **state,
        "status": "ROUTING",
        "historian_records": [
            {
                "type": "raw_request",
                "content": state["raw_request"],
                "created_at": datetime.now().isoformat(),
            }
        ],
    }


def historian_record_result(state: ChaoState) -> ChaoState:
    validation_result = state.get("validation_result", {})

    if validation_result and not validation_result.get("deliverable", False):
        return {
            **state,
            "status": "VALIDATION_FAILED",
        }

    records = state.get("historian_records", [])
    records.append(
        {
            "type": "delivery_summary",
            "content": (
                f"任务 {state.get('task_code')} 已完成本地 MVP 流程。"
                f"等级：{state.get('task_level')}"
            ),
            "created_at": datetime.now().isoformat(),
        }
    )
    return {
        **state,
        "historian_records": records,
        "status": "DELIVERED",
    }
