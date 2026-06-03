"""Core primitives for building measurable domain AI systems."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace
from statistics import mean
from typing import Any, Callable, Mapping, MutableMapping, Protocol, Sequence


@dataclass(frozen=True)
class Message:
    """A chat-style message passed to a model."""

    role: str
    content: str


@dataclass(frozen=True)
class ToolCall:
    """A tool action requested during an agent run."""

    name: str
    args: Mapping[str, Any] = field(default_factory=dict)
    agent: str = ""


@dataclass(frozen=True)
class ToolResult:
    """The result of executing a tool call inside a domain environment."""

    call: ToolCall
    output: str
    state_delta: Mapping[str, Any] = field(default_factory=dict)
    state_after: Mapping[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    error: str = ""


@dataclass(frozen=True)
class Generation:
    """Model output plus optional execution trace."""

    text: str
    trace: tuple[Mapping[str, Any], ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    latency_ms: float = 0.0


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


ToolHandler = Callable[[Mapping[str, Any], MutableMapping[str, Any]], ToolResult | str | Mapping[str, Any]]
ToolSelector = Callable[[str, Mapping[str, str], Mapping[str, Any]], Sequence[ToolCall]]


@dataclass
class ToolEnvironment:
    """A deterministic tool and state simulator for domain evaluation."""

    name: str
    tools: Mapping[str, ToolHandler]
    initial_state: Mapping[str, Any] = field(default_factory=dict)
    cost_usd_per_call: float = 0.0
    state: dict[str, Any] = field(init=False)

    def __post_init__(self) -> None:
        self.state = dict(self.initial_state)

    def snapshot(self) -> dict[str, Any]:
        return dict(self.state)

    def run(self, call: ToolCall) -> ToolResult:
        handler = self.tools.get(call.name)
        if handler is None:
            return ToolResult(
                call=call,
                output="",
                state_after=self.snapshot(),
                error=f"unknown tool: {call.name}",
            )

        start = time.perf_counter()
        raw = handler(call.args, self.state)
        elapsed_ms = (time.perf_counter() - start) * 1000

        if isinstance(raw, ToolResult):
            self.state.update(raw.state_delta)
            return ToolResult(
                call=call,
                output=raw.output,
                state_delta=dict(raw.state_delta),
                state_after=self.snapshot(),
                cost_usd=raw.cost_usd,
                latency_ms=raw.latency_ms or elapsed_ms,
                error=raw.error,
            )

        if isinstance(raw, Mapping):
            output = str(raw.get("output", ""))
            state_delta = raw.get("state_delta", {})
            if not isinstance(state_delta, Mapping):
                raise ValueError("tool state_delta must be a mapping")

            self.state.update(state_delta)
            return ToolResult(
                call=call,
                output=output,
                state_delta=dict(state_delta),
                state_after=self.snapshot(),
                cost_usd=float(raw.get("cost_usd", self.cost_usd_per_call)),
                latency_ms=float(raw.get("latency_ms", elapsed_ms)),
                error=str(raw.get("error", "")),
            )

        return ToolResult(
            call=call,
            output=str(raw),
            state_after=self.snapshot(),
            cost_usd=self.cost_usd_per_call,
            latency_ms=elapsed_ms,
        )


@dataclass(frozen=True)
class AgentStep:
    """One step in a multi-agent run."""

    agent: str
    role: str
    input: str
    output: str
    tool_calls: tuple[ToolCall, ...] = ()
    tool_results: tuple[ToolResult, ...] = ()
    cost_usd: float = 0.0
    latency_ms: float = 0.0
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def to_trace(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "role": self.role,
            "input": self.input,
            "output": self.output,
            "tool_calls": [
                {"name": call.name, "args": dict(call.args), "agent": call.agent}
                for call in self.tool_calls
            ],
            "tool_results": [
                {
                    "tool": result.call.name,
                    "output": result.output,
                    "state_delta": dict(result.state_delta),
                    "state_after": dict(result.state_after),
                    "cost_usd": result.cost_usd,
                    "latency_ms": result.latency_ms,
                    "error": result.error,
                }
                for result in self.tool_results
            ],
            "cost_usd": self.cost_usd,
            "latency_ms": self.latency_ms,
            "metadata": dict(self.metadata),
        }


@dataclass
class Agent:
    """A role-bound model call inside a multi-agent system."""

    name: str
    role: str
    model: DomainModel
    instructions: str = ""
    output_key: str | None = None
    tool_selector: ToolSelector | None = None

    def run(
        self,
        task: str,
        state: Mapping[str, str],
        environment: ToolEnvironment | None = None,
    ) -> AgentStep:
        start = time.perf_counter()
        tool_results = self._run_tools(task, state, environment)
        tool_state = {
            f"tool.{result.call.name}": result.output
            for result in tool_results
            if not result.error
        }
        prompt = self._build_prompt(task, {**state, **tool_state})
        system = self.instructions or self.role
        raw = self.model.respond(
            [
                Message(role="system", content=system),
                Message(role="user", content=prompt),
            ]
        )
        generation = coerce_generation(raw)
        measured_latency_ms = (time.perf_counter() - start) * 1000
        cost_usd = generation.cost_usd + sum(result.cost_usd for result in tool_results)
        latency_ms = max(
            measured_latency_ms,
            generation.latency_ms + sum(result.latency_ms for result in tool_results),
        )
        return AgentStep(
            agent=self.name,
            role=self.role,
            input=prompt,
            output=generation.text,
            tool_calls=tuple(result.call for result in tool_results),
            tool_results=tuple(tool_results),
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            metadata={"model": self.model.name, **dict(generation.metadata)},
        )

    def _run_tools(
        self,
        task: str,
        state: Mapping[str, str],
        environment: ToolEnvironment | None,
    ) -> list[ToolResult]:
        if environment is None or self.tool_selector is None:
            return []

        calls = self.tool_selector(task, state, environment.snapshot())
        results: list[ToolResult] = []
        for call in calls:
            agent_call = call if call.agent else replace(call, agent=self.name)
            results.append(environment.run(agent_call))
        return results

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
        start = time.perf_counter()
        task = latest_user_message(messages)
        environment = kwargs.get("environment")
        if environment is not None and not isinstance(environment, ToolEnvironment):
            raise TypeError("environment must be a ToolEnvironment")

        state: dict[str, str] = {}
        steps: list[AgentStep] = []

        for agent in self.agents:
            step = agent.run(task, state, environment=environment)
            key = agent.output_key or agent.name
            state[key] = step.output
            steps.append(step)

        if self.reducer:
            text = self.reducer(task, state, steps)
        elif steps:
            text = steps[-1].output
        else:
            text = ""

        metadata: dict[str, Any] = {"model": self.name, "agent_count": len(steps)}
        if environment is not None:
            metadata["environment_name"] = environment.name
            metadata["environment_state"] = environment.snapshot()

        measured_latency_ms = (time.perf_counter() - start) * 1000
        cost_usd = sum(step.cost_usd for step in steps)
        latency_ms = max(measured_latency_ms, sum(step.latency_ms for step in steps))

        return Generation(
            text=text,
            trace=tuple(step.to_trace() for step in steps),
            metadata=metadata,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
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
    samples: tuple[Generation, ...] = ()

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

    @property
    def sample_count(self) -> int:
        return len(self.samples) if self.samples else 1

    @property
    def cost_usd(self) -> float:
        if self.samples:
            return sum(sample.cost_usd for sample in self.samples)
        return self.generation.cost_usd

    @property
    def latency_ms(self) -> float:
        samples = self.samples or (self.generation,)
        return mean(sample.latency_ms for sample in samples)


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

    @property
    def failure_count(self) -> int:
        return sum(1 for result in self.results if not result.passed)

    @property
    def sample_count(self) -> int:
        return sum(result.sample_count for result in self.results)

    @property
    def total_cost_usd(self) -> float:
        return sum(result.cost_usd for result in self.results)

    @property
    def average_latency_ms(self) -> float:
        if not self.results:
            return 0.0
        return mean(result.latency_ms for result in self.results)

    def summary(self) -> dict[str, Any]:
        return {
            "model_name": self.model_name,
            "case_count": len(self.results),
            "sample_count": self.sample_count,
            "overall_score": round(self.overall_score, 4),
            "pass_rate": round(self.pass_rate, 4),
            "failure_count": self.failure_count,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "average_latency_ms": round(self.average_latency_ms, 3),
        }

    def to_markdown(self) -> str:
        lines = [
            f"# Harness Report: {self.model_name}",
            "",
            f"- overall_score: {self.overall_score:.3f}",
            f"- pass_rate: {self.pass_rate:.3f}",
            f"- total_cost_usd: {self.total_cost_usd:.6f}",
            f"- average_latency_ms: {self.average_latency_ms:.3f}",
            f"- cases: {len(self.results)}",
            f"- samples: {self.sample_count}",
            "",
            "| case | score | passed | cost_usd | latency_ms | output |",
            "| --- | ---: | :---: | ---: | ---: | --- |",
        ]
        for result in self.results:
            output = result.generation.text.replace("\n", " ").strip()
            lines.append(
                f"| {result.example.id} | {result.weighted_score:.3f} | "
                f"{'yes' if result.passed else 'no'} | "
                f"{result.cost_usd:.6f} | {result.latency_ms:.3f} | {output} |"
            )
        return "\n".join(lines)


EnvironmentFactory = Callable[[Example], ToolEnvironment]


class Harness:
    """Domain evaluation harness."""

    def __init__(
        self,
        scorers: Sequence[Scorer],
        name: str = "domain_harness",
        environment_factory: EnvironmentFactory | None = None,
        repetitions: int = 1,
    ) -> None:
        self.name = name
        self.scorers = tuple(scorers)
        self.environment_factory = environment_factory
        self.repetitions = max(1, repetitions)

    def run(
        self,
        model: DomainModel,
        examples: Sequence[Example],
        tags: Sequence[str] | None = None,
        environment_factory: EnvironmentFactory | None = None,
        repetitions: int | None = None,
    ) -> RunReport:
        selected = self._filter_examples(examples, tags)
        results: list[CaseResult] = []
        factory = environment_factory or self.environment_factory
        repeat_count = max(1, repetitions or self.repetitions)

        for example in selected:
            samples: list[Generation] = []
            score_sets: list[tuple[Score, ...]] = []
            for _ in range(repeat_count):
                environment = factory(example) if factory else None
                raw = model.respond(
                    [Message(role="user", content=example.input)],
                    example=example,
                    environment=environment,
                )
                generation = coerce_generation(raw)
                generation = attach_environment_metadata(generation, environment)
                scores = tuple(scorer(example, generation) for scorer in self.scorers)
                samples.append(generation)
                score_sets.append(scores)

            representative = samples[0] if samples else Generation(text="")
            results.append(
                CaseResult(
                    example=example,
                    generation=representative,
                    scores=aggregate_score_sets(score_sets),
                    samples=tuple(samples),
                )
            )

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


def attach_environment_metadata(
    generation: Generation,
    environment: ToolEnvironment | None,
) -> Generation:
    if environment is None:
        return generation

    metadata = dict(generation.metadata)
    metadata.setdefault("environment_name", environment.name)
    metadata["environment_state"] = environment.snapshot()
    return replace(generation, metadata=metadata)


def aggregate_score_sets(score_sets: Sequence[Sequence[Score]]) -> tuple[Score, ...]:
    if not score_sets:
        return ()
    if len(score_sets) == 1:
        return tuple(score_sets[0])

    max_len = max(len(scores) for scores in score_sets)
    aggregated: list[Score] = []
    for index in range(max_len):
        indexed_scores = [scores[index] for scores in score_sets if index < len(scores)]
        if not indexed_scores:
            continue

        first = indexed_scores[0]
        aggregated.append(
            Score(
                name=first.name,
                value=mean(score.normalized for score in indexed_scores),
                rationale=f"mean over {len(indexed_scores)} runs",
                weight=first.weight,
            )
        )

    return tuple(aggregated)


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


def metadata_requires_agents(
    metadata_key: str = "required_agents",
    weight: float = 1.0,
) -> Scorer:
    """Score whether required agents appear in the execution trace."""

    def score(example: Example, generation: Generation) -> Score:
        required_agents = _metadata_sequence(example, metadata_key)
        if not required_agents:
            return Score(
                name="metadata_requires_agents",
                value=1.0,
                rationale=f"no metadata.{metadata_key} agents",
                weight=weight,
            )

        observed = {
            str(step.get("agent", ""))
            for step in generation.trace
            if isinstance(step, Mapping)
        }
        hits = [agent for agent in required_agents if agent in observed]
        return Score(
            name="metadata_requires_agents",
            value=len(hits) / len(required_agents),
            rationale=f"matched {len(hits)}/{len(required_agents)} agents",
            weight=weight,
        )

    return score


def metadata_requires_tool_call(
    metadata_key: str = "required_tools",
    weight: float = 1.0,
) -> Scorer:
    """Score whether required tools appear in the execution trace."""

    def score(example: Example, generation: Generation) -> Score:
        required_tools = _metadata_sequence(example, metadata_key)
        if not required_tools:
            return Score(
                name="metadata_requires_tool_call",
                value=1.0,
                rationale=f"no metadata.{metadata_key} tools",
                weight=weight,
            )

        observed = set(_trace_tool_names(generation))
        hits = [tool for tool in required_tools if tool in observed]
        return Score(
            name="metadata_requires_tool_call",
            value=len(hits) / len(required_tools),
            rationale=f"matched {len(hits)}/{len(required_tools)} tools",
            weight=weight,
        )

    return score


def metadata_environment_state_matches(
    metadata_key: str = "expected_state",
    weight: float = 1.0,
) -> Scorer:
    """Score whether the final environment state matches case expectations."""

    def score(example: Example, generation: Generation) -> Score:
        expected = example.metadata.get(metadata_key, {})
        if not isinstance(expected, Mapping) or not expected:
            return Score(
                name="metadata_environment_state_matches",
                value=1.0,
                rationale=f"no metadata.{metadata_key} state",
                weight=weight,
            )

        actual = generation.metadata.get("environment_state", {})
        if not isinstance(actual, Mapping):
            actual = {}

        hits = [
            key
            for key, expected_value in expected.items()
            if actual.get(key) == expected_value
        ]
        return Score(
            name="metadata_environment_state_matches",
            value=len(hits) / len(expected),
            rationale=f"matched {len(hits)}/{len(expected)} state keys",
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


def _metadata_sequence(example: Example, key: str) -> tuple[str, ...]:
    raw_value = example.metadata.get(key, ())
    if isinstance(raw_value, str):
        return (raw_value,)
    if isinstance(raw_value, Sequence):
        return tuple(str(value) for value in raw_value)
    return (str(raw_value),) if raw_value else ()


def _trace_tool_names(generation: Generation) -> tuple[str, ...]:
    names: list[str] = []
    for step in generation.trace:
        tool_calls = step.get("tool_calls", ()) if isinstance(step, Mapping) else ()
        if not isinstance(tool_calls, Sequence):
            continue
        for call in tool_calls:
            if isinstance(call, Mapping):
                name = call.get("name")
                if name:
                    names.append(str(name))
    return tuple(names)
