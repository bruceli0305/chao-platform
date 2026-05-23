from typing import Any, Literal, TypedDict

GovernanceAgent = Literal["menxia", "hubu", "bingbu"]
SELF_UPGRADE_GOVERNANCE_AGENTS: tuple[GovernanceAgent, ...] = ("menxia", "hubu", "bingbu")


class RequiredArtifactCheck(TypedDict):
    artifact_type: str
    present: bool
    artifact_uri: str | None


class GovernanceCheckResult(TypedDict):
    agent_name: str
    task_code: str
    task_level: str
    status: str
    deliverable: bool
    summary: str
    required_artifacts: list[RequiredArtifactCheck]
    missing_artifacts: list[str]


GOVERNANCE_REQUIRED_ARTIFACTS: dict[GovernanceAgent, list[str]] = {
    "menxia": ["l3_design_plan"],
    "hubu": ["l3_design_plan", "l3_menxia_review"],
    "bingbu": ["l3_design_plan", "l3_menxia_review", "l3_hubu_review"],
}


def list_self_upgrade_governance_agents(task: dict[str, Any]) -> list[GovernanceAgent]:
    if task.get("task_level") != "L3":
        return []

    return list(SELF_UPGRADE_GOVERNANCE_AGENTS)


def build_governance_check_result(
    task: dict[str, Any],
    *,
    agent_name: str,
) -> GovernanceCheckResult:
    if agent_name not in GOVERNANCE_REQUIRED_ARTIFACTS:
        raise ValueError(f"unsupported governance agent: {agent_name}")

    task_level = str(task.get("task_level") or "")
    artifact_rows = task.get("artifacts") or []
    artifacts_by_type = {
        str(artifact.get("artifact_type")): str(artifact.get("artifact_uri"))
        for artifact in artifact_rows
        if isinstance(artifact, dict) and artifact.get("artifact_type")
    }

    required_artifacts = []
    missing_artifacts = []
    for artifact_type in GOVERNANCE_REQUIRED_ARTIFACTS[agent_name]:  # type: ignore[index]
        artifact_uri = artifacts_by_type.get(artifact_type)
        present = bool(artifact_uri)
        required_artifacts.append(
            {
                "artifact_type": artifact_type,
                "present": present,
                "artifact_uri": artifact_uri,
            }
        )
        if not present:
            missing_artifacts.append(artifact_type)

    deliverable = task_level != "L3" or not missing_artifacts
    if task_level != "L3":
        status = "not_required"
        summary = f"{agent_name} governance check is not required for {task_level}."
    elif deliverable:
        status = "passed"
        summary = f"{agent_name} governance artifact chain is complete."
    else:
        status = "blocked"
        summary = (
            f"{agent_name} governance artifact chain is missing: {', '.join(missing_artifacts)}."
        )

    return {
        "agent_name": agent_name,
        "task_code": str(task.get("task_code") or ""),
        "task_level": task_level,
        "status": status,
        "deliverable": deliverable,
        "summary": summary,
        "required_artifacts": required_artifacts,
        "missing_artifacts": missing_artifacts,
    }
