from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from domain_ai_forge import Agent, Example, Harness, Message, MultiAgentModel
from domain_ai_forge import OptimizationLoop, keyword_coverage, load_jsonl_cases
from domain_ai_forge import metadata_keyword_coverage, no_forbidden_terms
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
