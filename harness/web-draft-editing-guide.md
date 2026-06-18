# Web Draft Editing Guide

Web editing is intentionally draft-only.

When a user clicks `Save Draft` in BoI Wiki, or an agent calls an MCP draft tool, the app records a draft request under `data/drafts/`. It does not change the original Markdown/YAML file and does not create a Git commit.

Agent apply flow:

1. Read the draft and its `base_sha256`.
2. Confirm the target file still has the same hash.
3. Run source validation, OKF lint, catalog validation, and secret scan.
4. Apply the file change.
5. Run focused tests and smoke checks.
6. Commit the curated change to Git.
7. Update the draft status with `applied_at`, `applied_by`, and `commit_hash`.

This split keeps quick web edits ergonomic without making every typo or invalid YAML edit part of curated knowledge history.
