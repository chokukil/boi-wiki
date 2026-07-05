# Harness Responsibility Matrix

Use this matrix to keep BoI Wiki lightweight while still giving API, MCP, and Action authors a powerful execution surface.

| Responsibility | BoI contract | Primary surfaces | Verification |
|---|---|---|---|
| Observation | Gather user request, page context, runtime events, artifacts, and visible Inbox tasks without mixing raw logs into user-facing reports. | Web UI, BoI API, MCP `ontology_search`, `boi_inbox`, `work_context_get` | Inbox report tests, WorkContextPack tests, OKF lint |
| Context | Keep OKF Markdown/JSONL as core source of truth; use Data Lake artifacts and Legacy DB Demo only as optional evidence overlays. | OKF docs, Data Lake artifact APIs, private/team/public ACL | Data Lake disabled/enabled smoke, ACL tests |
| Control | Separate plan/preview/draft from apply/submit/execute; pin constraints in server code, not only in prompts. | API validators, MCP wrappers, Web forms, RBAC checks | mutation confirmation tests, RBAC audit tests |
| Action | Route real external work through Action Gateway allowlists and approval policy; distinguish `user_confirmed` from high-risk `approved_by`. | Action Gateway, Event Router, MCP `action_invoke`, Agent execution cards | Action catalog tests, high-risk approval tests |
| State | Append runtime changes and decisions to logs/artifacts instead of rewriting user history; keep raw IDs internal or diagnostic. | Action logs, Event Stream, artifact attachments, Inbox history | append-only tests, raw-ID visibility tests |
| Verification | Every public scenario has a narrow automated check plus a smoke command that can run without optional overlays. | pytest, scripts, compose profiles, local workspace check | final acceptance suite and compose config smoke |

## Guardrail Defaults

- Preview tools may show feasibility and blockers before confirmation.
- Submit, apply, publish, workflow start, real action invoke, and evidence adoption require `user_confirmed=true`.
- High-risk Action Gateway calls may additionally require `approved_by`; `user_confirmed` is not a substitute for approval.
- UI surfaces use opaque public references for Inbox tasks. Raw request/action/trace IDs stay in API responses, audit logs, and diagnostics only.
- Langflow is a connector/debug backend. Native BoI Agent plus BoI API/MCP remain the production contract.
