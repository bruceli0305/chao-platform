from app.chao.runner_validation import (
    build_runner_validation_result,
)
from app.chao.state import ChaoState


def xingbu_validate(state: ChaoState) -> ChaoState:
    validation_result = build_runner_validation_result(
        state.get("required_gates", []),
    )
    status = "VALIDATING" if validation_result["deliverable"] else "VALIDATION_FAILED"

    return {
        **state,
        "status": status,
        "validation_result": validation_result,
    }
