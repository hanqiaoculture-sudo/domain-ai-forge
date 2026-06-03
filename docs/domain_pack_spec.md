# Domain Pack Spec

Domain packs are the planned contribution unit for Domain AI Forge.

## Goal

A domain pack should package the minimum useful evaluation context for one vertical AI workflow.

## Structure

```text
domain_packs/
  customer_support/
    pack.json
    cases.jsonl
    scorers.py
    README.md
```

## Pack Manifest

```json
{
  "name": "customer_support",
  "version": "0.1.0",
  "task_type": "support_response",
  "description": "A small harness-first domain pack for customer support response workflows.",
  "cases": "cases.jsonl",
  "tools": ["lookup_order", "open_refund_review"],
  "scorers": ["metadata_keyword_coverage", "metadata_requires_tool_call"]
}
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
    "forbidden_terms": ["guaranteed refund"],
    "required_agents": ["planner", "domain_expert", "tool_user", "responder"],
    "required_tools": ["lookup_order", "open_refund_review"],
    "expected_state": {
      "order_checked": true,
      "refund_review_opened": true
    }
  }
}
```

The current Python core includes `load_domain_pack()` for `pack.json` and `load_jsonl_cases()` for this JSONL case format.

## Review Rules

- Cases should be realistic but must not include private user data.
- Expected behavior should be specific enough to score.
- Risk checks should be explicit.
- Required tools and expected state should describe observable behavior.
- Domain packs should stay small enough for contributors to understand.
