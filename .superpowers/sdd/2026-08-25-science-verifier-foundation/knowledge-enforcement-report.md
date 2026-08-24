# Science knowledge enforcement report

Date: 2026-08-25
Branch: `codex/science-verifier`
Baseline: `52254d20bbb15ad6d1140a7ccf58fa6b467dfaf2`

## Outcome

The two critical enforcement gaps are closed without activating any real Source or Evidence.

1. Active decision components fail closed unless a trusted callback resolves every approving human reviewer to `science.admin`. Draft, pending, inactive, blocked, missing/stale approval, unverifiable author, self-approval, caller-written role, untrusted reviewer, and unpinned Source paths are rejected.
2. Evidence claim scope is now closed, canonical-hash-bound metadata inside every Evidence `science` profile. `VerificationRule` binds a typed `EvidenceUse`, and Catalog resolution checks exact Evidence reference, claim family, purpose, and required conditions before the engine can receive the Rule.
3. Candidate Releases remain usable for qualification assembly only. Catalog active resolution rejects them by default, and the engine independently refuses candidate or withdrawn Releases even if handed a structurally valid Rule set.
4. The spin-time prose explicitly forbids both RPM and spin-speed thickness-direction families. The figure Observation is limited to the named AZ 125nXT grades, revision 01/24, and recorded plotted-marker ranges. KCL use is limited to the lumped-matter approximation with no net node-charge accumulation over the modeled timescale.

All repository Source/Evidence documents remain `draft` / `pending_review` with blocked release eligibility. No real approval event or active decision eligibility was added.

The unrelated pre-existing untracked `.superpowers/application-architecture-scout.md` was not read, edited, staged, or committed.

## RED/GREEN evidence

### Trusted active-release gate

Initial focused RED:

```text
12 failed
```

The constructor had no trusted resolver, active resolution did not inspect Source/Evidence governance, and candidate Rule sets were accepted as active.

GREEN coverage now proves:

- trusted `science.admin` positive fixture;
- no-resolver fail-closed behavior;
- draft, pending review, inactive decision, blocked release, missing event, temporal inversion, missing author, self-approval, caller-written Admin role, and non-admin resolver rejection;
- direct `resolve_release()` cannot bypass the same active gate;
- active Evidence must pin its exact Source component;
- candidate Releases may resolve for qualification but cannot execute through Catalog or engine.

### Executable Evidence scope

Typed `EvidenceUse` initial RED:

```text
1 failed, 2 passed
```

The Rule schema rejected the new field as unknown. GREEN added the closed typed object and exact, duplicate-free identity with `evidence_refs`.

Evidence-profile claim-scope RED:

```text
5 failed
```

The profile ignored scope structure and hash drift. GREEN added exact field sets, nonblank/unique lists, allow/forbid collision checks, and canonical hash verification.

Catalog scope RED:

```text
8 failed
```

Rules with a different family, broader purpose, missing required conditions, or forbidden RPM/spin-speed family reached rule-set resolution. GREEN rejects each before engine entry, including descendant families below a forbidden prefix.

Self-review RED also found duplicate `evidence_refs` and an engine-level candidate-release bypass:

```text
2 failed
1 failed
```

GREEN requires duplicate-free exact Evidence identity in both profile and typed Rule, and `verify_claim()` now rejects non-operational release status independently of Catalog call mode.

## Data disposition

- All 45 Evidence documents carry `claim_scope` and `claim_scope_hash` inside their hashed OKF metadata.
- `evidence-claim-scope-v0.1.yaml` remains a review summary only. Tests require its scope and hash to be byte-semantically identical to each embedded Evidence profile; Catalog never reads it as authority.
- Inactive Evidence retains an empty allowed-claim list and cannot satisfy a Rule use.
- No original span, locator, Source checksum, reviewed translation, access status, or approval state was broadened or rewritten.

## Final verification

Required Foundation, ledger, profile, and OKF tests:

```bash
TMPDIR=/tmp /tmp/boi-wiki-sci-task4-venv/bin/pytest \
  tests/test_science_models.py tests/test_science_profile.py \
  tests/test_science_catalog.py tests/test_science_engine.py \
  tests/test_science_source_ledger.py tests/test_okf_lint.py -q
```

Output:

```text
........................................................................ [ 22%]
........................................................................ [ 44%]
........................................................................ [ 66%]
........................................................................ [ 89%]
...................................                                      [100%]
323 passed in 8.15s
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

Compilation, whitespace, and no-activation checks:

```bash
/tmp/boi-wiki-sci-task4-venv/bin/python -m compileall -q boi_api/app/science
git diff --check
! rg -n "active_release_eligible|decision_eligibility: eligible|status: approved|review_status: approved" \
  data/boi/public/science
```

Output: no output; exit status `0`.

## Self-review

- Re-read the active-release and Evidence-scope requirements against the final production paths, not only the tests.
- Confirmed caller-written `role` fields are never authorization input; the resolver receives only a sanitized human identity.
- Confirmed active approval time must follow authored, retrieved, locator-retrieved, and curated timestamps.
- Confirmed a missing resolver, resolver exception, missing author identity, or unresolved Admin role is operational failure rather than a scientific verdict.
- Confirmed every Evidence use has one exact Evidence ref and one exact embedded allowed claim; forbidden prefixes win before allow lookup.
- Confirmed candidate qualification mode cannot be reused at the engine boundary.
- Confirmed the summary YAML is not referenced by Catalog or engine production code.
- Confirmed the 45 real Evidence documents remain pending and release-blocked.
- Confirmed no TODO, FIXME, suppression, source-body import, or unrelated file edit was introduced.

## Concerns

None within this enforcement scope. A real Source/Evidence activation still requires an externally supplied trusted reviewer-role resolver and a genuine authorized Admin review event; this change intentionally does not provide either.
