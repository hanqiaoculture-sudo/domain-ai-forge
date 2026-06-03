"""Deterministic model adapter for demos, tests, and harness baselines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping, Sequence

from domain_ai_forge.core import Generation, Message


@dataclass
class RuleBasedModel:
    """A tiny keyword router that behaves like a model adapter.

    This is intentionally simple: it lets new contributors run the framework
    without API keys while still exercising the same model interface.
    """

    routes: Mapping[str, str]
    fallback: str = "I need more domain context before answering."
    name: str = "rule_based_model"
    metadata: Mapping[str, str] = field(default_factory=dict)

    def respond(self, messages: Sequence[Message], **kwargs: object) -> Generation:
        prompt = "\n".join(message.content for message in messages).lower()
        for keyword, response in self.routes.items():
            if keyword.lower() in prompt:
                return Generation(
                    text=response,
                    metadata={"matched_route": keyword, **dict(self.metadata)},
                )

        return Generation(
            text=self.fallback,
            metadata={"matched_route": "", **dict(self.metadata)},
        )

