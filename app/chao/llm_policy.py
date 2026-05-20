from dataclasses import dataclass
from typing import Any

ALLOWED_EXECUTE_TASK_LEVELS = {"L1", "L2"}
GOVERNED_EXECUTE_TASK_LEVELS = {"L3", "L4"}
ALLOWED_EXECUTE_DATA_CLASSIFICATIONS = {"D0", "D1"}
ALLOWED_EXECUTE_PROVIDER_MODELS = {
    "anthropic": {"claude-3-5-sonnet-latest"},
    "deepseek": {"deepseek-chat"},
    "openai": {"gpt-4.1-mini"},
}
DATA_CLASSIFICATION_ORDER = {"D0": 0, "D1": 1, "D2": 2, "D3": 3, "D4": 4}


@dataclass(frozen=True)
class LLMEgressDecision:
    allowed: bool
    reason: str
    task_level: str
    data_classification: str
    provider: str
    model: str
    execute: bool
    governed_egress_approved: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "allowed": self.allowed,
            "reason": self.reason,
            "task_level": self.task_level,
            "data_classification": self.data_classification,
            "provider": self.provider,
            "model": self.model,
            "execute": self.execute,
            "governed_egress_approved": self.governed_egress_approved,
        }


def resolve_task_data_classification(
    task: dict[str, Any],
    requested_classification: str = "D1",
) -> str:
    classifications = [normalize_data_classification(requested_classification)]

    for asset in task.get("data_assets") or []:
        classification = asset.get("classification")
        if classification:
            classifications.append(normalize_data_classification(str(classification)))

    return max(classifications, key=lambda item: DATA_CLASSIFICATION_ORDER[item])


def is_llm_provider_model_allowlisted(provider: str, model: str) -> bool:
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip()
    return normalized_model in ALLOWED_EXECUTE_PROVIDER_MODELS.get(normalized_provider, set())


def is_data_classification_covered(
    *,
    authorized_classification: str,
    requested_classification: str,
) -> bool:
    normalized_authorized = normalize_data_classification(authorized_classification)
    normalized_requested = normalize_data_classification(requested_classification)
    return (
        DATA_CLASSIFICATION_ORDER[normalized_authorized]
        >= DATA_CLASSIFICATION_ORDER[normalized_requested]
    )


def evaluate_llm_egress_policy(
    *,
    task_level: str,
    data_classification: str,
    provider: str,
    model: str,
    execute: bool,
    governed_egress_approved: bool = False,
) -> LLMEgressDecision:
    normalized_level = normalize_task_level(task_level)
    normalized_classification = normalize_data_classification(data_classification)
    normalized_provider = provider.strip().lower()
    normalized_model = model.strip()

    if not execute:
        return LLMEgressDecision(
            allowed=True,
            reason="dry-run does not call external provider",
            task_level=normalized_level,
            data_classification=normalized_classification,
            provider=normalized_provider,
            model=normalized_model,
            execute=False,
            governed_egress_approved=governed_egress_approved,
        )

    if not is_llm_provider_model_allowlisted(normalized_provider, normalized_model):
        return LLMEgressDecision(
            allowed=False,
            reason=(
                f"{normalized_provider}/{normalized_model} is not allowlisted "
                "for external LLM execution"
            ),
            task_level=normalized_level,
            data_classification=normalized_classification,
            provider=normalized_provider,
            model=normalized_model,
            execute=True,
            governed_egress_approved=governed_egress_approved,
        )

    governed_level_allowed = (
        governed_egress_approved and normalized_level in GOVERNED_EXECUTE_TASK_LEVELS
    )
    if normalized_level not in ALLOWED_EXECUTE_TASK_LEVELS and not governed_level_allowed:
        return LLMEgressDecision(
            allowed=False,
            reason=f"{normalized_level} tasks cannot call external LLM providers",
            task_level=normalized_level,
            data_classification=normalized_classification,
            provider=normalized_provider,
            model=normalized_model,
            execute=True,
            governed_egress_approved=governed_egress_approved,
        )

    if normalized_classification not in ALLOWED_EXECUTE_DATA_CLASSIFICATIONS:
        return LLMEgressDecision(
            allowed=False,
            reason=f"{normalized_classification} data cannot be sent to external LLM providers",
            task_level=normalized_level,
            data_classification=normalized_classification,
            provider=normalized_provider,
            model=normalized_model,
            execute=True,
            governed_egress_approved=governed_egress_approved,
        )

    return LLMEgressDecision(
        allowed=True,
        reason=(
            "external LLM egress allowed by governed approval"
            if governed_level_allowed
            else "external LLM egress allowed"
        ),
        task_level=normalized_level,
        data_classification=normalized_classification,
        provider=normalized_provider,
        model=normalized_model,
        execute=True,
        governed_egress_approved=governed_egress_approved,
    )


def normalize_task_level(task_level: str) -> str:
    normalized = task_level.strip().upper()
    if normalized not in {"L1", "L2", "L3", "L4"}:
        raise ValueError(f"unsupported task level for LLM egress: {task_level}")
    return normalized


def normalize_data_classification(data_classification: str) -> str:
    normalized = data_classification.strip().upper()
    if normalized not in DATA_CLASSIFICATION_ORDER:
        raise ValueError(f"unsupported data classification for LLM egress: {data_classification}")
    return normalized
