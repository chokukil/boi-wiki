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
- Action package drafts for automated actions.
- Manual action docs for human judgment, approval, field work, or completion checks.
- Catalog patch drafts for `data/event_catalog/event_types.yaml` and `data/action_catalog/actions.yaml`.
- `# Citations` and bundle-relative OKF Markdown links.

Every SOP stage must include `id`, `name`, `purpose`, `entry_event`, `next_stage`, `emits_event`, `source_systems`, `automated_actions`, `manual_actions`, `outputs`, `failure_modes`, and `acceptance_criteria`.
