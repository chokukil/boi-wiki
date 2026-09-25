# Supervision and correction contract

Use the connected server's `boi_knowledge_supervision(operation, request)` or HTTP `POST /api/v2/knowledge-supervision` with `{operation, request}`. This is the `boi/knowledge-supervision@1` contract. These instructions do not make an older server implement this endpoint. Discover it through the current authenticated bootstrap/tool surface.

| Operation | Request | Meaning |
| --- | --- | --- |
| `list` | `task_ref` | Read pending instructions. Does not resolve them. |
| `read` | `task_ref`, `event_ref` | Read the exact retained event and current resolution state. |
| `correct` | `task_ref`, `expected_revision`, `reason`, `idempotency_key`; optional `unit_ids`, `asset_revisions`, `cause_code` | Record the user's correction for exact current targets. |
| `resolve` | `task_ref`, `expected_revision`, `event_ref`, `reason`, `idempotency_key` | Report how the correction was handled; preserve its history. |
| `stop` | `task_ref`, `expected_revision`, `reason`, `idempotency_key` | Stop further task publication through existing work controls, retaining work and attempts. |
| `document_feedback` | `revision`, `comment`, `idempotency_key` | Send the reader's actual feedback about a published document to its identity owner's Inbox. Requires `boi.read` and current document access. |
| `feedback_inbox` | optional `after`, `limit` | Read the current identity owner's accessible feedback, including linked published corrections. |
| `feedback_read` | `feedback_ref` | Read the reporter's or responsible owner's current-access receipt. |

An `event_ref` or asset revision is `{ref, revision_digest}` returned by Wiki. `expected_revision` is the current positive task revision. Reasons must be nonblank and at most 8,000 characters; idempotency keys are at most 240 characters. Correction `cause_code` is `source`, `interpretation`, `coverage` or `other`. Omit targets only when the user's instruction applies to the whole task at that exact revision; the server binds the affected unit IDs. Selected asset revisions must be current, authorized and related to the task. The server enforces these boundaries.

Read operations require `boi.read`; mutations require `boi.draft` and current source rights. A correction neither changes the original material nor repairs a meaning automatically. Perform the supported repair within the existing task budget, retaining prior useful results. Report resolution with the actual handling and remaining gaps. `reported_resolved` is not semantic approval, scientific verification or a new executor receipt. Stop does not prove that an already running external invocation was cancelled; preserve its unknown outcome and recover its original output through the work contract.

Use the helper from its installed directory:

```bash
python3 scripts/boi_knowledge_work.py supervision --action list --task-ref TASK_REF
python3 scripts/boi_knowledge_work.py supervision --action read --request-file event-read.json
python3 scripts/boi_knowledge_work.py supervision --action correct --request-file correction.json
python3 scripts/boi_knowledge_work.py supervision --action resolve --request-file handled-correction.json
python3 scripts/boi_knowledge_work.py supervision --action stop --request-file stop-request.json
```

Request files contain the inner request object only. The configured agent prepares them from actual user instructions and current task state; the end user need not assemble JSON. Keep the exact request and key after an uncertain response. Read task/event state before deliberately resending that same request; do not regenerate a replacement or reset a budget. The helper never retries automatically.

Task correction delivery is implemented through stored instructions. This contract does not configure background notifications, notification preferences or autonomous monitoring schedules.

Published-document feedback is separate from task instruction handling. Link to the returned document `feedback_url` when the external host cannot collect an inline answer comment. Do not claim that the host's final wording or selected text was captured: this path records the submitted comment and exact document revision. The Inbox currently routes to the original identity owner; team assignment is not implemented.

For an owner correction, read the actual current published document and native asset. Preserve its namespace, logical ID, original sources, source spans and dependencies. Prepare a `revise` change with its exact `previous_revision` and `correction` containing `expected_policy_revision`, `reason`, `source_difference` and any returned `feedback_refs`. Keep the same single target space. Author the corrected body and meaning together, preserving conditions, uncertainty and raw source. A new local source opinion can cite an exact declared `existing_source` envelope instead of `source_object_id`; retain `source_byte_digest`, field locator, quote and occurrence. No source re-upload or fresh source identity is required for this path.

Use the existing exact bundle preview, direct-reference impact, one browser confirmation, upload, registered native checks, scoped qualification and publication flow. Only that publication transaction sets linked feedback to `correction_published`. Reporting `resolve` on a task does not change document feedback or publish a correction. Current limits: identity-owner correction, one unchanged space, preserved source closure, and up to 256 visible prior revisions. Another team editor, source re-ingestion with a changed closure, multi-space corrections and assignment need further adapters; never create another user's copy to bypass a rejection. The high-level `assemble` command still creates new source-derived records; it is not a correction authoring interface. An external agent must prepare the exact revision proposal before the generic bundle packing/confirmation path.
