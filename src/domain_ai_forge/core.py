"""Core primitives for building measurable domain AI systems."""

from __future__ import annotations

from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Callable, Mapping, Protocol, Sequence


@dataclass(frozen=True)
class Message:
    """A chat-style message passed to a model."""

    role: str
    content: str


@dataclass(frozen=True)
class Generation:
    """Model output plus optional execution trace."""

    text: str
    trace: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Example:
    """A domain evaluation case."""

    id: str
    input: str
    expected: str = ""
    tags: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


class DomainModel(Protocol):
    """Anything that can answer a domain task."""

    name: str

    def respond(self, messages: Sequence[Message], **kwargs: Any) -> Generation | str:
        """Return a generation for the supplied messages."""


@dataclass(frozen=True)
class AgentStep:
    """One step in a multi-agent run."""

    agent: str
    role: str
    input: str
    output: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass
class Agent:
    """A role-bound model call inside a multi-agent system."""

    name: str
    role: str
    model: DomainModel
    instructions: str = ""
    output_key: str | None = None

    def run(self, task: str, state: Mapping[str, str]) -> AgentStep:
        prompt = self._build_prompt(task, state)
        system = self.instructions or self.role
        raw = self.model.respond(
            [
                Message(role="system", content=system),
                Message(role="user", content=prompt),
            ]
        )
        generation = coerce_generation(raw)
        return AgentStep(
            agent=self.name,
            role=self.role,
            input=prompt,
            output=generation.text,
            metadata={"model": self.model.name, **dict(generation.metadata)},
        )

    def _build_prompt(self, task: str, state: Mapping[str, str]) -> str:
        if not state:
            return f"Task:\n{task}\n\nReturn your contribution for this domain workflow."

        state_block = "\n".join(f"- {key}: {value}" for key, value in state.items())
        return (
            f"Task:\n{task}\n\n"
            f"Previous agent state:\n{state_block}\n\n"
            "Return your contribution for this domain workflow."
        )


Reducer = Callable[[str, Mapping[str, str], Sequence[AgentStep]], str]


@dataclass
class MultiAgentModel:
    """A model composed from ordered agents."""

    name: str
    agents: Sequence[Agent]
    reducer: Reducer | None = None

    def respond(self, messages: Sequence[Message], **kwargs: Any) -> Generation:
        task = latest_user_message(messages)
        state: dict[str, str] = {}
        steps: list[AgentStep] = []

        for agent in self.agents:
            step = agent.run(task, state)
            key = agent.output_key or agent.name
            state[key] = step.output
            steps.append(step)

        if self.reducer:
            text = self.reducer(task, state, steps)
        elif steps:
            text = steps[-1].output
        else:
            text = ""

        return Generation(
            text=text,
            trace=tuple(step.__dict__ for step in steps),
            metadata={"model": self.name, "agent_count": len(steps)},
        )


@dataclass(frozen=True)
class Score:
    """A normalized score from 0.0 to 1.0."""

    name: str
    value: float
    rationale: str = ""
    weight: float = 1.0

    @property
    def normalized(self) -> float:
        return max(0.0, min(1.0, self.value))


Scorer = Callable[[Example, Generation], Score]


@dataclass(frozen=True)
class CaseResult:
    """The result of running one example through a harness."""

    example: Example
    generation: Generation
    scores: tuple[Score, ...]

    @property
    def weighted_score(self) -> float:
        if not self.scores:
            return 0.0

        total_weight = sum(score.weight for score in self.scores)
        if total_weight <= 0:
            return mean(score.normalized for score in self.scores)

        return sum(score.normalized * score.weight for score in self.scores) / total_weight

    @property
    def passed(self) -> bool:
        threshold = float(self.example.metadata.get("pass_threshold", 0.75))
        return self.weighted_score >= threshold


@dataclass(frozen=True)
class RunReport:
    """A full harness run report."""

    model_name: str
    results: tuple[CaseResult, ...]

    @property
    def overall_score(self) -> float:
        if not self.results:
            return 0.0
        return mean(result.weighted_score for result in self.results)

    @property
    def pass_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for result in self.results if result.passed) / len(self.results)

    def summary(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "case_count": len(self.results),
            "overall_score": round(self.overall_score, 4),
            "pass_rate": round(self.pass_rate, 4),
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Harness Report: {self.model_name}",
            "",
            f"- overall_score: {self.overall_score:.3f}",
            f"- pass_rate: {self.pass_rate:.3f}",
            f"- cases: {len(self.results)}",
            "",
            "| case | score | passed | output |",
            "| --- | ---: | :---: | --- |",
        ]
        for result in self.results:
            output = result.generation.text.replace("\n", " ").strip()
            lines.append(
                f"| {result.example.id} | {result.weighted_score:.3f} | "
                f"{'yes' if result.passed else 'no'} | {output} |"
            )
        return "\n".join(lines)


class Harness:
    """Domain evaluation harness."""

    def __init__(self, scorers: Sequence[Scorer], name: str = "domain_harness") -> None:
        self.name = name
        self.scorers = tuple(scorers)

    def run(
        self,
        model: DomainModel,
        examples: Sequence[Example],
        tags: Sequence[str] | None = None,
    ) -> RunReport:
        selected = self._filter_examples(examples, tags)
        results: list[CaseResult] = []

        for example in selected:
            raw = model.respond([Message(role="user", content=example.input)])
            generation = coerce_generation(raw)
            scores = tuple(scorer(example, generation) for scorer in self.scorers)
            results.append(CaseResult(example=example, generation=generation, scores=scores))

        return RunReport(model_name=model.name, results=tuple(results))

    def _filter_examples(
        self,
        examples: Sequence[Example],
        tags: Sequence[str] | None,
    ) -> list[Example]:
        if not tags:
            return list(examples)

        tag_set = set(tags)
        return [example for example in examples if tag_set.intersection(example.tags)]


@dataclass(frozen=True)
class CandidateComparison:
    """Ranking of candidate models against the same harness."""

    reports: Mapping[str, RunReport]

    @property
    def best_candidate(self) -> str:
        if not self.reports:
            return ""
        return max(self.reports, key=lambda name: self.reports[name].overall_score)

    def leaderboard(self) -> list[tuple[str, float, float]]:
        rows = [
            (name, report.overall_score, report.pass_rate)
            for name, report in self.reports.items()
        ]
        return sorted(rows, key=lambda row: row[1], reverse=True)


class OptimizationLoop:
    """Compare candidate systems with one harness."""

    def __init__(self, harness: Harness) -> None:
        self.harness = harness

    def compare(
        self,
        candidates: Mapping[str, DomainModel],
        examples: Sequence[Example],
    ) -> CandidateComparison:
        reports = {
            name: self.harness.run(candidate, examples)
            for name, candidate in candidates.items()
        }
        return CandidateComparison(reports=reports)


def latest_user_message(messages: Sequence[Message]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return messages[-1].content if messages else ""


def coerce_generation(output: Generation | str) -> Generation:
    if isinstance(output, Generation):
        return output
    return Generation(text=str(output))


def keyword_coverage(keywords: Sequence[str], weight: float = 1.0) -> Scorer:
    """Score how many required keywords appear in the output."""

    normalized_keywords = tuple(keyword.lower() for keyword in keywords)

    def score(example: Example, generation: Generation) -> Score:
        text = generation.text.lower()
        if not normalized_keywords:
            return Score(name="keyword_coverage", value=1.0, rationale="no keywords", weight=weight)

        hits = [keyword for keyword in normalized_keywords if keyword in text]
        value = len(hits) / len(normalized_keywords)
        rationale = f"matched {len(hits)}/{len(normalized_keywords)} keywords"
        return Score(name="keyword_coverage", value=value, rationale=rationale, weight=weight)

    return score


def metadata_keyword_coverage(
    metadata_key: str = "keywords",
    weight: float = 1.0,
) -> Scorer:
    """Score case-specific keywords stored in example metadata."""

    def score(example: Example, generation: Generation) -> Score:
        raw_keywords = example.metadata.get(metadata_key, ())
        if isinstance(raw_keywords, str):
            keywords = (raw_keywords,)
        else:
            keywords = tuple(str(keyword) for keyword in raw_keywords)

        if not keywords:
            return Score(
                name="metadata_keyword_coverage",
                value=1.0,
                rationale=f"no metadata.{metadata_key} keywords",
                weight=weight,
            )

        text = generation.text.lower()
        normalized_keywords = tuple(keyword.lower() for keyword in keywords)
        hits = [keyword for keyword in normalized_keywords if keyword in text]
        value = len(hits) / len(normalized_keywords)
        return Score(
            name="metadata_keyword_coverage",
            value=value,
            rationale=f"matched {len(hits)}/{len(normalized_keywords)} metadata keywords",
            weight=weight,
        )

    return score


def contains_any(terms: Sequence[str], weight: float = 1.0) -> Scorer:
    """Score 1.0 when any accepted term appears in the output."""

    normalized_terms = tuple(term.lower() for term in terms)

    def score(example: Example, generation: Generation) -> Score:
        text = generation.text.lower()
        matched = [term for term in normalized_terms if term in text]
        return Score(
            name="contains_any",
            value=1.0 if matched else 0.0,
            rationale=f"matched: {', '.join(matched) if matched else 'none'}",
            weight=weight,
        )

    return score


def no_forbidden_terms(terms: Sequence[str], weight: float = 1.0) -> Scorer:
    """Score 0.0 if forbidden terms appear in the output."""

    normalized_terms = tuple(term.lower() for term in terms)

    def score(example: Example, generation: Generation) -> Score:
        text = generation.text.lower()
        found = [term for term in normalized_terms if term in text]
        return Score(
            name="no_forbidden_terms",
            value=0.0 if found else 1.0,
            rationale=f"forbidden terms: {', '.join(found) if found else 'none'}",
            weight=weight,
        )

    return score


def metadata_no_forbidden_terms(
    metadata_key: str = "forbidden_terms",
    weight: float = 1.0,
) -> Scorer:
    """Score case-specific forbidden terms stored in example metadata."""

    def score(example: Example, generation: Generation) -> Score:
        raw_terms = example.metadata.get(metadata_key, ())
        if isinstance(raw_terms, str):
            terms = (raw_terms,)
        else:
            terms = tuple(str(term) for term in raw_terms)

        if not terms:
            return Score(
                name="metadata_no_forbidden_terms",
                value=1.0,
                rationale=f"no metadata.{metadata_key} terms",
                weight=weight,
            )

        text = generation.text.lower()
        normalized_terms = tuple(term.lower() for term in terms)
        found = [term for term in normalized_terms if term in text]
        return Score(
            name="metadata_no_forbidden_terms",
            value=0.0 if found else 1.0,
            rationale=f"forbidden terms: {', '.join(found) if found else 'none'}",
            weight=weight,
        )

    return score


def min_length(chars: int, weight: float = 1.0) -> Scorer:
    """Score whether the output is at least the requested length."""

    def score(example: Example, generation: Generation) -> Score:
        actual = len(generation.text.strip())
        value = 1.0 if actual >= chars else actual / chars
        return Score(
            name="min_length",
            value=value,
            rationale=f"{actual}/{chars} chars",
            weight=weight,
        )

    return score
