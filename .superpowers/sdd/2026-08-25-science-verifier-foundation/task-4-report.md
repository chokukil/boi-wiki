# Science Verifier Foundation — Task 4 Report

## Scope completed

- Added a locked Pint registry, finite/defined unit validation, base-unit normalization, deterministic compatible-quantity comparison, and explicit incompatible-dimension rejection.
- Added a strict `VerificationRule` schema and the five closed rule-kind evaluators: directional relation, equation constraint, dimension constraint, validity domain, and empirical boundary. No evaluator accepts source text, paths, or executable expressions.
- Added pure `verify_claim` aggregation over explicit `ClaimPacket`, `ResolvedRelease`, and validated rule objects. Only release-pinned rules with release-resolved Knowledge and Evidence refs can contribute to a verdict or explanation fact.
- Enforced false-red precedence: unresolved ambiguity stops before dispatch; missing coverage/conditions precede validity mismatch; validity mismatch precedes empirical-only gating; only fully `IN_SCOPE` evaluations can produce `VIOLATION` or `CONSISTENT`.

## RED evidence

1. Wrote `tests/test_science_engine.py` first with literal Claim, Rule, and Release fixtures. The tests name the protected breaks: five primary verdicts, condition-change false red, contradiction-gate precedence, ambiguity bypass, unpinned grounding, audit detail, dimension mismatch, unknown rule kind, unsafe units, user-loaded definitions, and byte instability.
2. Ran:

   ```bash
   TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_engine.py -q
   ```

   Initial result: collection failed with `ModuleNotFoundError: No module named 'boi_api.app.science.engine'`, the intended missing-feature failure.
3. The first registry implementation exposed an initialization-order defect: Pint's post-init tried to load its bundled definitions after the lock was set. The test collection failed with `PermissionError: Science unit registry is locked`; moving the lock to `_after_init` preserved bundled loading and blocked only post-startup mutation.
4. Added the brief's public `normalized_quantity(value, unit)` contract before implementing it. Collection failed with `ImportError: cannot import name 'normalized_quantity'`; the function was then implemented through the already-tested validation path.
5. Self-review found that an undefined unit in a dimension rule was being converted into a contradiction. Added `test_undefined_unit_is_rejected_instead_of_becoming_a_violation` first; it failed with `DID NOT RAISE InvalidQuantityError`. The evaluator now lets unit-validation failure reject the input instead of synthesizing a false `VIOLATION` candidate.

## GREEN evidence

1. The focused engine suite passed:

   ```bash
   TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_engine.py -q
   ```

   Result: `15 passed in 0.17s`.
2. The requested Science regression suite passed under Python 3.11, required by the already-pinned Pint 0.25 dependency:

   ```bash
   TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_models.py tests/test_science_profile.py tests/test_science_catalog.py tests/test_science_engine.py -q
   ```

   Result: `69 passed in 0.53s`.
3. The byte-stability test evaluates the same Claim and Release twice with opposite rule iteration order and compares literal `canonical_json_bytes(VerdictPacket)` outputs.

## Self-review

- Ambiguity is checked before rule iteration. A non-confirmed interpretation or any ambiguity ID raises `UnresolvedAmbiguityError`; no verdict is synthesized for unresolved meaning.
- Required-condition mismatch is deliberately `MISSING_CONDITIONS`, not contradiction. Missing validity fields also stop as information insufficiency, while present-but-incompatible validity values return `OUTSIDE_DOMAIN`.
- Coverage fails closed when no concept-matching rule is supplied, a matching rule is absent from the exact Release, its digest is unresolved, or either its Knowledge or Evidence refs are not release-resolved.
- Deterministic contradiction/support is reachable only from `IN_SCOPE`. A mix of qualified support and contradiction returns information insufficiency for explicit review.
- `corrected_claim` is populated only for `VIOLATION`; condition, domain, empirical, and coverage gates always leave it empty.
- Every emitted explanation fact has at least one resolved Knowledge ref and one resolved Evidence ref. Sorting and de-duplication cover rules, conditions, refs, reason codes, facts, and limitations.
- Pint loads only its bundled definitions during initialization. After startup both `load_definitions` and `define` are locked, and no engine API accepts a definition path.
- Mutation check: reversing precedence, treating changed conditions as satisfied, dispatching an unknown kind, accepting a time unit as length, dropping Release/citation grounding, allowing a user unit file, reordering supplied rules, or emitting a correction outside `VIOLATION` is caught by the focused suite.

## Deliberate boundary

- `ResolvedRelease` intentionally carries immutable component identities/digests rather than rule bodies. `verify_claim` therefore accepts already validated `VerificationRule` objects explicitly and checks them against the Release. With no matching trusted rule it returns `INSUFFICIENT_INFORMATION`; it never reads a catalog path or invents a rule from an ID.
