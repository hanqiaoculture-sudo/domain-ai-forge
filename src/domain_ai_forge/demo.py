"""Built-in demo domain for Domain AI Forge."""

from __future__ import annotations

from domain_ai_forge.adapters import RuleBasedModel
from domain_ai_forge.core import (
    Agent,
    Example,
    Harness,
    MultiAgentModel,
    OptimizationLoop,
    contains_any,
    metadata_keyword_coverage,
    metadata_no_forbidden_terms,
    min_length,
)


def build_customer_support_demo() -> tuple[OptimizationLoop, dict[str, MultiAgentModel | RuleBasedModel], list[Example]]:
    examples = [
        Example(
            id="refund-001",
            input="A customer asks whether they can get a refund after buying yesterday.",
            expected="refund eligibility next steps",
            tags=("refund", "policy"),
            metadata={
                "pass_threshold": 0.75,
                "keywords": ["refund", "eligibility", "policy", "next step"],
                "forbidden_terms": ["guaranteed refund", "ignore policy"],
            },
        ),
        Example(
            id="shipping-001",
            input="A customer says the package is late and wants a clear next step.",
            expected="tracking escalation apology",
            tags=("shipping", "support"),
            metadata={
                "pass_threshold": 0.75,
                "keywords": ["tracking", "apology", "escalation", "next step"],
                "forbidden_terms": ["guaranteed delivery", "ignore tracking"],
            },
        ),
    ]

    harness = Harness(
        name="customer_support_harness",
        scorers=[
            metadata_keyword_coverage(weight=0.45),
            contains_any(["apology", "sorry", "I understand"], weight=0.15),
            metadata_no_forbidden_terms(weight=0.20),
            min_length(80, weight=0.20),
        ],
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
        agents=[planner, domain_expert, responder],
    )

    return (
        OptimizationLoop(harness=harness),
        {
            "baseline_support_bot": baseline,
            "multi_agent_support_v1": multi_agent,
        },
        examples,
    )
