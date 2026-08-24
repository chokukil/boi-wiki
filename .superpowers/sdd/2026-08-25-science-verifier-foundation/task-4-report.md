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

## Fix Round 1/5

### RED evidence

1. Added equation and kind-schema regressions first. The focused run produced `4 failed`: incompatible equation operands returned `CONTRADICTS`, while directional equation-only payloads, equation predicate-only payloads, and directional dimension payloads all validated.
2. Added claim-string empirical regressions first. Both `"unqualified"` and `"false"` produced `CONSISTENT`; the run was `2 failed`. Claim conditions no longer qualify observations.
3. Added the typed observation contract test before the class existed. Collection failed with `ImportError: cannot import name 'QualifiedObservation'`.
4. Added exact Release binding regressions before replacing the bare rule iterable. The run was `4 failed`: omitting pinned rules produced `VIOLATION`, substituting a same-ID body produced `CONSISTENT`, and duplicate IDs in both orders produced `VIOLATION`.
5. Added a catalog production test before its API existed. It failed with `AttributeError: 'ScienceCatalog' object has no attribute 'resolve_rule_set'`.
6. Self-review added three further kind-mixing cases first. Explicit equation polarity and corrections on validity/empirical rules all validated, producing `3 failed, 3 passed` before the validator was closed.

### GREEN evidence

1. `ResolvedComponent` now carries a derived rule `semantic_digest`. `ScienceCatalog.resolve_release` validates each typed `VerificationRule`, derives that digest, and `resolve_rule_set` produces the complete `ResolvedRuleSet` of `ReleasedRule(rule, component_digest, semantic_digest)` records from the exact stored OKF components.
2. `verify_claim` now requires `ResolvedRuleSet`. Before any evaluator runs it checks Release identity, duplicate IDs, exact equality between supplied and pinned rule ID sets, the exact OKF component digest, the Release component's semantic digest, and a fresh digest of the typed rule payload. Integrity/coverage failure returns `INSUFFICIENT_INFORMATION` and never a correction.
3. Equation operand dimensional incompatibility now raises `IncompatibleDimensionsError` instead of becoming contradiction. Directional, equation, dimension, validity, and empirical schemas reject fields owned by another evaluator; directional requires a predicate and equation requires structured operands.
4. Empirical support requires a typed `QualifiedObservation` with `verified=True`, matching rule ID, release-resolved measurement Knowledge, and Evidence that is both release-resolved and declared by the exact Rule. Nonblank claim strings, false records, unresolved measurements, and other resolved-but-undeclared Evidence remain `EMPIRICAL_ONLY`.
5. `ResolvedRuleSet` rejects duplicate IDs independent of order, and the engine retains a defensive duplicate check for objects constructed outside normal validation.
6. Ran the requested full regression command:

   ```bash
   TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest tests/test_science_models.py tests/test_science_profile.py tests/test_science_catalog.py tests/test_science_engine.py -q
   ```

   Result: `91 passed in 0.57s`.
7. Ran `python -m compileall -q boi_api/app/science` and `git diff --check`; both exited successfully with no output.

### Self-review

- Ambiguity remains the first gate. Rule-set integrity/coverage is the next gate and suppresses evaluation entirely; condition, validity, empirical, and deterministic result precedence remains unchanged after binding succeeds.
- Semantic substitution is caught even when the attacker preserves the rule ID and claimed component digest. Component substitution is independently caught against the exact `ResolvedRelease` component and manifest digest map.
- Exact set equality means an omitted unrelated pinned rule cannot be ignored merely because another supplied rule matches the current Claim; extra unpinned rules also cannot expand a Release.
- A typed observation is not trusted merely because `verified=True`: measurement and Evidence refs are checked against the current Release, and Evidence must also be declared by the empirical Rule.
- Mutation check: removing any ID-set equality branch, component comparison, semantic recomputation, observation grounding clause, schema-kind clause, equation dimension exception, or duplicate validator is caught by the focused tests.

### Updated boundary

- The earlier bare `VerificationRule` iterable boundary is superseded. Engine callers must obtain a `ResolvedRuleSet` from the catalog (or construct the identical typed contract in literal qualification tests); an unbound rule iterable is no longer accepted.
