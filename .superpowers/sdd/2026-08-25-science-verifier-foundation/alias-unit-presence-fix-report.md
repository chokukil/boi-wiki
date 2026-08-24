# Science Verifier Foundation alias/unit-presence fix report

Date: 2026-08-25

Base commit: `923708c`

Scope: the two Important findings in `final-fix-review.md` only

## Outcome

The condition boundary now requires symmetric unit presence before every scalar comparison. A unit on exactly one side produces `INCOMPATIBLE_CONDITION_UNIT_PRESENCE`, keeps the Rule `MISSING_CONDITIONS`/`UNDECIDED`, and cannot produce a red full-verifier verdict. `ClaimCondition` also rejects a unit on a string, boolean, or missing value.

The unit boundary now canonicalizes only the explicitly reviewed aliases for the already registered families:

- `K` / `kelvin`
- `°C` / `degC` / `degree_Celsius`
- `m` / `meter`
- `cm` / `centimeter`
- `V` / `volt`
- `A` / `ampere`
- `Ω` / `ohm`

The registered Ohm-law product has one deterministic canonical form, `ampere * ohm`, for both factor orders and the reviewed aliases. Cross-unit magnitude conversion remains restricted to exact `ConversionRegistry` definitions; no evaluator calls unrestricted Pint conversion. The existing `inch <-> centimeter` condition/equation rejection tests remain green.

## Strict RED/GREEN evidence

### Cycle 1: symmetric condition unit presence

Tests were added first for evaluator `eq`, `range`, and ordered comparisons in both one-sided-unit orientations; full `verify_claim()` false-red behavior; and rejection of units on nonnumeric Claim conditions. The existing rule-unit/claim-unitless reason assertion was updated to the typed symmetric reason.

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_typed_condition_missing_required_unit_is_missing_conditions \
  tests/test_science_engine.py::test_condition_evaluator_requires_symmetric_unit_presence \
  tests/test_science_engine.py::test_verify_claim_cannot_turn_one_sided_condition_unit_red \
  tests/test_science_engine.py::test_claim_condition_rejects_a_unit_on_nonnumeric_value -q
```

RED output:

```text
13 failed in 0.33s
```

Minimal production change:

- compare `(constraint.unit is None)` and `(actual_unit is None)` before scalar/value evaluation;
- classify one-sided units as `INCOMPATIBLE_CONDITION_UNIT_PRESENCE`;
- treat that reason as a missing-condition applicability result;
- reject `ClaimCondition.unit` unless the value is numeric and not `bool`.

GREEN command: the same focused command.

```text
13 passed in 0.19s
```

The final matrix also includes `ne` and both unit orientations at the full `verify_claim()` boundary:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_condition_evaluator_requires_symmetric_unit_presence \
  tests/test_science_engine.py::test_verify_claim_cannot_turn_one_sided_condition_unit_red -q
```

```text
16 passed in 0.21s
```

### Cycle 2: reviewed aliases and commutative Ohm-law product

Tests were added first for condition aliases in both directions, voltage equality aliases, both Ohm-law product orders, every requested family in both comparison orders, registered conversions through aliases, and preservation of the unregistered `inch <-> centimeter` failures.

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_condition_evaluator_accepts_reviewed_aliases_in_both_orders \
  tests/test_science_engine.py::test_equal_equation_accepts_reviewed_voltage_aliases_in_both_orders \
  tests/test_science_engine.py::test_ohm_law_product_uses_reviewed_aliases_and_commutative_canonical_order \
  tests/test_science_engine.py::test_every_registered_unit_family_has_reviewed_alias_normalization \
  tests/test_science_engine.py::test_registered_conversions_accept_canonical_aliases_in_both_directions \
  tests/test_science_engine.py::test_condition_evaluator_rejects_an_unregistered_cross_unit_conversion \
  tests/test_science_engine.py::test_equation_evaluator_rejects_an_unregistered_cross_unit_conversion -q
```

RED output:

```text
23 failed, 7 passed in 0.65s
```

Minimal production change:

- introduce one shared reviewed alias map at the Claim/Rule/unit-registry boundaries;
- reduce Celsius conversion registrations to their canonical endpoints;
- canonicalize only the registered `ampere`/`ohm` product and sort its factors;
- keep every other cross-unit comparison behind exact reviewed registry lookup.

GREEN output for the alias/conversion matrix plus retained rejection cases:

```text
30 passed in 0.20s
```

### Cycle 3: alias identity at the conversion API boundary

A self-review found that direct `convert_value(alias, canonical)` normalized both endpoints but still attempted an unnecessary conversion lookup. A focused test covering all seven alias families was added before changing production.

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_convert_value_treats_reviewed_aliases_as_identity_before_lookup -q
```

RED output:

```text
7 failed in 0.31s
```

Minimal production change: after canonicalization, identical endpoints return the unchanged finite Decimal only for multiplicative/affine requests without a requested conversion ID. Logarithmic and procedure-defined requests still fail closed.

GREEN output:

```text
7 passed in 0.19s
```

Final focused boundary matrix, including both one-sided-unit directions and retained unregistered conversions:

```text
48 passed in 0.20s
```

## Files changed

- `boi_api/app/science/models.py`: shared reviewed unit canonicalization and nonnumeric Claim-condition unit rejection.
- `boi_api/app/science/rules.py`: symmetric unit-presence mismatch and nondecisive applicability mapping.
- `boi_api/app/science/units.py`: canonicalization before registry lookup, canonical conversion registrations, safe alias identity.
- `tests/test_science_engine.py`: evaluator and full-verifier false-red regressions, complete alias/order coverage, fail-closed preservation.
- this report.

## Final verification

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_models.py tests/test_science_profile.py \
  tests/test_science_catalog.py tests/test_science_engine.py -q
```

```text
225 passed in 0.87s
```

```bash
python -m compileall -q boi_api/app/science
```

```text
exit 0
```

```bash
git diff --check
```

```text
exit 0
```

## Self-review

- Unit presence is checked before type compatibility or magnitude comparison; the mismatch therefore cannot reach a red decision path.
- `eq`, `ne`, `range`, and ordered comparisons are covered in both one-sided-unit orientations at evaluator and full-verifier boundaries.
- Boolean values remain distinct from numeric values; the new Claim validator explicitly excludes `bool`.
- Alias normalization is an exact finite map. It does not ask Pint for conversion magnitudes.
- Composite canonicalization is deliberately limited to the registered two-factor Ohm-law family; arbitrary products and exponent expressions remain unregistered.
- Cross-unit conversions still use `ConversionRegistry.convert_registered()` and exact canonical endpoint pairs.
- Existing `inch <-> centimeter` condition, full-verifier, equality-equation, and product-equation tests are green.
- Logarithmic conversion remains unsupported and unregistered procedure conversion remains rejected.
- The unrelated untracked `.superpowers/application-architecture-scout.md` was preserved and not staged.

## Concerns

None within this fix scope. New aliases or composite unit families must be reviewed and explicitly added rather than inferred through Pint.
