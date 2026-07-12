---
name: boi-wiki-v2
description: Search and use BoI Wiki knowledge, current work, similar cases, and guarded draft capabilities through the v2 API or MCP contract.
---

# BoI Wiki v2

Use this skill when a task needs BoI Wiki documents, SOPs, Business Events, Actions, Skills, Inbox work, execution history, or reusable knowledge drafts.

## Start

1. Send ordinary user requests to `boi_agent` without a `capability_id`; BoI Wiki routes the goal automatically.
2. Preserve `work_session_id`, `work_run_id`, source IDs, citation IDs, GoalPlan, and artifact IDs across follow-up turns.
3. Use `boi_bootstrap` or `boi_tools_search` only for diagnostics and deterministic integration discovery.
4. Treat `unavailable` as unavailable. Do not replace it with a canned answer.

## Read

- Start with `boi_search(view="ranked")` for ACL-visible evidence. Use the same tool with `view="neighbors"`, `"path"`, `"impact"`, or `"tour"` when the task depends on relationships, change scope, or an order for understanding; open exact references with `boi_get`.
- Use `boi_my_work` for current work. Do not present history seed rows as current work.
- Fetch large artifacts by reference. Do not paste raw files or long logs into the working context.
- Cite returned citation IDs and source URLs in conclusions. Fetch exact excerpts with `boi_get`.
- Treat the current page as an interpretation anchor, not a forced search boundary. Use the ACL-visible Wiki-wide evidence selected by the returned ContextManifest.

## Draft And Execute

- Use `boi_plan` with an explicit capability such as `business_event.plan`, `sop.plan`, `action.plan`, `skill.plan`, or `knowledge.draft`.
- Draft results are private and are not production changes.
- Call `boi_confirm` only after explicit user review. Confirmation still does not bypass publication, Action, RBAC, Task mode, or risk guardrails.
- Never invent an employee ID or ask the user to put a PAT in chat. Identity comes from the bearer token.
- Do not declare a Task complete from model text. Continue the returned WorkRun with a new evidence, Action result, human confirmation, state transition, or blocker delta.
- Repeated query/tool calls without a new delta are a stop condition. Surface the blocker or ask for human input.

## Deep Work

- Ask `boi_agent` naturally for long research and then poll a returned job with `boi_job_status`.
- Stop when the job reports failure or no progress. Never claim completion without a non-empty artifact and evidence ledger.

## Learn

- A `KnowledgeCandidate` is reusable private provisional knowledge, not a shared Wiki change.
- Review or archive it before reuse; request promotion only after Harness validation and explicit user review.
- Never turn a raw chat, full log, or unverified model answer directly into shared knowledge.
