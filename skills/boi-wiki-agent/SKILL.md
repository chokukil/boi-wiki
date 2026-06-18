---
name: boi-wiki-agent
description: Use when working on BoI Wiki SOPs, OKF documents, action specs, MCP integration, Langflow BoI flows, workflow runtime, draft edits, or BoI Wiki validation. This skill bootstraps Codex into BoI Wiki MCP and harness resources instead of duplicating the full domain rules.
---

# BoI Wiki Agent

Use this skill before creating or changing BoI Wiki knowledge, SOP workflows, action catalog entries, Langflow BoI flows, MCP tools/resources/prompts, or draft edits.

## Startup

1. Prefer BoI Wiki MCP if available.
   - MCP URL: `http://localhost:8200/mcp`
   - Smoke: `python scripts/check_boi_wiki_mcp.py`
2. If MCP is unavailable, read repo harness files:
   - `harness/sop-authoring-harness.md`
   - `harness/action-authoring-harness.md`
   - `harness/web-draft-editing-guide.md`
3. For user-facing guidance, read BoI Wiki manuals under:
   - `data/boi/public/boi-wiki-manual/`

## Operating Rules

- OKF Markdown documents and action catalog are source of truth.
- Web and MCP writes are draft-only. Do not claim source or Git changed until an agent applies, validates, tests, and commits.
- Langflow is one connector kind, not the default connector.
- Always search existing SOPs, event types, action specs, manual tasks, and harness docs before creating new ones.
- Keep images under `_media/`, update `media-manifest.yaml`, and use standard Markdown image syntax.

## SOP Work

When a user supplies an SOP image, OCR text, or process description:

1. Search BoI Wiki for related concepts and reusable actions.
2. Extract workflow stages, entry events, emitted events, evidence, automated actions, manual handoffs, outputs, and failure modes.
3. Produce a package: SOP doc, event type docs, action specs, manual actions, catalog draft patches, citations, OKF links, and media references.
4. Use Langflow only when an LLM/agent stage is actually required.

## Action Work

Support all connector kinds: `api`, `webhook`, `mcp`, `langflow`, `manual`, `event_broker`, and `boi_writer`.

For each action, create or update the public action-spec BoI document and the catalog entry together. High-risk system actions require a manual approval action.

## Validation

Run the narrowest useful checks first, then full checks before completion:

```bash
pytest tests -q -s
python scripts/okf_lint.py --root data --include-logs --strict-media
python scripts/check_boi_wiki_mcp.py
python scripts/audit_langflow_flows.py
python scripts/run_equipment_sop_poc.py
```
