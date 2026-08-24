# Science Verifier Foundation composite pH fix report

Date: 2026-08-25

Base commit: `1e697ef`

Scope: the one remaining Important composite-`pH` finding in `final-fix-review.md`

## Outcome

Unit expressions now fail closed whenever the exact identifier `pH` appears independently inside the whole expression. Operators, whitespace, parentheses, ASCII exponent operators, and Unicode superscript exponent syntax all form identifier boundaries. The shared validation runs through the existing canonical unit entry point, so it protects Claim and Rule schema validation, stored-payload dimension evaluation, quantity comparison, and full `verify_claim()` evaluation.

The lexical rule does not reject `pH` as a substring of another identifier. Reviewed aliases and the canonical commutative Ohm-law product are unchanged, and no Pint magnitude conversion was added.

## RED/GREEN evidence

### Cycle 1: composite expression boundaries

Tests were added before production changes for these unit expressions:

- `pH / meter`
- `pH ** 2`
- `meter * pH * second`
- `meter / (pH * second)`

The tests exercise normal Claim/Rule schema construction, deliberately unvalidated stored Claim/Rule payloads at the dimension evaluator, identical-unit comparison short-circuiting, and positive/negative full-verifier paths. They also establish negative controls for `pHase`, `alpha_pH`, and `pH2`, plus the existing `A * Ω` and `Ω * A` canonical products.

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py::test_composite_ph_is_rejected_at_claim_and_rule_schema_boundaries \
  tests/test_science_engine.py::test_dimension_evaluator_rejects_composite_ph_in_stored_payloads \
  tests/test_science_engine.py::test_comparison_boundary_rejects_composite_ph \
  tests/test_science_engine.py::test_verify_claim_never_selects_a_verdict_for_composite_ph \
  tests/test_science_engine.py::test_ph_lexical_guard_preserves_other_identifiers_and_reviewed_products -q
```

RED output:

```text
20 failed, 5 passed in 0.44s
```

All 20 finding cases failed with `DID NOT RAISE`: the schema, evaluator, comparison, and full verifier accepted the composite expressions. The five negative controls passed.

Minimal GREEN change: `canonical_science_unit_token()` now scans the complete expression for an independently bounded `pH` identifier before alias/product canonicalization. All schema and evaluator entry points already call this shared function directly or through `canonical_unit_token()`.

Initial GREEN output:

```text
25 passed in 0.19s
```

### Cycle 2: Unicode exponent boundary found during self-review

Self-review established that Pint also parses `pH²` as picohenry squared, while Python regex `\w` treats the superscript as part of a word. The Unicode exponent case was added before changing the initial implementation.

RED command:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_engine.py -k 'unicode_exponent or unicode-exponent' -q
```

RED output:

```text
5 failed, 155 deselected in 0.27s
```

Minimal GREEN change: replace `\w` boundaries with a small lexical scanner. Unicode alphabetic characters, `_`, and ASCII digits remain identifier characters; mathematical superscripts and operators are boundaries.

GREEN output:

```text
5 passed, 155 deselected in 0.19s
```

Final focused composite matrix:

```text
30 passed in 0.22s
```

Focused preservation matrix covering standalone/whitespace/composite `pH`, reviewed aliases, Ohm product commutation, and retained unregistered `inch <-> centimeter` rejection:

```text
56 passed in 0.22s
```

## Files changed

- `boi_api/app/science/models.py`: shared whole-expression lexical `pH` identifier guard.
- `tests/test_science_engine.py`: schema, stored dimension evaluator, comparison, positive/negative full-verifier, Unicode exponent, and negative-control regressions.
- this report.

## Final verification

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_models.py tests/test_science_profile.py \
  tests/test_science_catalog.py tests/test_science_engine.py -q
```

```text
255 passed in 0.83s
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

- The validator detects exact `pH` occurrences using both preceding and following lexical boundaries; it is not substring matching.
- Alphabetic characters from any Unicode script, underscore, and ASCII digits keep a token inside one identifier. This preserves `pHase`, `alpha_pH`, `pH2`, and analogous unrelated identifiers.
- Operators (`/`, `*`, `**`, `^`), whitespace, parentheses, and Unicode mathematical superscripts terminate the identifier and therefore reject `pH` before Pint parsing.
- Claim quantities and conditions and Rule condition units call `canonical_science_unit_token()` at schema validation. Rule expected dimensions and all unit helpers call the same policy directly or through `canonical_unit_token()`.
- Stored-payload evaluator tests intentionally use Pydantic `model_copy(update=...)` to bypass schema validation and prove the downstream dimension and full-verifier boundaries independently.
- Positive matching dimensions can no longer produce `CONSISTENT`; negative matching dimensions can no longer produce `VIOLATION`. Both raise `AmbiguousUnitError` before verdict selection.
- Comparison rejects the expression before the identical-unit shortcut.
- Existing reviewed aliases and both Ohm product orders remain accepted. Existing arbitrary `inch <-> centimeter` conversions remain rejected.
- The unrelated untracked `.superpowers/application-architecture-scout.md` was preserved and is not part of this fix.

## Concerns

None within this fix scope. Supporting scientific pH measurements later will require an explicit logarithmic/procedure-defined representation, not a Pint unit-token alias.
