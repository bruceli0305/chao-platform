from langgraph.graph import StateGraph, START, END

from app.chao.state import ChaoState
from app.chao.nodes.historian import historian_record_raw, historian_record_result
from app.chao.nodes.router import task_router
from app.chao.nodes.gongbu import gongbu_execute
from app.chao.nodes.xingbu import xingbu_validate

def route_by_level(state: ChaoState) -> str:
    if state["task_level"] in ["L3", "L4"]:
        return "need_confirmation"
    return "gongbu_execute"

def need_confirmation(state: ChaoState) -> ChaoState:
    return {
        **state,
        "status": "NEED_CONFIRMATION",
    }

def build_graph():
    builder = StateGraph(ChaoState)

    builder.add_node("historian_record_raw", historian_record_raw)
    builder.add_node("task_router", task_router)
    builder.add_node("need_confirmation", need_confirmation)
    builder.add_node("gongbu_execute", gongbu_execute)
    builder.add_node("xingbu_validate", xingbu_validate)
    builder.add_node("historian_record_result", historian_record_result)

    builder.add_edge(START, "historian_record_raw")
    builder.add_edge("historian_record_raw", "task_router")

    builder.add_conditional_edges(
        "task_router",
        route_by_level,
        {
            "gongbu_execute": "gongbu_execute",
            "need_confirmation": "need_confirmation",
        },
    )

    builder.add_edge("need_confirmation", END)
    builder.add_edge("gongbu_execute", "xingbu_validate")
    builder.add_edge("xingbu_validate", "historian_record_result")
    builder.add_edge("historian_record_result", END)

    return builder.compile()
