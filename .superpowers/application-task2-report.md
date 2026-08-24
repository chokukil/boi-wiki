# Application Task 2 Review-Fix Report

Date: 2026-08-25 (Asia/Seoul)

Branch: `codex/science-application`

Implementation commit: `d749af8d888cee4383a0987dab3e57d3456bb4ec`

Reviewed base: `1a28f8bf653db9fb27040fb6a9832af50e48f859`

Foundation enforcement base: `707ddb7ee680326bf006dd5d05582e4d5bc3bc04`

## Scope and trust boundaries

This change fixes every Critical/Important finding in the Task 2 review and all
four follow-up re-reviews, including the final token-boundary report,
while preserving the Task 1 atomic record/audit protocol and the Foundation
Catalog-issued operational capability.

- The LLM produces proposals only. It cannot set `user_confirmed`, decide
  outcome impact, create a verdict, cite Evidence, or supply a locator.
- Explicit confirmation is a separate identity-bound immutable revision.
- Verification still follows only
  `ScienceCatalog.resolve_release_set -> resolve_operational_rule_set ->
  OperationalVerification -> engine`.
- Deterministic record IDs reuse Task 1's immutable record+audit WAL as the
  authoritative idempotency mapping. No side database or weaker write path was
  added.
- Operation bindings are mandatory for every interpretation and report. There
  is no legacy/default path capable of producing, storing, reading, or exporting
  an authoritative verdict/report without the typed binding.

## Re-review closure

### C1: mandatory authority and immutable dependency chain

- `InterpretationRecord.operation_binding` and
  `VerificationReport.operation_binding` are required closed fields.
- Proposal records forbid confirmed claims and revisions. Confirmation records
  require one exact typed revision whose actor, proposal ID, and sorted claim IDs
  equal the operation binding.
- Both service verification entry points revalidate the stored confirmation,
  safely load its immutable proposal dependency, reconstruct the only permitted
  confirmed Claim Packets, and pause before Catalog/Engine access on any stale,
  missing, or mismatched link.
- `ScienceRuntimeStore` independently revalidates model instances through their
  canonical JSON form, binds the operation actor to the trusted `AuthIdentity`,
  and validates proposal/confirmation/report dependencies on save, load, and WAL
  recovery. A missing interpretation therefore cannot be stored or exported as
  a report even if its own digest is recomputed.
- Report validators unconditionally recompute report digest, request/document/
  claim/release binding, exact interpretation ID, confirmed claims, verdict
  coverage, Claim Packet digests, and release maps.

### I1: closed Evidence locator

- Evidence locators now use a closed `EvidenceLocator` schema for reviewed
  page, section, equation, source URL, hash, and transcription metadata.
- All non-URL locator fields pass the shared recursive non-secret validator.
  Locator URLs require HTTPS and reject userinfo, credential query/fragment
  names, token-shaped values, and endpoint/credential scalar patterns.
- Service and store failures return closed diagnostics; rejected locator secret
  values and credential URLs are never echoed or written to immutable storage.

### Final I1: one stable-source URL policy

- `validate_credential_free_https_url()` is now the single policy used by all
  three Evidence locator URL fields, the persisted Source link, and the service
  Source lookup before report construction.
- The exact persisted string must be its checked canonical ASCII serialization.
  Raw C0/space characters, NFKC-changing input, malformed percent syntax,
  noncanonical scheme/hostname/port, percent-encoded authority, userinfo, and
  every fragment fail closed before parsing can discard or reinterpret bytes.
- Path normalization runs before every strict percent-decode iteration. A
  shared boundary tokenizer scans exact markers and reviewed multi-token
  sequences anywhere across path segments and canonical hostname labels. It
  recognizes all 22 generic/vendor families plus `X-Amz`/`X-Goog`/`X-Ms`
  credential/signature and SharedAccessSignature forms without treating
  `signals`, `sigma`, or `authors` as `sig`/`auth` markers.
- Stable source queries are denied by default. The only current reviewed
  exception is `download=true|1`, which preserves the checked-in BIPM immutable
  PDF source links without admitting a signed or tracking URL.
- Adversarial tests cover Source and `resource_url`/`requested_url`/
  `resolved_url` values through service, real Store save, direct private-file
  load, and WAL recovery, including nested non-URL locator secrets. Every
  returned failure is sanitized and no rejected report is published. The
  `closed_science_validation_error()` factory is called only after the raw
  validation exception scope exits, so the future Task 3 REST adapter can raise
  a closed error with neither a cause nor implicit secret-bearing context.

## RED evidence

The review fixes were implemented in adversarial TDD slices.

1. The first semantic test update failed because `concept_role` was forbidden by
   the old LLM schema:

   ```text
   ScienceInterpretationPayload claims.0.candidate_meanings.*.concept_role
   Extra inputs are not permitted
   1 failed, 6 passed
   ```

2. After the typed role schema, the service RED failed because
   `interpret_document()` did not accept the trusted idempotency key. Subsequent
   semantic cases demonstrated that false `changes_outcome`, missing
   subject/relation/object bindings, unknown refs, alias mismatch, and partial
   relation spans could not yet use the required pause/confirmation flow.

3. The I1 endpoint-shaped model test initially failed with `DID NOT RAISE` for
   `https://internal-llm.test:1236/v1`. Additional RED cases covered a
   scheme-less host/port, userinfo, token-shaped model IDs, nested/list secret
   values, typed revision extras, and an endpoint-shaped identity.

4. The transport test showed the need for a sanitized diagnostic contract. It
   now asserts an `http_status_503` code, generic outer message, and
   `__cause__ is None`; neither the private endpoint nor response token appears.

5. The first real-store post-record/pre-audit retry test failed because a normal
   record load returned the published record without reconciling the pending
   audit. The service preflight now calls Task 1 recovery before idempotency
   lookup; the retry records the original audit exactly once without a second
   LLM call.

6. The re-review RED probe saved a confirmed record with
   `operation_binding=None` and no revision, and separately saved an unbound
   forged report. The initial adversarial test failed with `DID NOT RAISE`.
   Follow-up RED cases covered stale model copies, a missing interpretation
   dependency, and report load from an orphaned immutable file.

7. The Evidence locator RED probe supplied an `api_key` plus an HTTPS URL with
   userinfo. Before the fix, the closed service/store assertions failed because
   locator metadata was copied outside the recursive validator. Tests now also
   recompute the outer report digest to prove the inner locator boundary is
   independently authoritative.

8. The final review's path/signature cases produced 40 RED failures: literal,
   percent-encoded, and double-encoded `api_key` paths, bearer path segments,
   `X-Amz-Signature`, `signature`, `sig`, `X-Amz-Credential`, fragments, and
   Source URLs were persisted. The same matrix is now GREEN across all URL
   fields and storage/recovery paths.

9. The canonical-boundary re-review matrix initially produced 68 RED failures
   across service, direct Store save, private load, and WAL recovery. It covered
   NFKC separators/percent signs, malformed percent syntax, vendor signature
   families, encoded/double-encoded authority userinfo, and raw whitespace/C0
   input. Three compact generic credential prefixes then produced 12 additional
   service RED failures, and `/api/key-hidden` produced four more, proving a
   split-prefix path bypass before the final bounded segment-prefix scan.

10. The token-boundary slice first failed collection because the closed error
    factory did not exist. After adding only that factory and Pydantic input
    hiding, 44 benign-prefix path/hostname credentials were still accepted and
    the three required scientific paths were falsely denied: `47 failed, 1
    passed`. The final matrix expands the 22 compact families with every
    reviewed separated vendor credential/signature sequence and exercises the
    same URLs through service, Store save/load, and WAL recovery.

## GREEN behavior

### C1: proposal-only interpretation and explicit confirmation

- `CandidateMeaning` has an exact `subject | relation | object` role.
- The server checks the exact pinned binding ID, binding digest, ontology release
  ID, canonical concept, reviewed alias, unique anchored occurrence, and complete
  subject-relation-object order.
- Trusted validated refs and untrusted proposed refs are separate fields.
  Unknown/mismatched proposed refs are preserved for correction but never appear
  in the validated ontology-ref set or report trust path.
- LLM `changes_outcome` and its free-form reason are ignored for authority and
  persistence. Server impact is conservatively `unresolved`.
- Zero refs, unknown refs, missing subject/object/relation bindings, concept or
  alias mismatch, duplicate/partial span, and false outcome-impact claims create
  a typed paused proposal. Confirmation and report creation fail before Engine
  or report storage.
- `confirm_interpretation()` injects the trusted actor, creates a closed
  `claim_confirmed` revision, clears ambiguity only for server-valid selected
  claims, and creates a new immutable record. `verify_claim()` accepts only a
  stored explicitly confirmed interpretation/claim identity.

### I1: non-secret provenance and sanitized diagnostics

- `safety.py` is the shared recursive persistence validator used by Task 1
  storage and Task 2 records.
- Model IDs use a reviewed grammar that permits provider/model names such as
  `qwen/qwen3.8-27b` while rejecting URLs, scheme-less host/port endpoints,
  userinfo, bearer/token patterns, and credential aliases.
- Interpretation/report models recursively inspect every non-source field.
  Scientific source-span and reviewed Knowledge prose are intentional content
  fields. Source and locator URLs use the stricter credential-free HTTPS
  validator, while all remaining closed locator fields are recursively scanned.
- User revisions and decision impacts are closed typed models. LLM reason prose
  is never persisted.
- HTTP status, timeout, transport, malformed envelope/JSON, forbidden output,
  and schema errors expose only closed diagnostic codes and sanitized messages.
  Raw `httpx` errors are never retained as exception causes.
- All `ScienceModel` validation strings hide input values. The public validation
  factory takes no raw exception and is invoked after the `except` scope; the
  real adapter-pattern test proves the raised closed error has no cause, no
  context, and no secret-bearing text.

### I2: immutable, self-verifying grounding snapshot

- `GroundedAnnotation`, `EvidenceLink`, and `SourceLookupIdentity` are closed
  schemas.
- Each annotation stores the exact pinned Knowledge digest. Each Evidence link
  stores the exact Evidence and Source digests, `original_text_hash`, equal
  quote hash, server-injected URL/locator, BoI ID, versioned relative source path,
  visibility, classification, ACL policy, and an exact lookup digest.
- Evidence quote hash is checked against the reviewed original text before save.
  Source lookup and report digests are recomputed by model validators.
- Reports include the exact confirmed Claim Packets so Task 3 Markdown/PDF can
  render spans and ontology refs from the immutable report alone.
- Later in-memory Catalog changes cannot alter stored report bytes. Canonical
  tampering of Knowledge/Evidence/Source or ACL snapshot fields invalidates the
  immutable report digest.

### I3: exactly-once operations on Task 1 storage

- Interpretation, confirmation, and report creation require a trusted
  idempotency key. Only its SHA-256 digest is persisted.
- Record identity is deterministic from that digest. A closed operation binding
  stores operation, actor, canonical request/document/claim/release/prompt
  digests. Prompt identity includes the exact system-prompt digest and pinned
  Dictionary/Ontology/model settings.
- Exact retry returns the original record before another LLM/Engine/Catalog
  operation. Actor, request, document, claim, release, or prompt reuse mismatch
  raises `ScienceIdempotencyConflict`.
- Concurrent identical operations may race in computation, but Task 1 immutable
  publication chooses one canonical record and emits one authoritative audit.
- Post-record/pre-audit retries run Task 1 recovery, return the published record,
  append the original audit once, and remove the journal. Tests cover this for
  both interpretation and report creation.

## Verification evidence

Focused Task 2 review-fix suite:

```text
umask 077 && TMPDIR=/tmp/boi-sci-pytest /tmp/boi-sci-uv/bin/pytest -q \
  tests/test_science_interpretation.py --tb=short
573 passed in 16.06s
```

Fresh combined Task 2 + Task 1 + Foundation regression:

```text
umask 077 && TMPDIR=/tmp/boi-sci-pytest /tmp/boi-sci-uv/bin/pytest -q \
  tests/test_science_interpretation.py \
  tests/test_science_authorization.py tests/test_science_storage.py \
  tests/test_science_catalog.py tests/test_science_engine.py \
  tests/test_science_models.py tests/test_science_profile.py \
  tests/test_science_source_ledger.py --tb=short
984 passed in 20.89s
```

Static verification:

```text
/tmp/boi-sci-uv/bin/ruff check --select E,F,I \
  boi_api/app/science/models.py boi_api/app/science/safety.py \
  boi_api/app/science/service.py boi_api/app/science/storage.py \
  tests/test_science_interpretation.py tests/test_science_storage.py \
  tests/test_science_models.py
All checks passed!

ruff format --check <same files>
7 files already formatted

python -m compileall -q boi_api/app/science tests/test_science_interpretation.py \
  tests/test_science_storage.py tests/test_science_models.py
git diff --check
```

The Ruff result uses Ruff 0.16.4 and explicitly states the repository's clean
contract for syntax, undefined names, line length, and import ordering
(`E,F,I`). It does not claim that the repository has adopted every optional
Ruff 0.16 rule. Compile and diff checks completed with no output/errors.

## Self-review

- No compatibility adapter or direct `ResolvedRuleSet` verification path was
  introduced.
- No request-body actor/role authority was added; application mutations receive
  the trusted `AuthIdentity`, and proposal governance retains Task 1 role
  resolution.
- No endpoint, API key, raw idempotency key, LLM reason, LLM Evidence, or LLM
  locator is stored.
- The stable-source policy rejects only exact reviewed boundary tokens and
  multi-token sequences, including those appearing after benign path/hostname
  tokens or split across segments/labels. It intentionally permits the ordinary
  scientific tokens `signals`, `sigma`, and `authors`.
- Proposed invalid ontology refs cannot be confirmed and cannot enter a verdict,
  annotation, Evidence link, or report.
- Task 1 no-follow IO, atomic publication, audit WAL, recovery, collision checks,
  and authorization code were not weakened. Its secret validator was moved to a
  shared module without changing the public exception import.
- The root agent's intentional Task 3 REST-contract plan update was preserved
  verbatim in the implementation commit; this task did not implement Task 3.
- No merge, cherry-pick, push, release activation, or external state change was
  performed.
