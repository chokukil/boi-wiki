# BoI Harness

This directory is the repo-side source for agent harness guidance.

Use these documents before creating or changing curated BoI Wiki knowledge:

- `harness-responsibility-matrix.md`: map Observation, Context, Control, Action, State, and Verification to BoI API/MCP/UI/runtime checks.
- `web-draft-editing-guide.md`: source/body edits use preview, validation, apply, and auto-commit; Team/Public promotion uses user-confirmed validated publish.
- `sop-authoring-harness.md`: create SOP packages with events, actions, citations, and OKF links.
- `action-authoring-harness.md`: create executable API/Webhook/MCP/Langflow/manual/event-broker/BoI-writer action packages.
- `data-lake-query-harness.md`: use optional Data Lake artifacts and structured demo sources through BoI API/MCP without making MinIO or PostgreSQL core dependencies.
- `data-lake-artifact-harness.md`: store file evidence as Data Lake artifacts and pass only URL/profile/sample metadata into BoI/LLM context.
- `science-source-curation-harness.md`: curate locator-bound Source/Evidence proposals without granting AI scientific authority.
- `science-knowledge-authoring-harness.md`: author atomic Science Knowledge with explicit assumptions, applicability, and Evidence scope.
- `science-rule-qualification-harness.md`: qualify deterministic Rules with ten real-claim boundary cases and an independent holdout.
- `science-verification-harness.md`: verify interpretation, verdict, visible Evidence, immutable reports, and cross-channel parity.

The BoI Wiki copies live under `data/boi/public/harness/` so Langflow, Codex, Claude, and other agents can lazy-load the same rules through the wiki or BoI Wiki MCP. Codex skills should stay thin and bootstrap agents into MCP/harness resources instead of duplicating the full rules.
