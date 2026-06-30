---
title: Inbox Review Report Harness
type: boi/harness
status: reviewed
---

# Inbox Review Report Harness

Use this harness when creating or validating BoI Inbox report behavior.

## Contract

- `/inbox` must render from a fast manifest. It must not wait for LLM narrative, Langflow, Data Lake, or report materialization.
- `GET /api/inbox` returns a slim report manifest, report state, and links. It may enqueue visible report candidates into a bounded background queue, but it must not synchronously build reports or block on warm-up work.
- `GET /api/inbox/reports/{report_id}` returns a verified report BoI when cached/materialized. If no report exists, it returns a clear not-ready/not-found state instead of generated filler prose.
- Visible report text must not contain `source_id`, raw trace/action ids, schema dumps, `WorkflowDefinition`, or repeated fallback phrases.
- Group cards are roll-ups. They show priority and processing order only; they do not expose group report BoI links or group report generation buttons. Approval decisions use individual task reports by default. High-risk group bulk approve is blocked.
- Verified reports must include decision readiness: whether the item is ready for individual approval/rejection review, needs more evidence, and which evidence should be checked first.

## Evidence Policy

Verified report evidence can come from actual Event Broker events, Action Gateway results, generated BoI documents, manual notes, Data Lake artifacts, and similar past cases.

Langflow Universal Simulator output is not verified report evidence. It can appear only as a labeled `시뮬레이션 결과` in dry-run/PoC views.

If Data Lake is enabled and relevant source data exists, the report can attach sample/profile/artifact links automatically. If no Data Lake evidence is available, do not fabricate it and continue with other source-bound evidence.

## Required Checks

```bash
python scripts/check_inbox_narrative_quality.py --base-url http://localhost:28000 --summary --require-ready-report
pytest tests/test_boi_api_routes.py -q -s -k "boi_inbox or agent_inbox"
pytest tests/test_boi_wiki_mcp.py -q -s -k "boi_inbox"
```
