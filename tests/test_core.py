from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_ai_forge import Agent, Example, Harness, Message, MultiAgentModel
from domain_ai_forge import OptimizationLoop, ToolCall, ToolEnvironment
from domain_ai_forge import keyword_coverage, load_domain_pack, load_jsonl_cases
from domain_ai_forge import metadata_environment_state_matches
from domain_ai_forge import metadata_keyword_coverage, metadata_requires_agents
from domain_ai_forge import metadata_requires_tool_call, no_forbidden_terms
from domain_ai_forge.adapters import RuleBasedModel


class CoreTest(unittest.TestCase):
    def test_rule_based_model_matches_keyword(self) -> None:
        model = RuleBasedModel({"refund": "refund eligibility next step"})

        generation = model.respond([Message(role="user", content="Need a refund")])

        self.assertEqual(generation.text, "refund eligibility next step")
        self.assertEqual(generation.metadata["matched_route"], "refund")

    def test_harness_scores_generation(self) -> None:
        model = RuleBasedModel({"refund": "refund eligibility next step"})
        harness = Harness(
            scorers=[
                keyword_coverage(["refund", "eligibility"]),
                no_forbidden_terms(["guaranteed refund"]),
            ]
        )

        report = harness.run(
            model,
            [Example(id="case-1", input="Need a refund", expected="refund eligibility")],
        )

        self.assertEqual(report.summary()["case_count"], 1)
        self.assertEqual(report.overall_score, 1.0)
        self.assertEqual(report.pass_rate, 1.0)

    def test_metadata_keyword_coverage_uses_case_metadata(self) -> None:
        model = RuleBasedModel({"refund": "refund eligibility policy next step"})
        harness = Harness(scorers=[metadata_keyword_coverage()])

        report = harness.run(
            model,
            [
                Example(
                    id="case-1",
                    input="Need a refund",
                    metadata={"keywords": ["refund", "eligibility", "policy", "next step"]},
                )
            ],
        )

        self.assertEqual(report.overall_score, 1.0)

    def test_load_jsonl_cases(self) -> None:
        path = ROOT / "examples" / "customer_support" / "cases.jsonl"

        examples = load_jsonl_cases(path)

        self.assertEqual(len(examples), 2)
        self.assertEqual(examples[0].id, "refund-001")
        self.assertIn("keywords", examples[0].metadata)

    def test_load_domain_pack_manifest(self) -> None:
        path = ROOT / "examples" / "customer_support"

        domain_pack = load_domain_pack(path)

        self.assertEqual(domain_pack.name, "customer_support")
        self.assertEqual(domain_pack.task_type, "support_response")
        self.assertEqual(len(domain_pack.examples), 2)
        self.assertIn("refund", domain_pack.tags)

    def test_multi_agent_model_exposes_trace(self) -> None:
        planner = Agent(
            name="planner",
            role="Plan",
            model=RuleBasedModel({"refund": "plan refund eligibility"}),
        )
        responder = Agent(
            name="responder",
            role="Respond",
            model=RuleBasedModel({"refund": "final refund eligibility next step"}),
        )
        model = MultiAgentModel(name="agent_team", agents=[planner, responder])

        generation = model.respond([Message(role="user", content="refund request")])

        self.assertEqual(generation.text, "final refund eligibility next step")
        self.assertEqual(len(generation.trace), 2)
        self.assertEqual(generation.metadata["agent_count"], 2)

    def test_tool_environment_and_trajectory_scorers(self) -> None:
        def check_policy(args: dict[str, object], state: dict[str, object]) -> dict[str, object]:
            return {
                "output": "policy checked",
                "state_delta": {"policy_checked": True},
            }

        environment = ToolEnvironment(
            name="policy_sim",
            tools={"check_policy": check_policy},
            cost_usd_per_call=0.01,
        )
        tool_user = Agent(
            name="tool_user",
            role="Use tools",
            model=RuleBasedModel({"policy checked": "final answer with policy checked"}),
            tool_selector=lambda task, state, env_state: [ToolCall("check_policy")],
        )
        model = MultiAgentModel(name="tool_agent", agents=[tool_user])
        example = Example(
            id="case-1",
            input="Check the policy",
            metadata={
                "required_agents": ["tool_user"],
                "required_tools": ["check_policy"],
                "expected_state": {"policy_checked": True},
            },
        )
        harness = Harness(
            scorers=[
                metadata_requires_agents(),
                metadata_requires_tool_call(),
                metadata_environment_state_matches(),
            ],
            environment_factory=lambda case: environment,
        )

        report = harness.run(model, [example])

        self.assertEqual(report.overall_score, 1.0)
        self.assertEqual(report.total_cost_usd, 0.01)
        self.assertTrue(report.results[0].generation.metadata["environment_state"]["policy_checked"])
        self.assertEqual(report.results[0].generation.trace[0]["tool_calls"][0]["name"], "check_policy")

    def test_harness_repetitions_aggregate_scores_and_samples(self) -> None:
        model = RuleBasedModel({"refund": "refund eligibility"})
        harness = Harness(
            scorers=[keyword_coverage(["refund", "eligibility"])],
            repetitions=3,
        )

        report = harness.run(model, [Example(id="case-1", input="refund")])

        self.assertEqual(report.sample_count, 3)
        self.assertEqual(report.overall_score, 1.0)

    def test_optimization_loop_ranks_candidates(self) -> None:
        harness = Harness(scorers=[keyword_coverage(["refund", "eligibility"])])
        loop = OptimizationLoop(harness)
        candidates = {
            "weak": RuleBasedModel({"refund": "refund"}),
            "strong": RuleBasedModel({"refund": "refund eligibility"}),
        }

        comparison = loop.compare(
            candidates,
            [Example(id="case-1", input="refund please")],
        )

        self.assertEqual(comparison.best_candidate, "strong")
        self.assertGreater(
            comparison.reports["strong"].overall_score,
            comparison.reports["weak"].overall_score,
        )


if __name__ == "__main__":
    unittest.main()
