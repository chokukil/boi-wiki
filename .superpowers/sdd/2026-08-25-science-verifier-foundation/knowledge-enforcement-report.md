# Science knowledge enforcement report

Date: 2026-08-25
Branch: `codex/science-verifier`
Fix baseline: `96e19ebab18452d05142f38c9094a398ce36a288`

## Outcome

All four Critical findings in `knowledge-enforcement-review.md` are closed at the production verification boundary. No real Science object was approved or activated.

### C1 — operational attestation boundary

- `QualificationRuleSet` is a distinct serializable qualification result.
- The public Engine accepts only an opaque `OperationalVerification` issued by `ScienceCatalog.resolve_operational_rule_set()` after active governance resolution.
- The capability is immutable through its public API and rejects direct construction, `model_copy`, ordinary copying, deep copying, and pickle serialization.
- Its sealed attestation covers the exact Release-set digest, Release IDs and statuses, Release content hashes, component-digest manifests, approval/activation snapshot, and Rule-set digest.
- Directly constructed `ResolvedReleaseSet` / `ResolvedRuleSet`, candidate qualification output, a qualification `model_copy(update={"status": "active"})`, and an unsealed `object.__new__` instance are rejected by the public Engine.

The underscore-prefixed issue/open functions are an internal in-process trust boundary used only by Catalog and Engine. They are not a cryptographic sandbox against arbitrary code already executing inside the server process.

### C2 — executable Evidence scope

- `EvidenceUse` now binds only exact `evidence_ref`, `claim_family`, and `purpose`.
- Every embedded Evidence `claim_scope.required_conditions` entry is a validated `ConditionConstraint`; free-form strings are invalid.
- Catalog canonicalizes each Evidence constraint and proves that the exact constraint is present in the Rule's executable `required_conditions` or `validity_conditions` before issuing either qualification or operational Rules.
- Closed scalar membership (`operator: in`) was added for product-grade scope, including uniqueness, one-scalar-kind, and finite-number checks.
- Condition evaluation carries the closed membership list in its audit record.
- KCL requires consistent current references, `circuit_model = lumped_matter`, and `node_charge_accumulation = none`.
- The AZ 125nXT figure Observation requires product family, one of the two plotted grades, revision `01/24`, the common 600–2300 rpm plotted-marker range, and plotted-marker-only use.
- End-to-end Catalog-to-Engine tests show missing KCL model/no-accumulation and Figure product/revision/range inputs yield `INSUFFICIENT_INFORMATION`, never a red verdict.
- Spin-time Evidence still forbids both RPM/spin-speed direction families and is scoped only to AZ 125nXT revision `01/24`.

All 45 Evidence documents and `evidence-claim-scope-v0.1.yaml` were updated. The YAML remains a test-checked summary; Catalog and Engine read only the hash-bound scope embedded in each Evidence object.

### C3 — complete active governance gate

An operational Release now requires trusted Admin approval of:

- the Release itself;
- every pinned Source, Evidence, Knowledge, Rule, Ontology Binding, Qualification Matrix, and Pack;
- Source retrieval verification and Evidence decision eligibility where applicable; and
- a distinct trusted Admin Release activation event.

Every object must be `approved` and `active_release_eligible`. Active Evidence must pin its exact Source. Candidate Releases may retain pending drafts and produce only `QualificationRuleSet`; they cannot obtain an operational capability.

### C4 — actor and time closure

- A human actor is exactly `{type: human, user_id: ...}`.
- An agent actor is exactly `{type: agent, agent_id: ...}`.
- Dual identities, extra identity keys, missing identities, Agent reviewers, and canonical typed self-approval are rejected.
- Authorization comes only from the injected trusted role resolver resolving the sanitized human identity to `science.admin`; caller-written role labels are ignored.
- Operational resolution requires an injected timezone-aware trusted clock. Default skew is 30 seconds and the configurable maximum is one minute.
- Approval and activation cannot be in the future beyond skew, cannot precede authorship/retrieval/curation, and approval cannot occur after Release activation.

## TDD evidence

The new enforcement tests were observed failing before implementation:

- public operational boundary: direct Engine inputs and unsealed objects;
- typed membership/profile validation and prose-condition rejection;
- omitted draft Knowledge, Rule, Ontology Binding, Qualification Matrix, and Pack;
- draft/unactivated Release;
- dual author/reviewer identities and future/late approval or activation; and
- KCL/Figure missing-condition end-to-end cases.

The final focused and regression suite is recorded below.

## Data disposition

- All repository Source/Evidence objects remain `draft` / `pending_review` and release-blocked.
- No Knowledge, Rule, Pack, Ontology Binding, Qualification Matrix, or Release was approved or activated in repository data.
- Inaccessible AIP evidence remains inactive with an empty allowed-claim list.
- No Source URL, DOI, locator, checksum, original span, translation, access limitation, or factual statement was broadened.
- The unrelated untracked `.superpowers/application-architecture-scout.md` was not edited or staged.

## Final verification

Expanded Foundation, profile, Catalog, Engine, source-ledger, and OKF suite:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_models.py tests/test_science_profile.py \
  tests/test_science_catalog.py tests/test_science_engine.py \
  tests/test_science_source_ledger.py tests/test_okf_lint.py -q
```

Output:

```text
........................................................................ [ 20%]
........................................................................ [ 41%]
........................................................................ [ 62%]
........................................................................ [ 83%]
..........................................................               [100%]
346 passed in 9.21s
```

Strict OKF lint:

```bash
/tmp/boi-wiki-sci-task4-venv/bin/python scripts/okf_lint.py \
  --root data --strict-links --strict-media
```

Output:

```text
OKF lint checked 277 markdown docs; found 731 markdown graph links and 25 markdown image links.
OKF lint passed
```

Additional checks:

```bash
/tmp/boi-wiki-sci-task4-venv/bin/python -m compileall -q \
  boi_api/app/science tests/test_science_models.py tests/test_science_profile.py \
  tests/test_science_catalog.py tests/test_science_engine.py \
  tests/test_science_source_ledger.py
git diff --check
```

All additional checks exited `0` with no findings. A repository-data scan also confirmed there is no approved status, approved review, active-release eligibility, eligible Evidence, or activation record under `data/boi/public/science`.

## Self-review

- Replayed every exploit described in the review as a regression test.
- Confirmed public verification cannot accept a caller-supplied status, Release set, or Rule set.
- Confirmed the attestation contains governance and content identities, not merely a status flag.
- Confirmed Evidence conditions are typed at rest and executable in Rules, with exact Catalog comparison.
- Confirmed every pinned component kind and Release activation are included in the active gate.
- Confirmed actor comparison is typed and closed, and all operational time checks use the injected clock.
- Confirmed candidate qualification remains possible without weakening the operational path.
- Confirmed real repository data remains pending/blocked and no active Science truth was manufactured.
