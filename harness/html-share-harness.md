---
title: HTML Share Harness
type: boi/harness
status: reviewed
---

# HTML Share Harness

Use this harness when publishing a self-contained HTML document (a general document: 보고서, 대시보드, 가이드, anything) to a BoI Wiki shortlink, whether through the Web UI (`/share`) or through MCP tools. Both paths share the same contract.

## Self-contained Principle

- One `.html` file, 20MB max. Inline all CSS/JS/data. The intranet has no external CDN, so external `<script src=`/`<link href=` http(s) references are reported as lint warnings and will likely break for readers.
- Inline scripts are allowed and run inside an isolated iframe (`sandbox="allow-scripts"`); the raw route serves `Content-Security-Policy: sandbox allow-scripts; frame-ancestors 'self'` plus `Referrer-Policy: no-referrer` (blocks third-party sites from framing `/r/{name}` and stops the shortlink name leaking via the `Referer` header). Never add `allow-same-origin` — the combination lets uploaded HTML reach wiki cookies/sessions (XSS session theft).
- Secret-looking values (api key/token/password patterns) are rejected at upload.

## BoI HTML Profile (JSON-LD)

Every stored HTML gets exactly one `<script type="application/ld+json" id="boi-profile">` block in `<head>`, injected/replaced by the server on every upload (never duplicated; the rest of the document is preserved). The payload is schema.org `DigitalDocument` plus a `boiProfile` object carrying the same BoI Profile fields as Markdown frontmatter:

| Field | Value |
|---|---|
| `okf_version` / `boi_profile_version` | `"0.1"` / `"0.1"` |
| `type` | `boi/html-document` |
| `title` / `description` | From the upload form/args (description falls back to a generated one-liner) |
| `timestamp` | Publication time (KST ISO) |
| `boi_id` | `boi:public:html:{name}` / `boi:team:{team_id}:html:{name}` / `boi:private:{employee_id}:html:{name}` |
| `visibility` | `public` / `team` / `private` |
| `classification` | `internal` |
| `owner` | Private scope: MUST equal the path employee_id. Team/public: uploader label |
| `acl_policy` | `acl:public` / `acl:team:{team_id}` / `acl:private:{employee_id}` |
| `status` | `reviewed` (with `review.reviewer` = uploader label, `review.review_status: user_confirmed`) |
| `content_role` | `html_artifact` |
| `shortlink` | `/{name}` |
| `source_refs` | Upload provenance: `{type: upload, ref: <original filename>, uploaded_by: <employee_id>, sha256: <sha256 of the original uploaded bytes>}` |

`okf_lint` validates every `*.html` under `data/boi`: the block must parse, the `boiProfile` must pass the required-field/enum validators and the path↔ACL rule for the html path.

## Name / Scope / Tombstone Rules

- Name: `^[a-z0-9][a-z0-9-]{1,63}$`, reserved root segments denied, FCFS. Default name comes from the filename slug; check with `GET /api/share/names/{name}/availability` or MCP `shortlink_check`.
- Only the owner can re-upload or update the same name (409 with suggested alternatives otherwise).
- Scope decides storage: `data/boi/{public|team/{team_id}|private/{employee_id}}/html/{name}.html`. Team scope requires team membership.
- Delete = tombstone: the name is never reusable again (bookmark-hijacking protection), the stored HTML and its knowledge card are removed.
- Doc-kind shortlinks for existing accessible BoI documents use `POST /api/share/links` or MCP `shortlink_register` with the same name policy.

## Publish Flow (preview → user_confirmed → publish)

1. Preview: `POST /api/share/preview` or MCP `html_share_preview` — non-mutating; validates content, name availability, and scope, and shows what would be published.
2. Confirm: agents must obtain explicit user confirmation; MCP `html_share_publish` and `shortlink_register` refuse without `user_confirmed=true`.
3. Publish: `POST /api/share/html` (multipart from the Web UI, or JSON `content_base64` from MCP/automation) injects the BoI HTML Profile, writes the knowledge card, updates the registry, git-commits, and best-effort publishes `html.share.published.v1`.

## Knowledge Card Contract

- A sibling card `data/boi/{scope}/html/{name}.md` is generated synchronously on every publish. The card owns the canonical `boi_id` (the colon→path mapping resolves to this `.md`), carries full OKF frontmatter (`type: boi/html-document`, `status: reviewed`, reviewer, tags `[HTML, Share]`), and `source_refs` with (a) `html_artifact` ref + sha256 of the stored (post-injection) HTML and (b) upload provenance.
- Search, link graph, freshness, and promotion loops operate on the card; the card represents the HTML.
- Lint enforces card↔HTML integrity: missing card or sha256 mismatch is an error ("html artifact sha256 mismatch with knowledge card").
- Re-upload regenerates the card (created timestamp preserved from the registry). Delete removes the card with the HTML.

## Metadata Patch (title/description/visibility) and Ownership Transfer

- `PATCH /api/share/{name}` (owner only, admin break-glass allowed): change title/description/visibility/team without re-uploading the file. Title/description changes re-inject the BoI HTML Profile and regenerate the knowledge card in place. Visibility/team changes move the stored HTML + card to the new scope path (old files removed) and regenerate the profile/card with the new `boi_id`/`acl_policy`/owner rules. Owner never changes through this endpoint. 400/409 with Korean messages on invalid combos (unknown visibility, non-member team, destination collision); 403 for non-owner.
- `POST /api/share/{name}/transfer` body `{new_owner_employee_id}` (current owner or `boi.admin`): reassigns ownership. The registry record's `owner_employee_id` changes and a `transfers` entry `{from, to, by, at}` is appended (history preserved, never overwritten). Private-scope shares physically move to the new owner's private folder (path↔ACL rule); team/public shares keep their path but the profile/card owner field and registry owner change. The old owner immediately loses owner privileges (403 on PATCH/delete/transfer, 409 on re-upload as if it were someone else's name).
- Both endpoints reuse the same move/delete/regenerate patterns as upload and delete — no new storage or ACL logic.

## Prohibited

- External http(s) `<script src=`/`<link href=` references (lint warning; will break on the intranet — inline instead).
- Secrets of any kind in the HTML body.
- `allow-same-origin` in any sandbox attribute or CSP header (fixed by code comment + tests).

## One Contract, Many Consumers

The Web UI (`/share`), REST API, and MCP tools (`html_share_publish`, `html_share_preview`, `shortlink_check`, `shortlink_list`, `shortlink_register`) all use the same registry, the same name policy, the same profile injection, and the same knowledge card generation. Web users never need to know the harness exists; agents must follow it.

## Validation

```bash
python scripts/okf_lint.py --root data --strict-media --strict-links
python scripts/check_html_share.py --base-url http://localhost:28000
```

`GET /api/harness/acceptance` includes `html_share_lint` (Verification) and `shortlink_registry_integrity` (State).
