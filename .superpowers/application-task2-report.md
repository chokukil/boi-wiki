# Application Task 2 Review-Fix Report

Date: 2026-08-25 (Asia/Seoul)

Branch: `codex/science-application`

Implementation commit: `3c7ec08a8dced6306742bf4341f2c7531e74ee3b`

Reviewed base: `1a28f8bf653db9fb27040fb6a9832af50e48f859`

Foundation enforcement base: `707ddb7ee680326bf006dd5d05582e4d5bc3bc04`

## Scope and trust boundaries

This change fixes every Critical/Important finding in
`.superpowers/application-task2-review.md` while preserving the Task 1 atomic
record/audit protocol and the Foundation Catalog-issued operational capability.

- The LLM produces proposals only. It cannot set `user_confirmed`, decide
  outcome impact, create a verdict, cite Evidence, or supply a locator.
- Explicit confirmation is a separate identity-bound immutable revision.
- Verification still follows only
  `ScienceCatalog.resolve_release_set -> resolve_operational_rule_set ->
  OperationalVerification -> engine`.
- Deterministic record IDs reuse Task 1's immutable record+audit WAL as the
  authoritative idempotency mapping. No side database or weaker write path was
  added.
- Existing Task 1 legacy fixtures remain readable through an optional operation
  binding; every Task 2 service-created record requires and validates the typed
  binding.

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
  Source span text, reviewed Knowledge text, approved source URL, and reviewed
  locator are the only intentional content exemptions; credential-bearing
  source URLs and URL query/fragment credentials still fail closed.
- User revisions and decision impacts are closed typed models. LLM reason prose
  is never persisted.
- HTTP status, timeout, transport, malformed envelope/JSON, forbidden output,
  and schema errors expose only closed diagnostic codes and sanitized messages.
  Raw `httpx` errors are never retained as exception causes.

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
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest -q -s \
  tests/test_science_interpretation.py --tb=short
56 passed in 0.62s
```

Fresh combined Task 2 + Task 1 + Foundation regression:

```text
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest -q -s \
  tests/test_science_interpretation.py \
  tests/test_science_authorization.py tests/test_science_storage.py \
  tests/test_science_catalog.py tests/test_science_engine.py \
  tests/test_science_models.py tests/test_science_profile.py \
  tests/test_science_source_ledger.py --tb=short
467 passed in 5.85s
```

Static verification:

```text
ruff check boi_api/app/science/anchors.py boi_api/app/science/llm.py \
  boi_api/app/science/service.py boi_api/app/science/models.py \
  boi_api/app/science/catalog.py boi_api/app/science/storage.py \
  boi_api/app/science/safety.py tests/test_science_interpretation.py
All checks passed!

ruff format --check <same files>
8 files already formatted

python -m compileall -q boi_api/app/science tests/test_science_interpretation.py
git diff --check
```

Both commands completed with no output/errors after the reported Ruff results.

## Self-review

- No compatibility adapter or direct `ResolvedRuleSet` verification path was
  introduced.
- No request-body actor/role authority was added; every mutation still receives
  the trusted `AuthIdentity` object and Task 1 resolves authorization.
- No endpoint, API key, raw idempotency key, LLM reason, LLM Evidence, or LLM
  locator is stored.
- Proposed invalid ontology refs cannot be confirmed and cannot enter a verdict,
  annotation, Evidence link, or report.
- Task 1 no-follow IO, atomic publication, audit WAL, recovery, collision checks,
  and authorization code were not weakened. Its secret validator was moved to a
  shared module without changing the public exception import.
- No merge, cherry-pick, push, release activation, or external state change was
  performed.
