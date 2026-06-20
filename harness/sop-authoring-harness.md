# SOP Authoring Harness

Use this harness when a user asks an agent to convert an image, existing document, OCR text, or free-form process description into a BoI Wiki SOP.

Inputs:

- `source_images`: screenshots, photos, or exported pages supplied by the user.
- `ocr_text`: extracted text, if available.
- `domain`: business area or equipment/process family.
- `owner`: accountable human/team.
- `visibility`: default `private`; use `team` or `public` only when explicitly requested.
- `source_refs`: source files, conversations, images, or URLs.
- `target_folder`: OKF folder path.

Required output package:

- SOP Markdown document with BoI Profile frontmatter.
- Event Type docs for every workflow trigger.
- Action package drafts for automated actions across API, Webhook, MCP, Langflow, Event Broker, and BoI Writer connectors.
- Manual action docs for human judgment, approval, field work, or completion checks.
- Catalog patch drafts for `data/event_catalog/event_types.yaml` and `data/action_catalog/actions.yaml`.
- `# Citations` and bundle-relative OKF Markdown links.
- Media assets under `_media/`, `media-manifest.yaml`, and companion media reference docs when the source is an image or Browser screenshot.

Every SOP stage must include `id`, `name`, `purpose`, `entry_event`, `next_stage`, `emits_event`, `source_systems`, `automated_actions`, `manual_actions`, `outputs`, `failure_modes`, and `acceptance_criteria`.

Default workflow:

1. Search BoI Wiki through `boi-wiki-mcp` for existing SOPs, event types, action specs, and manuals.
2. Extract stages, triggers, evidence, automated actions, human decisions, approvals, and outputs.
3. Prefer existing action specs. Create new action package drafts only when no suitable action exists.
4. Use Langflow only when a stage needs LLM/agent reasoning that cannot be represented as API/MCP/Webhook/manual/event-broker actions alone.
5. For direct source/body edits, use preview, validation, apply, and auto-commit. For Team/Public promotion, use user confirmation plus remote synchronous validation and publish.
