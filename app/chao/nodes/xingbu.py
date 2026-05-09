from app.chao.state import ChaoState


def xingbu_validate(state: ChaoState) -> ChaoState:
    return {
        **state,
        "status": "VALIDATING",
        "validation_result": {
            "quality": "有条件可交付",
            "checks": state.get("required_gates", []),
            "note": "MVP 阶段只完成流程 smoke test。",
        },
    }
