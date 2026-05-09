from typing import Literal, TypedDict, Any

TaskLevel = Literal["L1", "L2", "L3", "L4"]

class ChaoState(TypedDict, total=False):
    task_id: str
    task_code: str
    title: str
    raw_request: str

    task_level: TaskLevel
    level_reason: str
    risk_types: list[str]
    required_confirmation: str
    required_agents: list[str]
    required_gates: list[str]

    status: str
    route_result: dict[str, Any]
    historian_records: list[dict[str, Any]]
    implementation_result: dict[str, Any]
    validation_result: dict[str, Any]
