"""Command line interface for Domain AI Forge."""

from __future__ import annotations

import argparse
import sys

from domain_ai_forge.demo import build_customer_support_demo


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="domain-ai-forge")
    parser.add_argument(
        "command",
        nargs="?",
        default="demo",
        choices=("demo",),
        help="Command to run.",
    )
    args = parser.parse_args(argv)

    if args.command == "demo":
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
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())

