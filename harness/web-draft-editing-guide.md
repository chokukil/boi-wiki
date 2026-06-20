# Web Source Validated Editing Guide

Direct Web/MCP source and body editing uses validated apply and auto-commit.

When a user clicks `Apply & Commit` in BoI Wiki, or an agent calls an MCP apply tool with explicit user confirmation, the app validates the proposed Markdown/YAML change, applies it only if validation passes, and creates a Git commit automatically.

Apply flow:

1. Confirm the target file still matches `base_sha256`.
2. Render Markdown preview when applicable.
3. Run source validation, OKF lint, catalog validation, and secret scan.
4. If validation fails, return structured errors and fix suggestions without changing the file.
5. Apply the file change.
6. Run post-apply validation.
7. Commit the curated change to Git.
8. If post-apply validation or commit fails, roll the file back and return failure feedback.

This keeps quick web edits ergonomic while preventing invalid YAML, broken OKF links, or uncommitted edits from entering curated source history.

Team/Public promotion is a separate path: after user preview approval, the agent calls promotion submit, the remote wiki validates synchronously, and successful candidates publish immediately with HOTL watching.
