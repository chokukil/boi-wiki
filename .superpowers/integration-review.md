# Science external-agent integration review

## Verdict

**FAIL**

Reviewed `e83ef49^..9dbea5c` at `9dbea5c33b4a34d5e565e4569e199c9e677fae35` against `docs/superpowers/specs/2026-08-25-science-verifier-design.md` and the fixed REST contract in `docs/superpowers/plans/2026-08-25-science-verifier-application.md`.

The skill and harness prose correctly says that agents do not own verdicts, inactive material is not Evidence, proposals require separate review, and activation is never automatic. The executable MCP integration does not enforce the same identity, confirmation, request, or export-integrity boundaries. It is not safe to merge with the planned Science REST router in its current form.

## Findings

### Critical — Native MCP release mutations have no authenticated caller mapping; bridge mutations impersonate arbitrary employees

Evidence:

- `boi_wiki_mcp/app/main.py:952-979` exposes `science_release_activate` and `science_release_withdraw` as native FastMCP tools. They accept caller-controlled `employee_id`, check only a Boolean supplied in the same tool call, and call `api_post` without an authenticated caller credential.
- `boi_wiki_mcp/app/main.py:675-692` turns that `employee_id` into a query parameter. With the repository's default dev authentication, that query parameter selects the dev identity; with production authentication it cannot forward the user's bearer/session identity and will fail closed rather than work.
- `boi_wiki_mcp/app/main.py:3555-3570` protects `/mcp` only when optional `MCP_REQUIRE_SERVICE_TOKEN` is enabled, but a shared service token is not an interactive Science Admin identity. No middleware maps the MCP request to a user identity.
- The bridge-specific denial at `boi_wiki_mcp/app/main.py:3775-3781` does not apply to the native `/mcp` tools. The review probe successfully reached the activation adapter as `employee_id='claimed-admin'` with payload `{'user_confirmed': True}`.
- Other bridge mutations remain impersonable: `boi_wiki_mcp/app/main.py:3775,3792-3805,3843-3851` accepts any `employee_id`, adds the shared service token, and forwards interpretation confirmation/proposal creation as that employee. The review probe returned HTTP 200 and forwarded a proposal as `claimed-victim`.
- This violates the agent-integration constraints at `docs/superpowers/plans/2026-08-25-science-verifier-agent-integration.md:18,63-65` and the REST mutation rule at `docs/superpowers/plans/2026-08-25-science-verifier-application.md:237-239`.

Impact:

Once the planned REST routes are merged, a native MCP caller can choose the configured Science Admin employee in dev/default deployments and request release activation or withdrawal. On the bridge, a holder of the shared service token can create user-confirmed records under another employee's identity. Audit actor, same-user interpretation confirmation, separation of duties, and confirmation provenance are therefore not trustworthy.

Required correction:

- Introduce one authenticated-user context for native MCP and bridge calls and forward that identity, not a tool argument.
- Treat the shared service token only as service authentication. Never derive an interactive actor or Science role from caller-supplied `employee_id`.
- Reject activation/withdrawal from every service-token-only surface, including native `/mcp`, until an authenticated caller mapping exists.
- Bind every mutation to the authenticated actor, exact request digest, and idempotency key. A Boolean generated in the same agent call is not sufficient proof of immediate user confirmation.

### Important — Verification and qualification wrappers do not implement the fixed REST request contract

Evidence:

- The fixed REST table requires Claim Packet plus ReleaseSelection for claim verification and confirmed claims plus ReleaseSelection for document verification (`docs/superpowers/plans/2026-08-25-science-verifier-application.md:168-188`). Rule qualification requires rule plus cases, and release validation consumes a release ID.
- The integration plan's own executable example calls `science_verify_claim("claim:x", CLAIM_PACKET, RELEASES)` and asserts `payload["claim_packet"]` (`docs/superpowers/plans/2026-08-25-science-verifier-agent-integration.md:39-48`).
- Implemented `science_verify_claim` sends only `request_id` (`boi_wiki_mcp/app/main.py:815-826`). `science_verify_document` sends raw `document` plus `request_id` (`829-840`). `science_rule_qualify` sends an empty object (`928-937`). `science_release_validate` sends a caller-provided release object instead of the specified release ID (`940-949`). The bridge duplicates these shapes at `3806-3823,3873-3885`.

Impact:

The adapters cannot drive deterministic, release-pinned verification or the planned Admin qualification endpoints. Depending on router validation, they will either return 422 errors or silently omit the inputs that make the result reproducible. They are not thin adapters to the contract they claim to expose.

Required correction:

- Define MCP schemas directly from the fixed REST request models.
- Forward Claim Packet, ReleaseSelection, confirmed claim set, rule/cases, exact release ID/digest, request digest, and idempotency key unchanged.
- Add contract tests that instantiate the actual REST Pydantic request models or run the MCP wrappers against the router, rather than asserting hand-written dictionaries.

### Important — Report export discards the canonical report digest and substitutes format-specific byte hashes

Evidence:

- The REST contract requires both Markdown and PDF to return the same `x-science-report-digest` associated with the immutable report (`docs/superpowers/plans/2026-08-25-science-verifier-application.md:194-201,214-216`). The integration constraint requires packet metadata and digest to remain unchanged (`docs/superpowers/plans/2026-08-25-science-verifier-agent-integration.md:18-21,59-61`).
- `api_get_bytes` reads only content type, drops all Science response metadata including `x-science-report-digest`, and returns a newly calculated byte `sha256` (`boi_wiki_mcp/app/main.py:695-723`). Markdown and PDF necessarily have different byte hashes even when they represent the same report.
- The review probe supplied the same API report digest for two different export bodies. Neither MCP result contained that digest, and the emitted `sha256` values differed.

Impact:

An external agent cannot prove that Markdown, PDF, REST, and MCP refer to the same immutable VerificationReport. A byte hash is useful additional integrity metadata, but replacing the server's report digest breaks the required cross-channel identity and can make valid parity appear unequal.

Required correction:

- Preserve the API's canonical `x-science-report-digest` as `report_digest` unchanged, along with any required release/report identifiers and content disposition.
- Optionally add a separately named `content_sha256`; do not substitute it for `report_digest`.
- Test two different formats with the same report digest and different byte hashes.

### Important — Passing tests and the documented smoke command do not exercise the security or parity contracts

Evidence:

- `tests/test_science_mcp.py:88-109` replaces `api_get_bytes` with a fake that already returns `sha256`, so the test never observes response headers and cannot detect canonical digest loss.
- `tests/test_science_mcp.py:113-156` calls native activation/withdrawal directly and considers arbitrary `employee_id` forwarding plus a Boolean sufficient. It contains no native `/mcp` identity/authorization test.
- Bridge tests cover missing Boolean errors for two calls and denial of activation/withdrawal (`tests/test_science_mcp.py:159-201`), but no successful bridge dispatch test asserts trusted actor derivation, request digest binding, Claim/Release payload preservation, ACL behavior, or report metadata.
- The implementation plan explicitly required `scripts/check_boi_wiki_mcp.py` to be modified and expected all 15 Science tools to appear (`docs/superpowers/plans/2026-08-25-science-verifier-agent-integration.md:28-31,51,67-76`). The file is unchanged in the reviewed commit range. It only requires at least 80 total tools (`scripts/check_boi_wiki_mcp.py:43,915-920`) and its checklist contains no Science tools, so it can pass with the whole Science group missing or broken.
- The Science skill/harness tests mostly assert the presence of phrases. They appropriately lock conservative documentation, but do not prove that the transport enforces those instructions.

Impact:

The focused suite is green while all three defects above remain. The claimed integration verification is therefore materially incomplete and creates false confidence at the exact authority and parity boundaries the design makes release-blocking.

Required correction:

- Add end-to-end MCP-to-REST contract tests for all 15 tools, both native and bridge surfaces.
- Exercise authenticated user, shared-service-token-only, forged employee ID, non-Admin, Science Admin, self-approval, stale confirmation digest, and retry/idempotency cases.
- Update `scripts/check_boi_wiki_mcp.py` to require the exact Science tool set and perform safe bridge/native contract probes.
- Test export headers and cross-format report identity using real response objects.

## Non-findings / positive controls

- The verifier skill preserves the five BoI verdict labels, explicitly limits `CONSISTENT`, requires outcome-changing ambiguity confirmation, and forbids memory/web Citation substitution.
- The curator skill is proposal-only, forbids self-approval and service-token approval, keeps Power User scope narrow, and requires separate human Admin activation.
- The parent skill routes fact checking and curation to the specialized skills without embedding scientific facts or an autonomous BoI Science agent.
- Harness bodies consistently require `science.admin`, separate review, inactive candidate isolation, G0-G7, visible Evidence, false-red protection, and cross-channel parity. No automatic activation instruction was found.
- No Science proposal-review MCP tool was added; review remains Web/REST-only as intended.

## Verification run

- `git diff --check e83ef49^..9dbea5c` — passed.
- `ruff check boi_wiki_mcp/app/main.py scripts/sync_science_harnesses.py tests/test_science_mcp.py tests/test_science_harnesses.py tests/test_science_skills.py` — passed.
- `pytest -s tests/test_science_mcp.py tests/test_science_skills.py tests/test_science_harnesses.py -q` — 26 passed.
- `pytest -s tests/test_boi_wiki_mcp.py -q` — 51 passed, 2 unrelated FastAPI deprecation warnings.
- `python scripts/sync_science_harnesses.py --check` — passed.
- `python scripts/okf_lint.py --root data --strict-links --strict-media` — passed; 332 Markdown documents checked.
- Initial pytest run with capture enabled did not collect tests because pytest's temporary capture file disappeared during cleanup. Re-running the identical targets with `-s` passed; this was environment/capture infrastructure noise, not a product test failure.
- Two read-only executable probes confirmed: (1) native activation forwards a caller-selected employee with no authenticated mapping, while bridge proposal creation forwards a caller-selected employee under the service token; (2) the export adapter drops a shared API report digest and emits unequal format byte hashes.

## Completion boundary

This review did not modify production or test files. Only `.superpowers/integration-review.md` was created. Existing unrelated files were left untouched.
