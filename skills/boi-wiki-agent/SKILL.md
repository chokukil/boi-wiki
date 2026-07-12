---
name: boi-wiki-agent
description: Use BoI Wiki v2 knowledge, current work, SOPs, Business Events, Actions, Skills, and guarded drafts through the shared Web, REST, and MCP capability contract.
---

# BoI Wiki Agent

Use this skill when a task needs BoI Wiki knowledge or a BoI-backed work operation. The generated Codex contract in `agent_kit/codex/SKILL.md` is the canonical external-Agent reference; keep this repository skill aligned with it.

## Start

1. Prefer the v2 Streamable HTTP MCP endpoint.
   - Environment-neutral URL: `<BOI_MCP_URL>/mcp/v2`
   - Local example: `http://localhost:8200/mcp/v2`
   - Authenticate with `Authorization: Bearer $BOI_PAT`. Never put a PAT in chat or invent an employee ID.
2. Send ordinary natural-language requests to `boi_agent` without a `capability_id`. BoI Wiki must infer the work intent and route it.
3. Preserve `work_session_id`, `work_run_id`, source IDs, citation IDs, GoalPlan, artifact IDs, and pending confirmation references across follow-up turns.
4. Treat `unavailable`, a Harness blocker, or no progress as a real stop. Do not replace them with a canned success response.

## MCP v2 Tools

Use the ten public tools only:

- `boi_bootstrap`: identity, readiness, and integration discovery
- `boi_agent`: natural questions and work continuation
- `boi_search`: ranked, neighbors, path, impact, or tour retrieval
- `boi_get`: exact ACL-visible source or citation retrieval
- `boi_my_work`: current Inbox, Workflow, and Task work
- `boi_context`: bounded WorkContextPack retrieval
- `boi_plan`: explicit deterministic draft planning
- `boi_confirm`: continue a reviewed plan without bypassing guardrails
- `boi_job_status`: deep-work status and result retrieval
- `boi_tools_search`: progressive capability discovery

Use REST `/api/v2/*` only when MCP is unavailable or a deterministic integration requires it. Web, REST, MCP, and Agent Kit clients must preserve the same source, citation, WorkRun, artifact, and permission results.

## Read And Understand

- Start with `boi_agent` for a natural request. Use `boi_search(view="ranked")` when the caller needs explicit evidence selection.
- Use `boi_search` views `neighbors`, `path`, `impact`, and `tour` for relationships, connection paths, change scope, and an order for understanding. Open exact references with `boi_get`.
- Treat the current page as an interpretation anchor, never as a forced search boundary. Search all ACL-visible Wiki knowledge with ontology, lexical, embedding, and runtime evidence.
- Cite only returned citation IDs and source URLs. Do not cite a selected source that did not support the answer.
- `index.md` and `log.md` are navigation files, not knowledge. Never use them in search, embedding, ontology, citation, or current-page context.
- Documents with `status: deprecated` are historical audit material. Exclude them from normal answers and recommendations unless the user explicitly asks for history.
- Keep history seed rows out of current work. Use `boi_my_work` for active work and treat old execution history as similar-case evidence only.

## Context, Harness, And Loop

- Build work from the current goal, Workflow and Task, Task mode, completion checks, required and acquired evidence, related assets, similar cases, and recent loop deltas.
- Keep large files, CSV, logs, and external-AI transcripts in the Data Library. Pass only an ACL URL, summary, profile, sample, and checksum into context.
- Every operation follows `preflight -> plan -> validate -> preview/test -> confirmation -> apply/run -> post-verify` as required by its Harness.
- A loop iteration must add evidence, an Action result, human input, an artifact, a state transition, a blocker, or a knowledge candidate. Repeated query or tool calls without a new delta are a stop condition.
- Never mark a Task complete from model prose. Completion comes from structured checks, Evidence Ledger entries, Action results, and required human confirmation.

## Draft And Execute

- Use `boi_plan` for an explicit deterministic capability such as `business_event.plan`, `sop.plan`, `action.plan`, `skill.plan`, or `knowledge.draft`.
- Drafts are private and do not change production state.
- Call `boi_confirm` only after explicit user review. Confirmation cannot bypass ACL, RBAC, publication review, Task mode, Action risk, or system-binding checks.
- Manual Tasks are performed and confirmed by people. Copilot Tasks let internal or external AI prepare evidence and drafts but require a person to finish. Autopilot Tasks may run only allowlisted low-risk Actions with system-verifiable completion checks.
- Deep work returns drafts and evidence. Poll its returned reference with `boi_job_status`; never claim completion from an empty artifact or missing Evidence Ledger.

## Domain Work

- Before creating an SOP, Business Event, Action, or Skill, retrieve existing assets and actual usage relationships first.
- Model a Workflow as a set of Tasks. Keep each Task's purpose, Manual/Copilot/Autopilot mode, completed state, evidence to check, result, exception path, and related Event or Action explicit.
- A Business Event defines when work begins or changes state. Connect it to a Workflow or Task only when the requested business relationship is supported by evidence.
- Actions are Task execution mechanisms. Preview or dry-run them before any real side effect, and require risk-appropriate confirmation.
- Langflow is one connector kind and an optional visual/debug surface, not the default Agent runtime or the source of truth.

## Learn And Publish

- A `KnowledgeCandidate` is reusable private provisional knowledge, not a shared Wiki change.
- Prefer strengthening an existing canonical asset over creating a duplicate document.
- Never promote raw chat, full logs, simulated output, or an unverified model answer directly into Team/Public knowledge.
- Team/Public SOP, Business Event, Action, Skill, and knowledge changes require source-backed diff review and Harness validation.
- OKF Markdown, Git history, and catalogs remain the source of truth. Search indexes, pgvector, and ontology are rebuildable read models.

## Repository Authoring

- Use the canonical manuals under `data/boi/public/boi-wiki-manual/` for user-facing guidance.
- Keep screenshots under `_media/`, update `media-manifest.yaml`, and use standard Markdown image syntax.
- Use canonical `/docs/{boi_id}` links for current guides. Preserve deprecated documents with frontmatter and `status: deprecated` rather than deleting their audit history.
- Never give `index.md` or `log.md` a synthetic `doc:` identity. Folder navigation must resolve to an OKF overview or canonical guide.

## Validation

Run the narrowest useful checks first, then the shared quality gates before completion:

```bash
python scripts/okf_lint.py --root data --strict-media --strict-links
python scripts/check_agent_v2_search_quality.py --base-url http://127.0.0.1:8765 --employee-id 100001
python scripts/check_agent_v2_interface_parity.py --base-url http://127.0.0.1:8765 --employee-id 100001
python scripts/check_boi_wiki_mcp.py --mcp-url http://localhost:8200/mcp/v2
```
