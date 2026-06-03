"""Domain pack helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from domain_ai_forge.core import Example


@dataclass(frozen=True)
class DomainPack:
    """A portable bundle of domain evaluation cases."""

    name: str
    version: str
    task_type: str
    examples: tuple[Example, ...]
    metadata: Mapping[str, Any]

    @property
    def tags(self) -> tuple[str, ...]:
        tag_set = {tag for example in self.examples for tag in example.tags}
        return tuple(sorted(tag_set))

    def select(self, tags: Sequence[str] | None = None) -> tuple[Example, ...]:
        if not tags:
            return self.examples

        tag_set = set(tags)
        return tuple(
            example for example in self.examples if tag_set.intersection(example.tags)
        )


def load_jsonl_cases(path: str | Path) -> tuple[Example, ...]:
    """Load evaluation cases from a JSONL file."""

    case_path = Path(path)
    examples: list[Example] = []
    with case_path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            stripped = line.strip()
            if not stripped:
                continue

            try:
                payload = json.loads(stripped)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON on line {line_number}: {exc}") from exc

            examples.append(_example_from_mapping(payload, line_number))

    return tuple(examples)


def _example_from_mapping(payload: Mapping[str, Any], line_number: int) -> Example:
    missing = [key for key in ("id", "input") if key not in payload]
    if missing:
        raise ValueError(f"Missing {', '.join(missing)} on line {line_number}")

    tags = payload.get("tags", ())
    if isinstance(tags, str):
        normalized_tags = (tags,)
    else:
        normalized_tags = tuple(str(tag) for tag in _as_iterable(tags))

    metadata = payload.get("metadata", {})
    if not isinstance(metadata, Mapping):
        raise ValueError(f"metadata must be an object on line {line_number}")

    return Example(
        id=str(payload["id"]),
        input=str(payload["input"]),
        expected=str(payload.get("expected", "")),
        tags=normalized_tags,
        metadata=dict(metadata),
    )


def _as_iterable(value: Any) -> Iterable[Any]:
    if value is None:
        return ()
    if isinstance(value, Iterable) and not isinstance(value, (str, bytes)):
        return value
    return (value,)

