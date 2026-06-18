# BoI Harness

This directory is the repo-side source for agent harness guidance.

Use these documents before creating or changing curated BoI Wiki knowledge:

- `web-draft-editing-guide.md`: web edits create drafts only; agents apply and commit.
- `sop-authoring-harness.md`: create SOP packages with events, actions, citations, and OKF links.
- `action-authoring-harness.md`: create executable API/Webhook/MCP/Langflow/manual/event-broker action packages.

The BoI Wiki copies live under `data/boi/public/harness/` so Langflow, Codex, Claude, and other agents can lazy-load the same rules through the wiki.
