# Foundation final review fix report

Date: 2026-08-25
Branch: `codex/science-verifier`

## Outcome

All nine findings in `final-fix-brief.md` are implemented as one coherent Foundation fix wave. The Science verifier now fails closed at directional predicates, typed conversions, typed condition units, release-set composition, polarity, Science profile metadata, Pack edges, and canonical numeric inputs. The catalog-to-engine proof resolves real stored Science objects and preserves the complete Foundation/Domain/Application selection in the verdict.

No Knowledge content was added. The pre-existing untracked `.superpowers/application-architecture-scout.md` was not read, edited, staged, or committed.

## Baseline

Command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_models.py tests/test_science_profile.py tests/test_science_catalog.py tests/test_science_engine.py -q
```

Output before this wave:

```text
91 passed in 0.59s
```

## RED/GREEN evidence

### 1. Directional false-red protection

RED command (the directional test is parametrized across positive expected/opposite/unchanged/association/unknown and negative expected/opposite/unknown cases):

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_engine.py::test_directional_rule_only_decides_expected_or_explicit_contradiction -q
```

RED output: `8 failed`; the prior evaluator classified every non-matching predicate as a contradiction and the Rule schema did not accept `contradiction_predicates`.

GREEN output after adding an explicit, directional-only contradiction list and polarity-aware evaluation: `8 passed`.

Self-review added `test_contradiction_predicates_are_explicit_and_directional_only`. RED: `1 failed` because omission still defaulted to an empty list. GREEN: `1 passed` after requiring the field to be explicitly supplied for directional rules and rejecting it on all other rule kinds.

### 2. Operational typed conversions

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_allowlisted_multiplicative_and_affine_conversions_use_decimal_arithmetic \
  tests/test_science_engine.py::test_logarithmic_and_unregistered_procedure_conversions_fail_explicitly \
  tests/test_science_engine.py::test_ambiguous_ph_token_is_not_parsed_as_an_si_prefix_unit -q
```

RED output: `3 failed`; the reviewed conversion API/errors did not exist and `pH` could be parsed as an SI-prefixed unit.

GREEN output: `3 passed` after adding an immutable allowlisted registry, Decimal multiplicative/affine conversions, exact Celsius/Kelvin point and interval behavior, explicit logarithmic/procedure failures, and the ambiguous-token guard.

Final self-review extended the `pH` guard to rule-declared units:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_engine.py::test_ambiguous_ph_token_is_not_parsed_as_an_si_prefix_unit -q
```

RED output:

```text
FAILED tests/test_science_engine.py::test_ambiguous_ph_token_is_not_parsed_as_an_si_prefix_unit
Failed: DID NOT RAISE AmbiguousUnitError
1 failed in 0.21s
```

GREEN output:

```text
1 passed in 0.17s
```

### 3. Exact multi-release boundary

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_catalog.py::test_resolved_release_set_preserves_roles_and_builds_deterministic_combined_rules \
  tests/test_science_catalog.py::test_release_set_rejects_duplicate_components_across_release_roles \
  tests/test_science_catalog.py::test_release_set_rejects_pack_dependency_absent_from_selection \
  tests/test_science_engine.py::test_verdict_preserves_complete_release_selection_and_exact_digests -q
```

RED output: `4 failed`; `resolve_release_set()` returned only a tuple, combined rules/digest/roles were absent, and duplicate/dependency conflicts were not rejected.

GREEN output: `4 passed` after introducing validated `ResolvedReleaseSet`, deterministic combined components/rules, exact role/digest preservation, Pack compatibility resolution, and `VerdictReleaseSet`.

Self-review RED found two manually constructible non-exact combinations (`combined_digest` forgery and omitted components): `2 failed`. GREEN after exact model validation and a canonical combined-digest function: `2 passed`. A temporary raw-`ResolvedRelease` compatibility overload was then removed from both catalog rule resolution and `verify_claim`; all callers now cross the explicit `ResolvedReleaseSet` boundary. Focused catalog/engine verification after that removal: `91 passed in 0.80s`.

### 4. Polarity for every rule kind

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_negative_claim_cannot_consist_with_a_satisfied_equation \
  tests/test_science_engine.py::test_negative_claim_cannot_consist_with_a_satisfied_dimension \
  tests/test_science_engine.py::test_negative_claim_cannot_consist_with_a_satisfied_validity_proposition \
  tests/test_science_engine.py::test_negative_claim_cannot_consist_with_a_qualified_empirical_proposition -q
```

RED output: `4 failed`; every satisfied evaluator returned `SUPPORTS` without consulting claim polarity.

GREEN output: `4 passed`. A negative claim denying a satisfied proposition now contradicts; a negative equation/dimension claim whose positive proposition is not established remains `UNDECIDED`.

### 5. Typed condition constraints and units

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_rule_conditions_reject_primitive_maps_and_accept_typed_constraints \
  tests/test_science_engine.py::test_typed_condition_normalizes_compatible_units_before_comparison \
  tests/test_science_engine.py::test_typed_condition_range_normalizes_units_at_both_boundaries \
  tests/test_science_engine.py::test_typed_condition_missing_required_unit_is_missing_conditions \
  tests/test_science_engine.py::test_same_number_with_incompatible_condition_units_cannot_create_false_red -q
```

RED output: `5 failed`; primitive maps were still the schema, typed ranges were rejected, and unit comparisons were unavailable.

GREEN output: `5 passed`. Rules now contain typed `ConditionConstraint` values (`eq`, `ne`, ordered comparisons, or range), comparison normalizes compatible units, missing required units yield `MISSING_CONDITIONS`, and incompatible dimensions yield `OUTSIDE_DOMAIN` without a false violation.

### 6. Exact Science profile version

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_profile.py::test_every_science_document_requires_exact_string_profile_version \
  tests/test_science_catalog.py::test_catalog_does_not_index_a_science_document_without_profile_version -q
```

RED output: `4 failed` across missing, wrong string, numeric `0.1`, and catalog-indexing cases.

GREEN output: `4 passed`; only the exact string `"0.1"` is accepted.

### 7. Closed typed Pack relations

RED targeted profile/catalog output: `5 failed`; bare strings, missing relations, malformed refs, and unknown/override relations crossed the profile or catalog boundary.

GREEN targeted output: `14 passed` across the six allowed enum values plus rejection cases. Self-review added non-list dependency collections, whitespace refs, extra keys, and custom relation-like objects; RED exposed six permissive cases, then GREEN was `12 passed` for the expanded Pack/profile/model target.

### 8. Canonical finite numbers

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_models.py::test_claim_packet_rejects_literal_nonfinite_numbers \
  tests/test_science_models.py::test_interpretation_model_settings_reject_nonfinite_numbers \
  tests/test_science_models.py::test_canonical_json_rejects_nonfinite_literals -q
```

RED output: `9 failed, 3 passed`; quantity validation already rejected some inputs, while Claim conditions, interpretation settings, and canonical JSON still admitted non-finite literals.

GREEN output: `12 passed`; all three literal values (`NaN`, `Infinity`, `-Infinity`) are rejected at each required boundary and canonical JSON uses `allow_nan=False`.

### 9. Stored-object catalog-to-engine proof

Test:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_catalog.py::test_catalog_to_engine_cross_task_proof_uses_exact_full_release_selection -q
```

The proof writes valid Source, Evidence, Knowledge, directional Rule, typed Pack, and Foundation/Domain/Application Release OKF fixtures. It resolves the exact release set and combined rule set through `ScienceCatalog`, obtains a grounded decisive `VIOLATION`, and asserts the exact Knowledge/Evidence refs plus complete release selection/digests. GREEN output: `1 passed`.

## Files changed

- `boi_api/app/science/models.py`: typed Pack edges, finite inputs, typed conditions, exact release-set/verdict release models.
- `boi_api/app/science/profile.py`: exact profile version and closed Pack dependency validation.
- `boi_api/app/science/digests.py`: recursive model normalization and strict canonical JSON numbers.
- `boi_api/app/science/units.py`: reviewed conversion registry, Decimal conversions, ambiguous-unit rejection.
- `boi_api/app/science/rules.py`: explicit directional opposites, typed condition evaluation, complete polarity handling, combined release-set rule binding.
- `boi_api/app/science/catalog.py`: typed Pack indexing, exact multi-release resolution/compatibility, combined rule resolution.
- `boi_api/app/science/engine.py`: exact `ResolvedReleaseSet` input, integrity checks, full release audit data.
- `tests/test_science_models.py`, `tests/test_science_profile.py`, `tests/test_science_catalog.py`, `tests/test_science_engine.py`: regression and end-to-end proof coverage.

## Self-review

- Compared the final implementation against each sentence of all nine findings and the Foundation plan/spec interfaces.
- Removed the raw release overload so Domain/Application rules cannot be relabeled as Foundation by the engine.
- Revalidated manually constructed release sets against original role order, exact digest map, exact deterministic component union, exact rule subset, and exact combined digest.
- Confirmed components, Pack dependency checks, rules, reason codes, refs, limitations, and output collections use deterministic ordering.
- Confirmed unknown/paraphrased directional predicates remain undecided and only declared opposites can produce directional red.
- Confirmed negative outcomes prefer undecided when the positive equation/dimension proposition is not established.
- Confirmed `pH` is rejected both for claim quantities and rule dimensionality declarations.
- Confirmed no dynamic unit definitions, arbitrary procedures, or logarithmic conversions are enabled.
- Searched for stale raw-release engine calls and stale `ResolvedRuleSet.release_id` construction; none remain.
- Ran `git diff --check`; no whitespace errors.
- Preserved the unrelated untracked architecture scout file.

## Final verification

Exact specified pytest command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_models.py tests/test_science_profile.py tests/test_science_catalog.py tests/test_science_engine.py -q
```

Output:

```text
........................................................................ [ 47%]
........................................................................ [ 94%]
.........                                                                [100%]
153 passed in 0.85s
```

Compilation and diff validation:

```bash
python -m compileall -q boi_api/app/science
git diff --check
```

Output: no output; exit status `0`.

## Concerns

None within the requested Foundation scope. Logarithmic and procedure-defined conversions intentionally remain explicit unsupported/unregistered failures until a reviewed conversion is added to the closed registry.
