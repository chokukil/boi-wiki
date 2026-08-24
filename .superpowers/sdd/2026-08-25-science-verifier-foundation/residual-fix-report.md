# Foundation residual fix report

Date: 2026-08-25

Scope: the three Important residual findings in `final-fix-review.md` only. No Knowledge content or unrelated architecture work was included.

## Outcome

The residual trust boundaries are closed:

1. Claim and Rule unit tokens are trimmed before policy/registry lookup, canonical `pH` is rejected, and condition/equation magnitude comparisons can cross units only through one exact reviewed conversion registration.
2. Claim quantity/condition identifiers are canonical, nonempty, unique, and unable to collide with the synthetic `process_stage` or `material_state` condition keys. Unitless condition equality distinguishes boolean, numeric, and string scalar kinds.
3. Release incompatibility and release/rule-set integrity failures raise `ScienceOperationalError` before rule evaluation or scientific verdict selection. `INSUFFICIENT_INFORMATION` is retained for scientific coverage and condition gaps only.

The unrelated pre-existing untracked `.superpowers/application-architecture-scout.md` remained untouched and unstaged.

## RED/GREEN evidence

### 1. Canonical unit tokens and reviewed conversion execution

The tests name the two unsafe mutations: removing token canonicalization and falling back from the reviewed registry to Pint magnitude conversion.

Initial RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_condition_evaluator_rejects_an_unregistered_cross_unit_conversion \
  tests/test_science_engine.py::test_verify_claim_rejects_unregistered_condition_conversion_before_red \
  tests/test_science_engine.py::test_equation_evaluator_rejects_an_unregistered_cross_unit_conversion \
  tests/test_science_engine.py::test_whitespace_ph_variants_are_rejected_at_claim_and_rule_boundaries \
  tests/test_science_engine.py::test_claim_and_rule_units_are_canonicalized_at_their_schema_boundaries -q
```

Observed RED:

```text
7 failed in 0.27s
```

The condition evaluator and full verifier returned normally after treating `1 inch` as `2.54 centimeter`; the equal-equation evaluator did the same. Three whitespace `pH` cases crossed both Claim and Rule construction, and accepted unit fields retained surrounding whitespace.

Composite-equation RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_engine.py::test_product_equation_rejects_unregistered_composite_unit_conversion -q
```

Observed RED:

```text
1 failed in 0.21s
Failed: DID NOT RAISE UnregisteredConversionError
```

Minimal GREEN implementation:

- Canonical unit fields trim at `ClaimQuantity`, `ClaimCondition`, `ConditionConstraint`, and `VerificationRule.expected_dimensions` boundaries; empty tokens and canonical `pH` are rejected.
- Direct unit helpers canonicalize before the ambiguity guard, so whitespace cannot change `pH` into picohenry.
- `comparable_values()` verifies dimensional compatibility with the locked registry but performs any magnitude conversion only through the exact `ConversionRegistry` entry. Same-unit values need no conversion; absent or ambiguous pair registrations raise `UnregisteredConversionError`.
- Condition equality/ranges call the reviewed comparison path.
- Equal, product, and quotient equations build deterministic unit pairs and call the same reviewed path. The existing Ohm-law product is represented by explicit `ampere * ohm <-> volt` registrations; other composite conversions fail closed until reviewed and registered.
- The former evaluator `.to()` and `_pint_quantity()` magnitude-conversion paths were removed.

Focused GREEN, including existing allowed Celsius/Kelvin, centimeter/meter, Ohm-law, dimension-error, and verdict cases:

```text
18 passed in 0.19s
```

After the identifier/type cycle was combined with these conversion regressions, the focused target remained:

```text
24 passed in 0.20s
```

### 2. Identifier ambiguity and scalar-kind compatibility

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_claim_rejects_empty_quantity_kind_and_condition_id \
  tests/test_science_engine.py::test_claim_rejects_duplicate_quantity_and_condition_identifiers \
  tests/test_science_engine.py::test_claim_condition_ids_cannot_collide_with_reserved_synthetic_conditions \
  tests/test_science_engine.py::test_unitless_condition_evaluator_rejects_incompatible_scalar_kinds \
  tests/test_science_engine.py::test_verify_claim_cannot_turn_bool_numeric_condition_ambiguity_red -q
```

Observed RED:

```text
9 failed in 0.28s
```

The schema admitted blank, duplicate, and reserved identifiers. Both `True == 1` and `True != 0` satisfied decision-changing unitless conditions; the full verifier consequently returned `VIOLATION` for the boolean/numeric case. String/numeric mismatch was nondecisive but lacked a typed mismatch reason.

Minimal GREEN implementation:

- `quantity_kind` and `condition_id` are stripped and must remain nonempty.
- `NormalizedClaim` rejects repeated quantity kinds, repeated condition IDs, and condition IDs reserved for `process_stage`/`material_state`.
- Condition scalar compatibility classifies boolean, numeric, and string separately. Integer and float remain one numeric kind; boolean is never numeric.
- A scalar-kind mismatch records `INCOMPATIBLE_CONDITION_TYPES`, remains unsatisfied, and enters `MISSING_CONDITIONS`/`UNDECIDED` rather than predicate evaluation.

Focused GREEN with full-verifier coverage:

```text
24 passed in 0.20s
```

### 3. Operational boundary for incompatible or corrupt execution state

Existing integrity-as-verdict tests were changed first to require the approved typed exception, and a new incompatible-release-set full-verifier regression was added.

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_incompatible_release_set_is_an_operational_error_not_a_verdict \
  tests/test_science_engine.py::test_release_must_pin_the_rule_and_every_explanation_reference \
  tests/test_science_engine.py::test_omitting_any_release_pinned_rule_fails_complete_coverage \
  tests/test_science_engine.py::test_same_id_substituted_rule_body_fails_semantic_integrity \
  tests/test_science_engine.py::test_substituted_rule_cannot_replace_the_resolved_component_semantic_digest \
  tests/test_science_engine.py::test_released_rule_component_digest_must_match_exact_release_component \
  tests/test_science_engine.py::test_extra_unpinned_rule_fails_exact_release_coverage -q
```

Observed RED:

```text
7 failed in 0.28s
Failed: DID NOT RAISE ScienceOperationalError
```

Minimal GREEN implementation:

- `verify_claim()` invokes `_rule_set_integrity()` before resolving candidates or evaluating rules.
- Any release compatibility, combined/release-set digest, rule-set completeness/identity, component digest, or semantic digest reason raises `ScienceOperationalError` with the deterministic reason code(s).
- Integrity reasons are no longer merged into scientific coverage or Verdict reason codes.

Focused GREEN:

```text
7 passed in 0.18s
```

## Files changed

- `boi_api/app/science/models.py`: canonical/nonempty unit and identifier fields; unique/reserved Claim lookup validation.
- `boi_api/app/science/units.py`: canonical unit policy, exact registered-pair conversion selection, reviewed comparable-value API, explicit Ohm-law composite registrations.
- `boi_api/app/science/rules.py`: canonical Rule dimension units, scalar-kind-safe condition gates, allowlisted equation comparisons.
- `boi_api/app/science/engine.py`: typed operational failure before scientific selection.
- `tests/test_science_engine.py`: evaluator, full-verifier, schema, conversion, and operational regressions; old integrity-as-verdict expectations updated.

## Self-review

- Re-read all three residual findings and checked each required behavior against the final diff.
- Searched Rule and engine paths for `_pint_quantity`, `.to()`, and `to_base_units()`; no decision-changing evaluator path retains them.
- Confirmed Pint is now used in comparison only to parse a locked unit and compare dimensionality, never to convert a magnitude across distinct unit tokens.
- Confirmed exact same-unit comparisons do not require a conversion and every distinct-token magnitude comparison requires exactly one reviewed registration or raises.
- Confirmed equal, product, and quotient equation forms all cross `comparable_values()`.
- Confirmed Claim quantities and conditions cannot enter last-value-wins maps with blank, duplicate, or reserved identifiers.
- Confirmed boolean/numeric and string/numeric mismatches remain nondecisive for both `eq` and `ne`; integer/float values remain compatible numeric scalars.
- Confirmed all `_rule_set_integrity()` failures are raised before candidate selection/evaluation, while genuine missing rules/grounding/conditions still use scientific `INSUFFICIENT_INFORMATION`.
- Confirmed the full engine suite passes independently: `76 passed in 0.22s`.
- Confirmed no TODO, FIXME, type-ignore, or unrelated file change was introduced.

## Final verification

Exact four-suite command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_models.py tests/test_science_profile.py tests/test_science_catalog.py tests/test_science_engine.py -q
```

Output:

```text
........................................................................ [ 42%]
........................................................................ [ 84%]
...........................                                              [100%]
171 passed in 0.81s
```

Compilation and diff validation:

```bash
python -m compileall -q boi_api/app/science
git diff --check
```

Output: no output; exit status `0`.

## Concerns

None within the requested residual scope. Cross-unit pairs and composite equation conversions not present in the immutable reviewed registry intentionally fail with `UnregisteredConversionError`; enabling one requires an explicit conversion definition and regression proof.
