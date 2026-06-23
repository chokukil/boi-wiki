---
name: boi-wiki-agent
description: Use when working on BoI Wiki SOPs, OKF documents, action specs, MCP integration, Langflow BoI flows, workflow runtime, validated edits, or BoI Wiki validation. This skill bootstraps Codex into BoI Wiki MCP and harness resources instead of duplicating the full domain rules.
---

# BoI Wiki Agent

Use this skill before creating or changing BoI Wiki knowledge, SOP workflows, action catalog entries, Langflow BoI flows, MCP tools/resources/prompts, or validated edits.

## Startup

1. Prefer BoI Wiki MCP if available.
   - MCP URL: `http://localhost:8200/mcp`
   - Smoke: `python scripts/check_boi_wiki_mcp.py`
   - Use `ontology_search` first when the user asks broad domain/search questions across SOP/Event/Action/Dictionary/runtime evidence.
   - Use `boi_agent_chat` when the user asks a page-aware question or wants recommendations from current context.
   - Use `boi_search` only when the task needs a BoI document list.
   - Use `agent_inbox` for "what do I need to act on" questions.
   - Use `dictionary_resolve` before interpreting shop-floor aliases, acronyms, or user-specific terms.
2. If MCP is unavailable, read repo harness files:
   - `harness/sop-authoring-harness.md`
   - `harness/action-authoring-harness.md`
   - `harness/web-draft-editing-guide.md`
3. For user-facing guidance, read BoI Wiki manuals under:
   - `data/boi/public/boi-wiki-manual/`

## Operating Rules

- OKF Markdown documents and action catalog are source of truth.
- Web and MCP source/body edits use preview, validation, apply, and auto-commit. MCP apply tools require explicit `user_confirmed: true`. Team/Public promotion is separate: after user preview approval, call the validated promotion publish path and treat HOTL as post-publication oversight.
- Native BoI Agent in `boi-api` is the production Agent backend. Langflow is one connector/debug backend, not the default Agent engine.
- Langflow is one connector kind among `api`, `webhook`, `mcp`, `manual`, `event_broker`, and `boi_writer`; do not model BoI Wiki as Langflow-only.
- BoI API/MCP are the official external Agent interfaces. Langflow direct run URLs are trusted/dev integration paths, not user-facing public APIs.
- Always search existing SOPs, event types, action specs, manual tasks, and harness docs before creating new ones.
- Keep images under `_media/`, update `media-manifest.yaml`, and use standard Markdown image syntax.
- Private memory and dictionary entries are BoI documents. Do not promote them automatically to Team/Public.

## SOP Work

When a user supplies an SOP image, OCR text, or process description:

1. Search BoI Wiki for related concepts and reusable actions.
2. Extract workflow stages, entry events, emitted events, evidence, automated actions, manual handoffs, outputs, and failure modes.
3. Produce a package: SOP doc, event type docs, action specs, manual actions, catalog draft patches, citations, OKF links, and media references.
4. Use Langflow only when an LLM/agent stage is actually required.

## Action Work

Support all connector kinds: `api`, `webhook`, `mcp`, `langflow`, `manual`, `event_broker`, and `boi_writer`.

For each action, create or update the public action-spec BoI document and the catalog entry together. High-risk system actions require a manual approval action.

## Agent / Search Work

- Keep `/api/boi` and MCP `boi_search` document-only for compatibility.
- Use `/api/search/ontology` or MCP `ontology_search` for grouped knowledge graph exploration.
- Use `/api/agents/boi-wiki/chat` or MCP `boi_agent_chat` for page-aware answers. Expect `used_backend=native_langgraph` unless the user explicitly asks to test Langflow legacy/debug mode.
- Use dictionary priority `private → team → public` when expanding terms.
- Runtime links, raw logs, and recent activity are evidence signals, not OKF concept graph edges.
- Mutating Agent operations such as manual handoff completion, source/body apply, promotion, and action invoke require explicit user confirmation.

## Validation

Run the narrowest useful checks first, then full checks before completion:

```bash
pytest tests -q -s
python scripts/okf_lint.py --root data --include-logs --strict-media
python scripts/check_boi_wiki_mcp.py
python scripts/audit_langflow_flows.py
python scripts/run_equipment_sop_poc.py
```
