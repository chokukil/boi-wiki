---
name: boi-wiki-v2
description: Use BoI Wiki as an ACL-aware business knowledge and workflow system through its compact v2 MCP surface.
---

# BoI Wiki v2 Project Skill

Send normal requests to `boi_agent` without selecting a capability. Preserve the returned `work_session_id`, `work_run_id`, source IDs, citations, GoalPlan, and artifact IDs across follow-up turns. Use `boi_bootstrap` only for readiness diagnostics or deterministic integration discovery.

- Search with `boi_search(view="ranked")`. Reuse `boi_search` with `view="neighbors"`, `"path"`, `"impact"`, or `"tour"` for graph-first exploration, then open exact references with `boi_get`.
- Use `boi_my_work` only for present work. Historical seed data is evidence, not a current assignment.
- Keep the context compact: summaries, profiles, checksums, URLs, and evidence IDs instead of raw files or complete logs.
- Create drafts with `boi_plan`. Draft does not mean published, approved, or executed.
- Use `boi_confirm` only when the user explicitly confirms the identified plan.
- Do not send `employee_id`; the BoI PAT determines identity, ACL, and effective RBAC.
- If a capability is unavailable, explain that state and continue only with capabilities marked ready.
- For deep work, poll `boi_job_status` and require an evidence ledger before reporting completion.
- Treat the current page as an anchor while allowing ACL-visible Wiki-wide ontology, lexical, embedding, and runtime evidence.
- Continue a WorkRun only with a new evidence, Action result, human input, artifact, state transition, or blocker. Stop on repeated no-progress calls.
- Treat KnowledgeCandidate as private provisional learning. Shared promotion still requires Harness validation and explicit review.
