# Domain AI Forge Framework

This document describes the operating framework behind Domain AI Forge.

中文摘要：垂域 AI 的优化不应该只围绕模型参数或 prompt。更稳定的路径是把业务目标拆成可评测的 harness，把模型和多 agent workflow 都放进同一个回归系统里，然后持续比较候选方案。

## The Three-Layer Architecture

### 1. Model Layer

The model layer answers the task. It can be:

- A hosted LLM
- A local model
- A retrieval pipeline
- A rules baseline
- A multi-agent system

The important rule is that every model must expose the same interface, so the harness can compare candidates fairly.

### 2. Harness Layer

The harness is the domain memory. It captures:

- Real user tasks
- Expected behavior
- Risk checks
- Rubrics
- Golden examples
- Regression cases
- Pass thresholds

In a vertical AI product, the harness should become more valuable over time. Each failure should turn into a new case.

### 3. Multi-Agent Model Layer

Agents are useful when they represent real product responsibilities:

- Planner: decomposes the task
- Domain expert: applies policy and domain constraints
- Tool user: retrieves or acts
- Critic: checks risk and completeness
- Responder: produces the final answer

Agents should not be added because they sound impressive. They should be added when they make a measurable harness score better or reduce a known risk.

## Optimization Loop

```text
1. Collect domain cases
2. Define scoring and risk rubrics
3. Build a baseline model
4. Add candidate model or agent workflow
5. Run both through the same harness
6. Compare score, pass rate, and failure cases
7. Convert failures into new harness cases
```

## Maturity Model

| Level | Name | Description |
| --- | --- | --- |
| 0 | Demo | Prompt works on hand-picked examples |
| 1 | Harness | Domain cases and basic scorers exist |
| 2 | Regression | Every release runs the same harness |
| 3 | Agentic | Multi-agent workflows are measurable |
| 4 | Operational | Human review, tools, retrieval, and safety are integrated |
| 5 | Compounding | Failures continuously improve the harness and domain pack |

## Design Principles

- Measure before optimizing.
- Keep the core model-provider neutral.
- Prefer domain cases over generic benchmarks.
- Treat every failure as future infrastructure.
- Make demos runnable without API keys.
- Keep agents tied to product responsibilities.

