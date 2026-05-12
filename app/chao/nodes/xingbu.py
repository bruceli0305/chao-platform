from app.chao.runner_validation import (
    build_runner_validation_result,
    require_runner_validation_success,
)
from app.chao.state import ChaoState


def xingbu_validate(state: ChaoState) -> ChaoState:
    validation_result = build_runner_validation_result(
        state.get("required_gates", []),
    )
    require_runner_validation_success(validation_result)

    return {
        **state,
        "status": "VALIDATING",
        "validation_result": validation_result,
    }
