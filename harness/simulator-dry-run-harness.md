---
title: Simulator Dry Run Harness
type: boi/harness
status: reviewed
---

# Simulator Dry Run Harness

Use this harness when validating Langflow Universal Simulator behavior.

## Role

The simulator is for execution preview, PoC, and local demo where external systems are unavailable. It is not the default evidence source for verified Inbox reports.

## Rules

- Label simulator output as `시뮬레이션 결과`.
- Do not mix simulator output with actual Event/Action/Data Lake evidence in a decision report.
- A simulator failure can fail a dry-run/PoC check, but it must not block `/inbox` from rendering or an already materialized verified report from loading.

## Checks

```bash
python scripts/check_langflow_universal_simulator.py --langflow-url http://localhost:7860 --boi-api-url http://localhost:28000
pytest tests/test_action_gateway.py -q -s -k "universal_simulator"
```

