"""Run a model + harness + multi-agent comparison for customer support."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from domain_ai_forge.demo import build_customer_support_demo  # noqa: E402


def main() -> int:
    loop, candidates, examples = build_customer_support_demo()
    comparison = loop.compare(candidates, examples)
    best = comparison.best_candidate
    best_report = comparison.reports[best]

    print("Domain AI Forge demo")
    print(f"overall_score: {best_report.overall_score:.2f}")
    print(f"pass_rate: {best_report.pass_rate:.2f}")
    print(f"best_candidate: {best}")
    print("")
    print("leaderboard:")
    for name, score, pass_rate in comparison.leaderboard():
        print(f"- {name}: score={score:.2f}, pass_rate={pass_rate:.2f}")
    print("")
    print(best_report.to_markdown())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

