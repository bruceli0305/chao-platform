from app.chao.runner_validation import (
    build_runner_validation_result,
)
from app.chao.state import ChaoState


def resolve_validation_gates(state: ChaoState) -> list[str]:
    skill_execution_plan = state.get("skill_execution_plan") or {}
    combined_gates = skill_execution_plan.get("combined_gates")

    if combined_gates:
        return list(combined_gates)

    return state.get("required_gates", [])


def xingbu_validate(state: ChaoState) -> ChaoState:
    validation_result = build_runner_validation_result(resolve_validation_gates(state))
    status = "VALIDATING" if validation_result["deliverable"] else "VALIDATION_FAILED"

    return {
        **state,
        "status": status,
        "validation_result": validation_result,
    }
