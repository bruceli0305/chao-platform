from app.chao.runner_executor import (
    apply_text_patch_operations,
    build_implementation_result_from_execution,
)
from app.chao.runner_policy import require_change_scope_allowed
from app.chao.state import ChaoState


def gongbu_execute(state: ChaoState) -> ChaoState:
    patch_operations = state.get("runner_patch_operations", [])

    if patch_operations:
        execution_result = apply_text_patch_operations(patch_operations)
        implementation_result = build_implementation_result_from_execution(execution_result)
    else:
        implementation_result = {
            "summary": "MVP runner did not receive executable patch operations.",
            "changed_files": [],
            "risk": "No repository files were modified.",
        }

    require_change_scope_allowed(
        implementation_result["changed_files"],
    )

    return {
        **state,
        "status": "IMPLEMENTING",
        "implementation_result": implementation_result,
    }
