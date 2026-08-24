# Knowledge Task 2 Report — General Science Foundation

## Scope delivered

- Pack: `sci-pack:science-foundation/0.1.0`
- Knowledge: `SCI-COM-001..012` / `sci:common:001..012`
- Rules: `R-COM-001..012` / `sci-rule:common:001..012`
- Interpretation-only ontology bindings: 12
- Qualification matrices: `Q-COM-001..012`
- Public qualification cases: 120, exactly ten required case kinds per Rule

Task 2 does not create a Science Release, approve an object, or activate operational verification.

## Trust and governance disposition

Every new Knowledge, Rule, Ontology Binding, Qualification Matrix, and Pack object records:

- `author: {type: agent, agent_id: codex}`
- `status: draft`
- `review.review_status: pending_review`
- no authorized review event
- `release_eligibility: blocked_pending_authorized_admin_review`

The Knowledge assurance basis remains `hypothesis` because these are AI-authored drafts. Matrix `release_refs` are empty rather than pointing to a nonexistent or falsely approved Release. Candidate qualification builds a transient `release_candidate` boundary in the test and resolves only `QualificationRuleSet`. The public Engine rejects that type, and Catalog refuses to issue `OperationalVerification` for the candidate.

## Evidence-scope discipline

Rules use only the exact `claim_family` and `purpose` embedded in the existing Evidence objects. Catalog resolution checks every `EvidenceUse` before returning the candidate qualification set.

| Rules | Evidence |
|---|---|
| R-COM-001, 002 | `sci-evidence:common:quantity-unit-dimension` |
| R-COM-003 | `sci-evidence:common:celsius-kelvin` |
| R-COM-004 | `sci-evidence:common:measurand-result` |
| R-COM-005 | `sci-evidence:common:uncertainty-error` |
| R-COM-006 | `sci-evidence:common:accuracy-precision` |
| R-COM-007 | `sci-evidence:common:repeatability-reproducibility` |
| R-COM-008, 011 | `sci-evidence:common:model-validity` |
| R-COM-009 | `sci-evidence:common:system-balance` |
| R-COM-010 | `sci-evidence:common:steady-state`, `sci-evidence:common:equilibrium` |
| R-COM-012 | `sci-evidence:common:correlation-causation` |

Evidence limitations are repeated in the related Knowledge drafts where an Evidence span is narrower than the drafted synthesis. No draft is eligible for active use before authorized Admin review.

## Deterministic qualification coverage

Each matrix contains one genuine case for:

1. clear violation
2. in-scope consistency
3. missing required condition
4. outside validity domain
5. empirical verification required
6. negation
7. registered-unit variation
8. decision-changing ambiguity
9. paraphrase normalized to the same claim
10. false-red prevention

The 120-case test obtains typed Rules only from Catalog's candidate qualification resolver. Rule evaluation is deterministic and does not call the operational Engine. Ambiguity cases prove that two candidate interpretations would change the verdict and therefore stop at `ambiguity_gate`. Unit cases exercise the locked conversion registry. Empirical cases route to R-COM-008 and stop without a qualification observation. Synthetic observation records used by positive R-COM-008 qualification cases are explicitly marked `fixture_only`; they are test inputs, not Evidence or approval records.

## TDD record

RED was observed before the Task 2 documents existed:

```text
4 failed
ScienceCatalogError: unknown science pack: sci-pack:science-foundation/0.1.0
ScienceCatalogError: unknown science rule: sci-rule:common:001
```

The first candidate-resolution run then exposed a real serialization defect: non-directional typed Rules were invalid after a default-filled JSON round trip. The minimal fix uses `exclude_unset=True` when Catalog converts the already validated resolved rule set into `QualificationRuleSet`. The Foundation test is the regression guard.

## Verification

Fresh final run after the last implementation and test edit:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_foundation_pack.py \
  tests/test_science_models.py tests/test_science_profile.py \
  tests/test_science_catalog.py tests/test_science_engine.py \
  tests/test_science_source_ledger.py tests/test_okf_lint.py -q
```

Result: `351 passed in 13.74s`.

```bash
/tmp/boi-wiki-sci-task4-venv/bin/python scripts/okf_lint.py \
  --root data --strict-links --strict-media
```

Result: `OKF lint passed` after checking 328 Markdown documents, 731 graph links, and 25 image links.

`compileall`, `git diff --check`, the 120-case count, the 12/12/12 Binding/Knowledge/Rule counts, and the no-approval/no-activation scan all exited zero.

## Self-review

- No human author, review, approval, activation, or eligible-release state was invented.
- Ontology bindings declare `interpretation_only: true` and contain no executable outcome direction.
- R-COM-011 checks the required input/response, held variables, stage, state, temporal basis, range, regime transition, and Evidence basis but does not choose an outcome direction.
- Candidate qualification and operational evaluation remain different types and authority paths.
- Existing Source and Evidence documents were not edited in Task 2.
- The unrelated untracked `.superpowers/application-architecture-scout.md` is outside this task and is not staged.

## Commit

Implementation commit: `50e16c34e5841e115f7c01166c65d29770aa3c74`.

This report is committed separately so it can truthfully name the immutable implementation commit. The report-only commit SHA is recorded in the final handoff.
