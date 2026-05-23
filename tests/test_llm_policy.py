import pytest

from app.chao.llm_policy import evaluate_llm_egress_policy, resolve_task_data_classification


def test_llm_egress_policy_allows_l1_d1_execute():
    decision = evaluate_llm_egress_policy(
        task_level="L1",
        data_classification="D1",
        provider="deepseek",
        model="deepseek-v4-pro",
        execute=True,
    )

    assert decision.allowed is True
    assert decision.reason == "external LLM egress allowed"


def test_llm_egress_policy_allows_dry_run_for_high_classification():
    decision = evaluate_llm_egress_policy(
        task_level="L4",
        data_classification="D3",
        provider="openai-compatible",
        model="custom-model",
        execute=False,
    )

    assert decision.allowed is True
    assert decision.reason == "dry-run does not call external provider"


def test_llm_egress_policy_denies_l3_execute():
    decision = evaluate_llm_egress_policy(
        task_level="L3",
        data_classification="D1",
        provider="deepseek",
        model="deepseek-v4-pro",
        execute=True,
    )

    assert decision.allowed is False
    assert decision.reason == "L3 tasks cannot call external LLM providers"


def test_llm_egress_policy_allows_l3_execute_with_governed_approval():
    decision = evaluate_llm_egress_policy(
        task_level="L3",
        data_classification="D1",
        provider="deepseek",
        model="deepseek-v4-pro",
        execute=True,
        governed_egress_approved=True,
    )

    assert decision.allowed is True
    assert decision.reason == "external LLM egress allowed by governed approval"
    assert decision.to_dict()["governed_egress_approved"] is True


def test_llm_egress_policy_denies_d2_execute():
    decision = evaluate_llm_egress_policy(
        task_level="L2",
        data_classification="D2",
        provider="deepseek",
        model="deepseek-v4-pro",
        execute=True,
    )

    assert decision.allowed is False
    assert decision.reason == "D2 data cannot be sent to external LLM providers"


def test_resolve_task_data_classification_uses_highest_task_asset_classification():
    task = {
        "data_assets": [
            {"classification": "D1"},
            {"classification": "D3"},
        ]
    }

    assert resolve_task_data_classification(task, "D0") == "D3"


def test_llm_egress_policy_rejects_unknown_data_classification():
    with pytest.raises(ValueError, match="unsupported data classification"):
        evaluate_llm_egress_policy(
            task_level="L2",
            data_classification="PUBLIC",
            provider="deepseek",
            model="deepseek-chat",
            execute=True,
        )


def test_llm_egress_policy_denies_unallowlisted_provider_model():
    decision = evaluate_llm_egress_policy(
        task_level="L2",
        data_classification="D1",
        provider="openai-compatible",
        model="custom-model",
        execute=True,
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == "openai-compatible/custom-model is not allowlisted for external LLM execution"
    )


def test_llm_egress_policy_denies_unallowlisted_model_for_provider():
    decision = evaluate_llm_egress_policy(
        task_level="L2",
        data_classification="D1",
        provider="deepseek",
        model="deepseek-reasoner",
        execute=True,
    )

    assert decision.allowed is False
    assert (
        decision.reason
        == "deepseek/deepseek-reasoner is not allowlisted for external LLM execution"
    )
