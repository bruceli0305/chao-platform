from typing import Any, Literal, TypedDict

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
    required_skills: list[str]
    required_skill_paths: list[str]
    required_skill_details: list[dict[str, Any]]
    skill_usage: list[dict[str, Any]]
    skill_execution_plan: dict[str, Any]

    status: str
    route_result: dict[str, Any]
    historian_records: list[dict[str, Any]]
    runner_patch_operations: list[dict[str, str]]
    implementation_result: dict[str, Any]
    validation_result: dict[str, Any]
