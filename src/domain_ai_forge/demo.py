"""Built-in demo domain for Domain AI Forge."""

from __future__ import annotations

from pathlib import Path

from domain_ai_forge.adapters import RuleBasedModel
from domain_ai_forge.core import (
    Agent,
    Example,
    Harness,
    MultiAgentModel,
    OptimizationLoop,
    ToolCall,
    ToolEnvironment,
    contains_any,
    metadata_environment_state_matches,
    metadata_keyword_coverage,
    metadata_no_forbidden_terms,
    metadata_requires_agents,
    metadata_requires_tool_call,
    min_length,
)
from domain_ai_forge.domain_pack import load_domain_pack


ROOT = Path(__file__).resolve().parents[2]
CUSTOMER_SUPPORT_PACK = ROOT / "examples" / "customer_support"


def build_customer_support_demo() -> tuple[
    OptimizationLoop,
    dict[str, MultiAgentModel | RuleBasedModel],
    list[Example],
]:
    domain_pack = load_domain_pack(CUSTOMER_SUPPORT_PACK)
    examples = list(domain_pack.examples)

    harness = Harness(
        name="customer_support_harness",
        scorers=[
            metadata_keyword_coverage(weight=0.30),
            contains_any(["apology", "sorry", "I understand"], weight=0.10),
            metadata_no_forbidden_terms(weight=0.15),
            metadata_requires_agents(weight=0.15),
            metadata_requires_tool_call(weight=0.15),
            metadata_environment_state_matches(weight=0.10),
            min_length(80, weight=0.05),
        ],
        environment_factory=build_customer_support_environment,
        repetitions=2,
    )

    baseline = RuleBasedModel(
        name="baseline_support_bot",
        routes={
            "refund": "Refunds depend on eligibility and policy.",
            "package": "Please check tracking.",
        },
    )

    planner = Agent(
        name="planner",
        role="Plan a safe customer support response with policy checks.",
        model=RuleBasedModel(
            name="planner_model",
            routes={
                "refund": "Plan: verify purchase date, refund policy, eligibility, and next step.",
                "package": "Plan: apologize, inspect tracking, identify delay reason, and provide next step.",
            },
        ),
        output_key="plan",
    )

    domain_expert = Agent(
        name="domain_expert",
        role="Add domain policy and operational detail.",
        model=RuleBasedModel(
            name="domain_expert_model",
            routes={
                "refund": (
                    "Policy: explain refund eligibility, avoid guaranteed refund language, "
                    "and ask for order details before next step."
                ),
                "package": (
                    "Policy: provide tracking review, apology, escalation path, and next step "
                    "if the carrier scan is stale."
                ),
            },
        ),
        output_key="domain_notes",
    )

    tool_user = Agent(
        name="tool_user",
        role="Use operational tools to inspect the case state.",
        model=RuleBasedModel(
            name="tool_user_model",
            routes={
                "refund": "Tool evidence: order lookup completed and refund review was recorded.",
                "package": "Tool evidence: tracking lookup completed and shipping escalation was recorded.",
            },
        ),
        output_key="tool_evidence",
        tool_selector=customer_support_tool_selector,
    )

    responder = Agent(
        name="responder",
        role="Write the final customer-facing answer.",
        model=RuleBasedModel(
            name="responder_model",
            routes={
                "refund": (
                    "I understand the refund question. I can help check refund eligibility "
                    "against the policy, review the purchase timing, and share the next step "
                    "once the order details are available."
                ),
                "package": (
                    "Sorry about the delay. I can review tracking, check whether escalation is "
                    "needed, and give the customer a clear next step based on the latest scan."
                ),
            },
        ),
        output_key="final_response",
    )

    multi_agent = MultiAgentModel(
        name="multi_agent_support_v1",
        agents=[planner, domain_expert, tool_user, responder],
    )

    return (
        OptimizationLoop(harness=harness),
        {
            "baseline_support_bot": baseline,
            "multi_agent_support_v1": multi_agent,
        },
        examples,
    )


def build_customer_support_environment(example: object) -> ToolEnvironment:
    return ToolEnvironment(
        name="customer_support_sim",
        tools={
            "lookup_order": lookup_order,
            "open_refund_review": open_refund_review,
            "lookup_tracking": lookup_tracking,
            "open_shipping_escalation": open_shipping_escalation,
        },
        initial_state={"case_id": getattr(example, "id", ""), "status": "new"},
        cost_usd_per_call=0.0002,
    )


def customer_support_tool_selector(task: str, state: dict[str, str], env_state: dict[str, object]) -> list[ToolCall]:
    task_lower = task.lower()
    if "refund" in task_lower:
        return [
            ToolCall("lookup_order", {"order_id": "demo-order"}),
            ToolCall("open_refund_review", {"reason": "customer_requested_refund"}),
        ]

    if "package" in task_lower or "late" in task_lower:
        return [
            ToolCall("lookup_tracking", {"tracking_id": "demo-tracking"}),
            ToolCall("open_shipping_escalation", {"reason": "late_package"}),
        ]

    return []


def lookup_order(args: dict[str, object], state: dict[str, object]) -> dict[str, object]:
    return {
        "output": "Order demo-order was purchased yesterday and is eligible for policy review.",
        "state_delta": {"order_checked": True},
    }


def open_refund_review(args: dict[str, object], state: dict[str, object]) -> dict[str, object]:
    return {
        "output": "Refund review opened; agent must avoid guaranteed refund language.",
        "state_delta": {"refund_review_opened": True, "status": "refund_review"},
    }


def lookup_tracking(args: dict[str, object], state: dict[str, object]) -> dict[str, object]:
    return {
        "output": "Tracking scan is stale and needs escalation.",
        "state_delta": {"tracking_checked": True},
    }


def open_shipping_escalation(args: dict[str, object], state: dict[str, object]) -> dict[str, object]:
    return {
        "output": "Shipping escalation opened for the delayed package.",
        "state_delta": {"shipping_escalation_opened": True, "status": "shipping_escalation"},
    }
