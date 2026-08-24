# Knowledge Task 3 Evidence Report — Domain and Application Packs

## Implementation commit

Implementation commit: `63bf9143efc99d616bf33c7d4bfcf9429d2b29d6` (`docs: add scientific domain and application packs`).

This report is committed separately so it can name the immutable implementation commit. Neither commit activates a Science Release or records a human review.

## Delivered inventory

| Pack | Knowledge | Rules | Qualification matrices | Public cases |
|---|---:|---:|---:|---:|
| Physical Principles | 5 | 5 | 5 | 50 |
| Chemical Principles | 5 | 5 | 5 | 50 |
| Circuit Principles | 6 | 6 | 6 | 60 |
| Materials Science | 5 | 5 | 5 | 50 |
| Semiconductor Devices | 6 | 6 | 6 | 60 |
| Spin Coating | 5 | 5 | 5 | 50 |
| **Task 3 total** | **32** | **32** | **32** | **320** |

- Non-Spin cases: 270.
- Foundation plus Task 3: 44 Rules and 440 qualification cases.
- Domain ontology bindings: 14, all interpretation-only and without outcome direction.
- Packs: 6, all candidate-only and dependent on the declared Foundation/domain packs without override.

## Evidence and source disposition

Task 3 adds two checksum-bound Source drafts and five short Evidence drafts:

| Source | Verified official URL | Retrieved PDF SHA-256 |
|---|---|---|
| MicroChemicals, *Spin-coating of Photoresists* | `https://www.microchemicals.com/dokumente/application_notes/spin_coating_photoresist.pdf` | `3d9b159838744f504db5c9742ef7f18b1b5f5d2ff78dfecc487086f41639c6b7` |
| NISTIR 5851 (1997) | `https://nvlpubs.nist.gov/nistpubs/Legacy/IR/nistir5851r1997.pdf` | `7f4e939b3fd4dc621ffd6a534773b08da687d4052b2148c865436ac30b9b854b` |

The five new Evidence objects are:

1. MicroChemicals spin-coating mechanism, PDF page index 0.
2. MicroChemicals drying-limited spin-speed/thickness direction, PDF page index 0.
3. MicroChemicals immediate-post-spin film-state change, PDF page index 1.
4. MicroChemicals equipment influence, PDF page index 2.
5. NIST thin-film versus same-composition bulk mechanical properties, PDF page index 24 (printed page 17).

Each stores the exact short original span, exact locator, retrieved-file checksum, original-text SHA-256, reviewed Korean translation, narrow embedded claim scope, explicit limitations, and agent retrieval/curation identity. The translations do not expand the source claim.

The complete ledger after Task 3 contains 50 Evidence objects: 47 `pending_review`, 3 `inactive`, and **0 active**. All 50 remain `blocked_pending_authorized_admin_review`. The five new Evidence objects are among the 47 pending drafts. The access-limited Emslie and Meyerhofer abstract records remain excluded from Rule evidence paths; they are recorded only as excluded Evidence on the related Knowledge drafts.

## Governance and capability boundary

Every new Knowledge, Rule, Binding, Matrix, Pack, Source, and Evidence object records agent authorship, `draft`/`pending_review`, no authorized review event, and release blocking. Every Qualification Matrix has an empty `release_refs` list.

Candidate tests resolve only `QualificationRuleSet`. Passing 440 public cases does not issue `OperationalVerification`, does not create an operational attestation, and cannot be evaluated as an active Release. Active capability count is **0**. A real authorized Admin review and later Release activation remain mandatory.

## Qualification semantics

Every Rule has exactly ten distinct natural-language cases:

1. clear violation
2. in-scope consistency
3. missing required condition
4. outside validity domain
5. empirical verification required
6. negation
7. unit variation
8. decision-changing ambiguity
9. paraphrase
10. false-red prevention

All 320 `source_span.exact` values are natural scientific sentences. The tests recompute each document digest as SHA-256 over that exact sentence, verify the Unicode-code-point end offset, and require all ten sentences for a Rule to be distinct.

The Rule evaluator gained two closed fields used by these cases:

- `context_dimensions`: requires a named quantity, validates its dimensionality, and makes unit variants executable inputs rather than ignored probes.
- `empirical_trigger_conditions`: keeps an equipment/numeric claim on its own target Rule and returns `EMPIRICAL_ONLY` without borrowing another Rule.

The locked conversion registry now contains exact bidirectional registrations used by 15 scientific quantity families: angular rate, force, energy, pressure, molarity, current, voltage, resistance, capacitance, diffusivity, carrier energy, conductivity, thickness, dynamic viscosity, and spin rate.

## Task 2 independent-review guards applied to Task 3

- **No synthetic source labels or fake digests:** every case uses a natural sentence; its digest and offset are recomputed in tests.
- **No borrowed empirical Rule:** `evaluation_rule_id == matrix_rule_id`; every Rule owns a typed empirical trigger and produces `EMPIRICAL_TRIGGER_MATCHED` itself.
- **False-red remains scientifically adjacent:** it keeps subject, relation, object, and predicate equal to the clear violation, changes a real typed applicability condition, and states that changed scope in the source sentence.
- **No ignored unit probe:** the alternative quantity is present in the normalized claim, is named in `context_dimensions`, is dimension-checked by the target evaluator, and must preserve the baseline verdict.
- **No free AI self-attestation booleans:** Task 3 Rules use structured enum/reference values. Only the two boolean parameter-known constraints required verbatim by existing embedded Evidence scopes are accepted.
- **Evidence scope is executable:** every `EvidenceUse` exactly matches an embedded allowed claim family and purpose; candidate Catalog resolution proves all scope-required typed conditions are present before Rule evaluation.
- **Association is not silently collapsed into correlation:** Task 3 bindings contain neither alias and remain interpretation-only; the Foundation distinction is not overridden.
- **Generality is not metre-only:** 15 exact scientific unit-pair tests cover mechanical, chemical, electrical, semiconductor, materials, and Spin quantities.

## Required failure examples

The decisive cases include fixed-voltage versus fixed-current resistor power, catalyst versus equilibrium constant, same-composition bulk versus deposited thin-film properties, doping/mobility/conductivity, ideal versus real MOS gate current, and product-scoped Spin direction. The Spin rules return no RPM setting, percentage change, DOE starting point, or recipe recommendation.

## TDD and verification record

RED was observed before implementation:

```text
ScienceCatalogError: unknown science pack: sci-pack:physical-principles/0.1.0
```

Additional focused RED tests exposed:

```text
15 failures: scientific unit pairs were not registered
1 failure: boolean *_identified / *_documented self-attestation was present
1 failure: only 9 unique case sentences for validity-domain Rules
```

The minimal implementation added the closed Rule gates and corrected the data/cases. Fresh final command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest -q \
  tests/test_science_foundation_pack.py \
  tests/test_science_domain_packs.py \
  tests/test_science_engine.py \
  tests/test_science_source_ledger.py \
  tests/test_science_profile.py \
  tests/test_science_catalog.py \
  tests/test_science_models.py \
  tests/test_okf_lint.py
```

Result: `373 passed in 30.60s`.

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/python \
  scripts/okf_lint.py --root data --strict-links --strict-media
```

Result: `OKF lint passed`; 469 Markdown documents, 731 graph links, and 25 image links checked.

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/python -m compileall -q \
  boi_api/app/science tests/test_science_domain_packs.py \
  tests/test_science_engine.py tests/test_science_source_ledger.py
git diff --check
```

Result: both exited zero.

## Files by responsibility

- Engine/schema: `boi_api/app/science/rules.py`, `boi_api/app/science/units.py`.
- Sources/Evidence: two Source drafts, five Evidence drafts, source ledger, and claim-scope manifest under `data/boi/public/science`.
- Knowledge/Rules/Cases: six domain directories under `knowledge`, `rules`, and `qualification/cases`.
- Interpretation: 14 files under `ontology-bindings/domain`.
- Pack manifests: six files under `packs`.
- Tests: `tests/test_science_domain_packs.py`, `tests/test_science_engine.py`, and `tests/test_science_source_ledger.py`.

## Self-review

- No human author, approval, active Release, or operational capability was invented.
- No existing inactive abstract was used as decision Evidence.
- Source URLs, PDF checksums, page indices, short spans, and original-text hashes are explicit and test-bound.
- Ontology aids interpretation only and carries no scientific direction.
- Spin remains a specialization of the shared Rule engine and contains no recipe-setting path.
- The independent review skill normally dispatches a reviewer agent, but the Task 3 instruction explicitly prohibited subagents; the fallback was a staged-diff self-review plus the full deterministic regression above.
- Unrelated untracked `.superpowers/application-architecture-scout.md` and `.superpowers/knowledge-task2-review.md` were preserved and excluded from both commits.
