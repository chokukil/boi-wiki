# Work Learning System v7 Completion Audit

Last reviewed: 2026-07-11

## Scope

This audit maps the BoI Work Learning System to the loop primitives described in Anthropic's
[Getting started with loops](https://claude.com/blog/getting-started-with-loops), while preserving
the project's Context Engineering, Harness, Task mode, Evidence Ledger, and knowledge-promotion
contracts.

## Alignment Matrix

| Loop principle | BoI implementation | Status |
|---|---|---|
| Turn loop for short work | Pet turn creates a `WorkRun`; LLM structured planning selects the operation and capability. Ambiguous or unavailable planning fails closed to read-only search. | Implemented |
| Goal loop with verifiable exit | Task loop uses structured completion checks, Evidence Ledger, system bindings or human confirmation, plus iteration/no-progress/tool limits. | Implemented |
| Time loop | `WorkRoutine` supports schedule/interval trigger, due execution by the Agent worker, max-runs/cancel stop, adaptive cadence, and bounded retry after transient system-target failure. | Implemented and runtime-smoked |
| Proactive loop | Event-triggered `WorkRoutine` starts the same Agent/Context/Harness/WorkRun path and can stop when the event resolves. | Implemented and tested |
| Separate task and routine stop | `LoopPolicy.task_stop` and `LoopPolicy.routine_stop` are stored independently on every WorkRun. | Implemented |
| Avoid repeated unchanged work | Source fingerprint dedupe, result fingerprint comparison, no-progress stop, and up to 8x schedule backoff. | Implemented |
| Verification tools and Skills | Versioned Harness preflight/validate/test/post-verify, real domain preview/test adapters, and executable Skill fixtures required before activation. | Implemented |
| Fresh independent reviewer | Drafts and Deep Work are reviewed without authoring conversation context. Reviewer evidence refs are restricted to supplied evidence and cannot complete Autopilot work. | Implemented |
| Pilot before broad work | Deep Work defaults to pilot mode, one worker path, no subagents, four tool calls, bounded timeout and token budget. | Implemented |
| Usage visibility | Scoped model/embedding usage ledger for turns and Deep Work usage/tool/subagent counts with per-run references. Provider usage is used when available with an explicit estimate fallback. | Implemented |
| Failure becomes system improvement | Repeated Manual completion creates Skill/Action candidates; repeated blockers create SOP/Harness candidates; promotion remains reviewed. | Implemented |
| Intent-preserving artifacts | Explanatory Mermaid artifacts remain read-only. Only an explicit transform intent exposes typed actions; Task-only conversion creates a `workflow_draft` and never an SOP plan. | Implemented and live-smoked |

## Important Boundaries

- LLM structured planning owns semantic intent. `LoopPolicy`, Harness, ACL, confirmation, budgets,
  and stop conditions are deterministic safety contracts, not phrase-based routing.
- A qualitative evaluator can request revision but never supplies an Autopilot system binding and
  never overrides a deterministic validator or human decision.
- Time and proactive loops reuse the same `WorkRun`; they are not a second agent architecture.
- Long source payloads remain outside prompts. Context uses summaries, profiles, samples,
  checksums, and ACL-controlled references.
- Semantic intent and operation planning belong to the structured LLM planner. Deterministic code
  only enforces ACL, schemas, risk, evidence validity, retry, no-progress, and resource budgets.
- Hybrid search does not use Korean phrase lists to infer operation intent. It combines lexical and
  embedding recall with ontology, graph, authority, recency, and generic title/term/alias identity.
- Local, intranet, and external deployments use the configured LM Studio/OpenAI-compatible route.
  GPT-5.5 is disabled unless both explicit test-mode switches and a test credential are supplied.

## Operational Boundaries

1. Deep Work defaults to a 24K pilot budget and therefore has no subagent fan-out. The API and
   worker independently recompute the budget policy. One isolated subagent requires at least 48K;
   broader work must be explicitly requested.
2. DeepAgents can only search and read ACL-visible BoI evidence. Its result is always a draft and
   cannot mutate production, complete an Autopilot Task, or bypass confirmation.
3. Independent review is qualitative. A pass requires at least one exact ID from the supplied
   Evidence Ledger, but deterministic Harness, Task completion bindings, and human decisions remain
   authoritative.
4. A Business Event may optionally start an event-triggered proactive routine. The ordinary Event
   editor exposes this as an optional workflow connection; it is not required for simple events.
5. Failed scheduled system targets retry with bounded exponential delay and become failed after the
   configured attempt limit. They are never reported as completed merely because a schedule fired.

## Acceptance Evidence

- `tests/test_agent_v2.py` covers goal completion, no-progress stop, system-bound Autopilot,
  proactive event dedupe, due time routine stop and retry, independent review evidence filtering,
  budget-aware subagents, and usage budget enforcement.
- `scripts/evaluate_agent_v2_work_scenarios.py` evaluates semantic routing, grounding, artifact,
  confirmation, and safety behavior against live model/search infrastructure.
- WorkRun, routine, evaluation, and usage records are owner-scoped and stored in the Agent v2
  operational store; Markdown/JSONL/catalog remain the knowledge source of truth.
- 2026-07-10 local runtime smoke: a required isolated subagent completed with one delegation,
  exact evidence references, independent-review pass, and 19,725/48,000 actual tokens.
- 2026-07-10 hybrid search quality: Recall@8 1.0 and authoritative top-3 1.0 across the curated
  Dictionary, SOP, Event, Action, and relationship cases.
- 2026-07-11 live semantic scenarios: 11/11 passed with routing, operation, safety, and overall
  pass rate all 1.0. The set includes current-page Q&A, Event guidance/draft, SOP/Action/Skill draft,
  current work, similar cases, guarded Action dry-run, cross-asset explanation, and Deep Work.
- 2026-07-11 unified Pet browser smoke: 25/25 passed across the 88px image launcher, current-page
  context, grounded citations, multi-turn/session restore, SOP Task autosave, full-editor round trip,
  mobile overflow, console errors, and failed requests.
- 2026-07-11 intent-preservation smoke: local Gemma produced a grounded read-only Mermaid with no
  Task/SOP actions, then resolved the follow-up “이 흐름을 Task로 나눠줘” to a seven-Task
  `workflow_draft` with no `plan_ref` and no SOP draft. Desktop 1440x900 and 1180x850 plus mobile
  390x844 rendered nonblank SVGs without horizontal overflow, failed requests, or console errors.
- 2026-07-11 contextual starter smoke: a starter click issued exactly one Agent turn, immediately
  added one user/assistant exchange, and left no duplicate composer submission. SOP/Event/Action
  starters now require an explicit ontology neighbor rather than an arbitrary catalog match.
- 2026-07-11 Work Learning E2E: natural Task completion waited for Manual confirmation, completed the
  same WorkRun, created a provenance-bound private candidate, indexed it with pgvector, and cited it
  from a new session. REST/MCP/Python Agent Kit parity passed 9/9 checks with identical search,
  Context, WorkRun, Harness, Evidence, and KnowledgeCandidate IDs.
- 2026-07-11 final repository regression: 701/701 tests passed. This includes Agent v2, API routes,
  Business Event Detector, MCP, Action Gateway, OKF lint, runtime history, Compose, NAS deploy,
  source editing, and rollback behavior.
- 2026-07-11 live readiness is fully ready: Postgres/pgvector, local generation and embedding,
  fresh 459-record/1,023-chunk search index with 1,040 ontology edges, Deep worker, PAT policy, and
  the 10-tool MCP v2 surface. `google/gemma-4-26b-a4b-qat` and `text-embedding-bge-m3` remain
  externally managed manual residents; application load requests and unload requests are both zero.
  GPT-5.5 test mode remains disabled.
- 2026-07-11 canonical document smoke: the legacy Dictionary index link resolves to `공개 업무 용어`
  without exposing `index`, while the checked-in `index.md` remains frontmatter-free and passes the
  reserved-directory OKF rule. Runtime-only path ACL never writes derived metadata back to the file.
- 2026-07-10 scheduled Business Event smoke: worker evaluation published to `boi.events`, Event
  Router dispatched through Action Gateway, and `boi.materialize_event` created and enriched a
  private BoI result.
