# Domain Pack Spec

Domain packs are the planned contribution unit for Domain AI Forge.

## Goal

A domain pack should package the minimum useful evaluation context for one vertical AI workflow.

## Proposed Structure

```text
domain_packs/
  customer_support/
    pack.yaml
    cases.jsonl
    scorers.py
    README.md
```

## Pack Metadata

```yaml
name: customer_support
version: 0.1.0
task_type: support_response
owner: community
risk_level: medium
```

## Case Format

```json
{
  "id": "refund-001",
  "input": "A customer asks whether they can get a refund after buying yesterday.",
  "expected": "refund eligibility next steps",
  "tags": ["refund", "policy"],
  "metadata": {
    "pass_threshold": 0.75,
    "keywords": ["refund", "eligibility", "next step"],
    "forbidden_terms": ["guaranteed refund"]
  }
}
```

The current Python core includes `load_jsonl_cases()` for this JSONL case format. Full `pack.yaml` loading is planned for a later release.

## Review Rules

- Cases should be realistic but must not include private user data.
- Expected behavior should be specific enough to score.
- Risk checks should be explicit.
- Domain packs should stay small enough for contributors to understand.
