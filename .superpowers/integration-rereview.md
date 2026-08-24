# Science external-agent integration rereview

## Verdict

**PASS**

Independently re-reviewed `26d6ce18cc51c7230d2ea80ebecd1f4ecf3e5f37` against:

- `docs/superpowers/specs/2026-08-25-science-verifier-design.md`
- `docs/superpowers/plans/2026-08-25-science-verifier-application.md`
- the stored-interpretation MCP contract clarified in `docs/superpowers/plans/2026-08-25-science-verifier-agent-integration.md`
- all Critical and Important findings in `.superpowers/integration-review.md`

No remaining Critical or Important defect was found in the requested closure areas. The new HEAD is safe for this integration scope. This PASS does not claim that the not-yet-completed Science application/API/UI or end-to-end qualification plan is finished.

## Prior finding closure

### Closed — Native and bridge identity/service-token authority

- `boi_wiki_mcp/app/main.py:812-816` rejects every direct Science wrapper call without a distinct interactive user bearer.
- `boi_wiki_mcp/app/main.py:3647-3663` derives the user bearer only from `Authorization: Bearer ...`, rejects the shared service token as a user token, and binds it to request-local context.
- `boi_wiki_mcp/app/main.py:3666-3682` retains optional MCP service-token transport protection while keeping user identity separate.
- Every native Science wrapper forwards `bearer_token=require_science_bearer()` with `employee_id=None`; no Science wrapper accepts a caller-provided employee ID.
- `boi_wiki_mcp/app/main.py:3878-3899` requires the custom bridge service token and, independently, a distinct user bearer for every registered Science tool.
- All Science bridge branches at `3900-4036` ignore the generic caller-provided `employee_id`, forward only the user bearer, and never set `service_token=True` for the BoI API Science call.

Adversarial evidence:

- A real JSON-RPC `tools/call` to native `/mcp` returned 401 with no credentials, returned an MCP tool error `interactive_user_identity_required` with service-token-only credentials, and made no downstream call even when `employee_id=admin-forged` was supplied.
- The same native call with both `x-service-token: svc-secret` and a distinct `Authorization: Bearer user-jwt` succeeded and forwarded exactly `bearer_token='user-jwt'`, `employee_id=None`.
- All 15 bridge Science tools returned HTTP 403 with service-token-only credentials, including read, verify, validation, proposal, activation, and withdrawal tools.
- All 15 bridge Science tools succeeded through the mocked API boundary with a distinct user bearer; every captured call used that bearer, omitted `employee_id`, and omitted service-token API authority despite a forged employee argument.

### Closed — Confirmation and mutation binding

- Proposal creation requires and forwards `request_digest`, `idempotency_key`, and `user_confirmed: true` (`boi_wiki_mcp/app/main.py:934-953`, bridge `3966-3979`).
- Release activation and withdrawal require and forward exact `release_digest`, `request_digest`, `idempotency_key`, and `user_confirmed: true` (`1028-1071`, bridge `4021-4036`).
- Interpretation confirmation names the stored interpretation and exact claim IDs, requires explicit confirmation, and carries an idempotency key (`838-856`, bridge `3911-3924`).
- Roles and the authenticated actor remain BoI API responsibilities derived from the forwarded bearer; the MCP layer does not mint `science.admin`, Power User, approval, or review authority.

### Closed — Stored interpretation verification payload parity

- `science_verify_claim` sends exactly `interpretation_id` and `release_selection` to `/api/science/claims/{claim_id}/verify` (`859-874`).
- `science_verify_document` sends exactly the stored `interpretation_id`, `release_selection`, and idempotency key to `/api/science/verify-document` (`877-893`).
- The bridge uses the same shapes (`3925-3946`).
- These calls match the application service boundary at `boi_api/app/science/service.py:1027-1067` and `1069-1138` in the Science application checkout: the server loads the authoritative confirmed interpretation and derives the Claim Packets rather than trusting caller-submitted packets.

Adversarial evidence captured unchanged payloads:

```text
verify_claim:    {interpretation_id: i1, release_selection: {foundation: rel}}
verify_document: {interpretation_id: i1, release_selection: {foundation: rel}, idempotency_key: i2}
```

### Closed — Rule and release qualification payloads

- `science_rule_qualify` forwards the complete caller-supplied qualification request unchanged to the exact rule path (`boi_wiki_mcp/app/main.py:995-1006`; bridge `4001-4007`).
- `science_release_validate` forwards `release_id`, `release_digest`, and sealed `holdout_manifest_digest` (`1009-1025`; bridge `4008-4020`).
- The adversarial bridge probe confirmed both payloads arrived intact and under the distinct user bearer.

### Closed — Canonical report digest and export byte integrity

- `api_get_bytes` now fails closed when the API omits `x-science-report-digest` (`boi_wiki_mcp/app/main.py:714-748`).
- It preserves that header as `report_digest`, preserves content type and disposition, and exposes the independently computed export-byte hash under the non-conflicting name `content_sha256` (`749-755`).
- Markdown and PDF probe bodies with the same API report digest retained one equal `report_digest` while producing different `content_sha256` values. The obsolete ambiguous `sha256` field was absent.
- A missing canonical digest produced `RuntimeError: Science report export is missing x-science-report-digest` rather than silently substituting a byte hash.

### Closed — Exact 15-tool smoke and meaningful regression coverage

- `scripts/check_boi_wiki_mcp.py:44-60` defines the required 15-tool Science set.
- Both MCP-client and stateless JSON-RPC inventory paths compute missing Science tools independently of total tool count (`170-178`, `234-245`).
- Overall smoke success explicitly requires `science_tools_ok is True` (`942-947`).
- An adversarial mocked protocol reporting 999 total tools but missing `science_verify_document` returned exit code 1 and listed the missing tool.
- A live temporary MCP process passed the real checker with 146 tools, 11 resource templates, 5 prompts, `science_tools_ok: true`, and no missing Science tools.
- Tests now cover real export response headers, stored interpretation payloads, qualification/release payloads, missing bearer, service-only bridge denial, forged employee suppression, request digest/idempotency fields, and missing-tool smoke failure.

## Skill and authority rereview

- The verifier and curator skills now explicitly require an authenticated user bearer and state that the service token is not a reader, verifier, curator, Power User, or Admin identity.
- The previous positive controls remain intact: verdict labels are preserved, `CONSISTENT` is not upgraded, inactive Evidence is not used, self-approval and service-token approval are forbidden, proposal review remains Web/REST-only, and activation is not automatic.
- No scientific fact, Citation, verdict engine, review decision, role grant, or activation fallback was added to MCP or the skills.

## Fresh verification

- `pytest -s tests/test_science_mcp.py tests/test_science_skills.py tests/test_science_harnesses.py tests/test_boi_wiki_mcp.py -q` — **83 passed**, 2 unrelated FastAPI `on_event` deprecation warnings.
- `ruff check boi_wiki_mcp/app/main.py scripts/check_boi_wiki_mcp.py scripts/sync_science_harnesses.py tests/test_science_mcp.py tests/test_science_harnesses.py tests/test_science_skills.py tests/test_boi_wiki_mcp.py` — passed.
- `python scripts/sync_science_harnesses.py --check` — passed.
- `python scripts/okf_lint.py --root data --strict-links --strict-media` — passed; 332 Markdown documents checked.
- `git diff --check 9dbea5c..26d6ce1` — passed.
- Live smoke: `python scripts/check_boi_wiki_mcp.py --base-url http://127.0.0.1:28251 --mcp-url http://127.0.0.1:28251/mcp --summary` — exit 0, 146 tools, exact required Science set present. The temporary server was then shut down and port 28251 was no longer listening.
- Adversarial probes were read-only and used mocked downstream API functions; they did not create Science records or change production/test files.

## Completion boundary

Only `.superpowers/integration-rereview.md` was created during this rereview. Production and test files were not modified.
