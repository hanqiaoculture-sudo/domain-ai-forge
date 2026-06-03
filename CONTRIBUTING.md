# Contributing

Domain AI Forge grows through real vertical AI practice. The most valuable contributions are domain packs, harness scorers, adapter integrations, and clear failure cases.

## Good First Contributions

- Add a scorer for a concrete domain risk.
- Add a small domain pack with 5 to 20 evaluation cases.
- Add an adapter for a model provider or local model runtime.
- Improve a demo so it teaches the framework faster.
- Add a regression case for a known agent failure.

## Contribution Standard

Every meaningful contribution should answer three questions:

- What domain behavior are we improving?
- Which harness case proves the improvement?
- What regression risk should future contributors avoid?

## Local Development

```bash
python -m unittest discover -s tests
python examples/customer_support/run_demo.py
```

## Pull Request Checklist

- [ ] The change is scoped to one clear behavior or concept.
- [ ] New or changed behavior has a test or example.
- [ ] The README or docs are updated when the public API changes.
- [ ] The project still works without model API keys.

