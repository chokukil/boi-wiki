# Knowledge Tasks 2 and 3 Scientific-Trust Fix Report

Date: 2026-08-25

Branch: `codex/science-verifier`

Authority state: candidate-only; no authorized review, Release, activation, or operational capability was added

## Scope

This change addresses every Important finding in the independent Knowledge Task 3 review and the inherited Knowledge Task 2 review. It hardens 44 candidate Rules and 440 candidate qualification cases while preserving the closed authority boundary. The result is still an agent-authored draft requiring an authorized Admin review; this report does not assert scientific approval or Release eligibility.

An independent re-review of the first hardening commit `4124692` still failed on synthetic one-sentence fixtures, incomplete unit operands, remaining string self-attestation, and caller-created observation authority. The corpus, schema, and operational-boundary work below is the second corrective pass for those findings; the earlier passing test count was not treated as acceptance evidence.

## Finding closure

### Task 3

1. **Generic empirical contradiction suppression**
   - Removed `claim_specificity == equipment_or_numeric` from all 32 domain Rules.
   - Added a unique, Rule-local empirical proposition to each Rule.
   - Moved empirical-observation handling after deterministic evaluation, so a deterministic contradiction remains `CONTRADICTS` even when the empirical trigger is present.
   - Caller-created `QualifiedObservation(verified=true)` values are now explicitly untrusted proposals and can never authorize a result. The public Engine accepts only an opaque operational observation type, but no issuer exists until a released observation schema and authorized Admin review event can be bound. Consequently empirical support is deliberately impossible in this candidate and remains `QUALIFIED_OBSERVATION_REQUIRED`.

2. **Ignored unit values**
   - Added typed `quantity_equivalence_constraints` to all 32 domain Rules and all 12 Foundation Rules.
   - Each unit case now carries target and reference operands for one named scientific role. The Rule evaluator, not test-only code, performs the registered conversion and exact magnitude comparison.
   - Magnitude changes return `QUANTITY_EQUIVALENCE_MISMATCH`. Same-dimension conversions absent from the reviewed registry return `UNREGISTERED_QUANTITY_EQUIVALENCE` rather than escaping as an evaluator exception.

3. **Templated false-red shortcuts**
   - Replaced generated `outside_*` labels and the phrase `outside this rule's required scope` with nearby scientific claims using real alternative conditions, regimes, stages, material states, or comparison subjects.
   - Tests require the benign case to retain the same subject and object while differing in a consumed condition, stage, or material state. Each Rule now has one immutable UTF-8 qualification document whose full byte SHA-256, exact character offsets, and nonempty prefix/suffix anchors are verified by the Catalog.

4. **Self-attested applicability booleans**
   - R-MAT-004 now consumes anchored activation energy, before/after temperature, and before/after diffusivity values and enforces their cross-field direction.
   - R-SCD-003 now consumes anchored electron/hole concentration, electron/hole mobility, and conductivity values and enforces `sigma = q(n mu_n + p mu_p)` within a declared tolerance.
   - Removed `material_parameters_known` and `carrier_state_parameters_known` as authoritative inputs.

5. **Four inexact `exact: true` PDF records**
   - `physics/viscosity-flow`: corrected to PDF page index 11 / printed page 12.
   - `common/model-validity`: restored the source qualifier `validated M&S`.
   - `chemistry/reaction-equilibrium`: preserved the rendered source text `K = is` instead of silently normalizing it.
   - `physics/force-momentum`: preserved the source's mid-sentence endpoint ending in `as` instead of adding a period.
   - Recomputed exact-text hashes, synchronized the scope manifest, and independently checked page text against the checksum-bound local PDFs with PyMuPDF.

6. **Claims exceeding pinned Evidence**
   - R-CHE-003 is limited to vapor pressure as molecular escaping tendency and no longer decides an open-process evaporation rate.
   - R-SPN-002 is limited to maintaining a validation-domain record; the inaccessible Emslie evidence remains explicitly excluded and inactive.
   - R-SPN-004 is limited to the exact MicroChemicals drying-limited qualitative statement. The vendor chart record now authorizes only its pinned axis/series labels and no inferred direction, range, or recipe.
   - R-SCD-003 and the diffusion Rule Evidence scopes were synchronized to the typed equation/cross-field premises and no longer use interpreter booleans as scope keys.

7. **Association/correlation collapse**
   - Added a distinct `sci:concept:association` binding.
   - Removed `association` and `연관성` from correlation aliases and added mutual `must_not_collapse` constraints.
   - Qualification checks the resolved Foundation-plus-domain binding graph, not only newly added domain bindings.

### Inherited Task 2

1. **Synthetic/weak Foundation cases**
   - Replaced all 120 label spans and non-digest placeholders with complete scientific sentences in 12 immutable Rule documents, exact anchors, and full-document SHA-256 byte digests.
   - Every empirical case now evaluates its own matrix Rule. Every ambiguity has two different normalized interpretations with different outcomes. Paraphrases normalize to the same claim.
   - False-red cases use real condition or validity differences rather than concept mismatch.

2. **Foundation Evidence overreach**
   - R-COM-003 is limited to Celsius/Kelvin interval magnitude.
   - R-COM-004 is limited to the measured-value-plus-uncertainty expression.
   - R-COM-005 is limited to the measurement-uncertainty definition.
   - R-COM-007 is limited to the reproducibility-condition definition.
   - R-COM-008 and R-COM-011 are limited to validation-domain record maintenance/content.
   - R-COM-009 is limited to material-particle mass invariance; the unsupported open-system conclusion was removed.

3. **Foundation self-attestation**
   - Removed boolean `*_identified`, `*_documented`, and `*_known` applicability inputs.
   - Replaced them with the narrow values or record semantics the cited span supports. No Foundation Rule condition uses a boolean as scientific authority.

4. **General-capability overclaim and association collapse**
   - The Foundation Pack now declares `executable_coverage: narrow_reviewed_examples` and explicitly records that R-COM-001 covers only sample length and R-COM-002 only equality between two length terms.
   - Association is modeled separately from correlation as described above.

## Adversarial qualification evidence

- The immutable corpus contains 44 documents, 44 matrices, 440 cases, 44 ambiguity alternatives, and 484 anchored Claim packets. All 484 spans re-anchor against the declared full-document byte digest with nonempty context anchors.
- 32/32 domain clear contradictions remain violations when their Rule-local empirical trigger is injected.
- 12/12 Foundation clear contradictions remain violations under their Rule-local empirical trigger.
- 44/44 Rules consume their unit case's target/reference operands; arbitrary same-dimension magnitude mutations fail closed.
- Catalog loading rejects a unit case when either structured operand is absent or when the exact source span does not explicitly contain both numeric-unit operands.
- At runtime, a second reviewed-unit quantity explicitly present in a source span but omitted from the normalized operands forces `INSUFFICIENT_INFORMATION` with `UNGROUNDED_REVIEWED_QUANTITY_MENTION`.
- Unregistered same-dimension conversion is explicitly rejected without an unhandled exception.
- R-MAT-004 rejects a before/after temperature mutation inconsistent with the typed Arrhenius direction.
- R-SCD-003 rejects a conductivity mutation inconsistent with the carrier equation.
- 32/32 domain and 12/12 Foundation false-red cases remain non-violations while preserving the same subject/object family.
- Raw `verified=true`, released-looking Evidence IDs, and caller-constructed observation proposals cannot cross the operational boundary or produce empirical `SUPPORTS`.
- All four corrected PDF spans are verified at their declared page and exact UTF-8 text hash.

## Candidate-only governance evidence

- All seven Packs remain `draft`, `pending_review`, and `blocked_pending_authorized_admin_review`.
- `authorized_review_events` remains empty.
- All qualification matrices retain empty `release_refs`.
- No Release document, activation pointer, review event, or issued observation capability was added. The opaque observation type has no issuer while the required released observation/review schemas do not exist.
- Candidate resolution returns `QualificationRuleSet`; the operational resolver and public Engine still reject release-candidate authority.

## Verification

```text
/home/chokukil/invariant/.venv/bin/python -m pytest -q -s \
  tests/test_science_qualification_fixtures.py \
  tests/test_science_foundation_pack.py tests/test_science_domain_packs.py \
  tests/test_science_engine.py tests/test_science_source_ledger.py \
  tests/test_science_profile.py tests/test_science_catalog.py \
  tests/test_science_models.py tests/test_okf_lint.py
398 passed (215 focused corpus/Rule/Engine tests, 75 Catalog tests, and 108 Source/Profile/Model/OKF tests)

/home/chokukil/invariant/.venv/bin/python scripts/okf_lint.py \
  --root data --strict-links --strict-media
OKF lint checked 470 markdown docs; found 731 markdown graph links and 25 markdown image links.
OKF lint passed

/tmp/boi-sci-uv/bin/ruff check --select I,F,B \
  boi_api/app/science/catalog.py boi_api/app/science/engine.py \
  boi_api/app/science/operational.py boi_api/app/science/rules.py \
  boi_api/app/science/units.py scripts/build_science_qualification_fixtures.py \
  tests/test_science_qualification_fixtures.py \
  tests/test_science_foundation_pack.py tests/test_science_domain_packs.py \
  tests/test_science_engine.py tests/test_science_source_ledger.py
All checks passed!

/home/chokukil/invariant/.venv/bin/python -m compileall -q \
  boi_api/app/science tests/test_science_foundation_pack.py \
  tests/test_science_domain_packs.py tests/test_science_engine.py \
  tests/test_science_source_ledger.py tests/test_science_profile.py \
  tests/test_science_catalog.py tests/test_science_models.py tests/test_okf_lint.py
PASS (exit 0)

git diff --check
PASS (exit 0)

Corpus generator idempotence:
44 matrices plus 44 fixture documents had identical content hashes before and after regeneration.
```

## Remaining authority boundary

These changes improve candidate qualification evidence only. They do not constitute authorized human scientific review. An Admin must independently inspect the Rules, Knowledge, exact Evidence spans, and case semantics before any later Release can be considered. No active Release was created by this work. In particular, empirical observations cannot produce `SUPPORTS` until a future released observation object, its content digest, the applicable Rule and Evidence, and an authorized Admin approval event can be sealed into a Catalog-issued operational capability.
