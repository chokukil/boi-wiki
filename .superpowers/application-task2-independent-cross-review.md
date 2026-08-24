# Application Task 2 Independent Cross-review

- Review date: 2026-08-25 (Asia/Seoul)
- Reviewed implementation: `1f2ee564adc4a3f76083314e8cfcdd3d60ac5c66`
- Branch state inspected: `b2de59e67032f2e2117dabbdecda00b677cc2bcb`
  (`1f2ee56` plus a documentation-only report commit)
- Result: **FAIL**
- Critical: **0**
- Important: **2**
- Advisory: **2**

The real `ScienceCatalog` resolution path correctly pins the exact release,
Source, Evidence, URL, and locator. The service also checks that exact chain
before it constructs a normal report. Canonical URL syntax is now structural,
not a credential-word or entropy heuristic, and the closed-validation tests
cover LLM, confirmation, Store, private load, and WAL exception graphs.

Those good paths do not establish the claimed authority boundary. An
in-process caller can promote a candidate profile, mint the purportedly opaque
active identity, and open it successfully. More importantly, the serialized
active profile is only protected by caller-recomputable hashes. Direct Store
save/load and pending-WAL recovery never re-resolve it against Catalog. A
coordinated mutation of URL, Source, Evidence, Release, and locator therefore
persists as an authoritative `VerificationReport`.

## Important findings

### I1. The active Source identity is caller-mintable; candidate preview is not a one-way authority boundary

Locations:

- `boi_api/app/science/source_identity.py:11-12`
- `boi_api/app/science/source_identity.py:15-55`
- `boi_api/app/science/source_identity.py:58-123`
- `boi_api/app/science/catalog.py:651-684`
- `tests/test_science_catalog.py:1655-1683`
- `tests/test_science_interpretation.py:1497-1569`

`ReviewedSourceURLIdentity.__new__()` checks the module `_ISSUER_CAPABILITY`,
but `_issue_reviewed_source_url_identity()` is an importable application
function that supplies that capability for any `ReviewedSourceURLProfile` whose
state says `active`. It does not require a `ScienceCatalog`, release manifest,
or previously resolved Source/Evidence object.

The profile itself contains only serializable, caller-reconstructible data and
self-computed SHA-256 fields.
Starting with a candidate profile, a caller can serialize it, change
`qualification_state` to `active`, recompute `profile_digest`, validate the
model, call the issuer, and open the resulting sealed identity.

Independent executable probe:

```text
PROBE1_CALLER_MINTED_ACTIVE_IDENTITY= active True
```

The current tests do not exercise this path. They prove only that the class
cannot be constructed with no capability, that an already issued object cannot
be copied/pickled, and that the issuer rejects an unchanged candidate. The
candidate test changes `active -> candidate`; it does not test the required
`candidate -> active` transition with a recomputed digest. Test fixtures also
import and call the same issuer directly, demonstrating that the seal is not
confined to `ScienceCatalog`.

Impact:

- `type(identity) is ReviewedSourceURLIdentity` and `_open_*()` no longer prove
  that Catalog reviewed the profile.
- A candidate preview can be upgraded by data transformation rather than an
  authorized release decision.
- Non-copyability and pickle rejection do not compensate for arbitrary fresh
  issuance.

Required closure:

1. Do not accept a module-private issuer plus a self-hash as proof of Catalog
   authority. Define the actual trust boundary explicitly; Python underscores
   are naming conventions, not capabilities.
2. Make every authority consumer re-resolve the exact profile through the
   trusted `ScienceCatalog`/immutable release ledger. A seal may be an
   optimization, but cannot replace that resolution.
3. Treat candidate previews and persisted profiles as non-authoritative data.
   Only the result of exact Catalog resolution may authorize service/report
   construction.
4. Add an adversarial test that begins with the actual candidate preview,
   rewrites state and all self-hashes, invokes every available issuer/open path,
   and requires rejection before an `EvidenceLink` is constructed.

### I2. Coordinated self-consistent report tampering bypasses Catalog through Store, reload, and WAL recovery

Locations:

- `boi_api/app/science/models.py:738-752`
- `boi_api/app/science/models.py:804-887`
- `boi_api/app/science/models.py:890-1027`
- `boi_api/app/science/storage.py:603-637`
- `boi_api/app/science/storage.py:767-801`
- `boi_api/app/science/storage.py:960-1030`
- `boi_api/app/science/storage.py:1205-1211`
- `boi_api/app/science/storage.py:1529-1603`
- `tests/test_science_interpretation.py:1547-1613`

`ReviewedSourceURLProfile`, `SourceLookupIdentity`, and
`VerificationReport` verify internal equality and SHA-256 self-consistency.
Those hashes are integrity checks against accidental or partial corruption;
they are not attestations because a caller can recompute every one.

`ScienceRuntimeStore._validate_report_dependency_locked()` checks only the
stored confirmation/proposal chain and confirmed claims. It has no Catalog or
immutable release-ledger resolver and therefore does not verify that the
report's release digests, Source/Evidence IDs and digests, URL, or locator exist
in the selected released components. Normal load repeats the same limited
check. WAL semantic validation revalidates the same self-consistent report and
then calls the same dependency function.

The report model also does not require each annotation's `fact_id`,
`knowledge_id`, and Evidence links to equal the corresponding verdict
`explanation_facts`, `knowledge_refs`, and `evidence_refs`. The coordinated
probe changed the Evidence link to IDs that were not in Catalog while the
verdict retained its original references; validation still passed.

Independent direct-save/load probe, using a valid report as the starting point
and recomputing the profile and report digests:

```text
PROBE2_STORE_ACCEPTED_UNREVIEWED_URL=
https://unreviewed.example.test/replacement
```

Independent pending-WAL probe changed the same URL, recomputed the profile,
report, and audit-detail digests, removed the already published report, and
ran recovery:

```text
PROBE3_WAL_RECOVERED_UNREVIEWED_URL=
1 https://unreviewed.example.test/from-wal
```

A second direct Store probe coherently replaced every requested provenance
class. Save and reload accepted this result:

```text
COORDINATED_CATALOG_BYPASS={
  'release_digest': 'sha256:602d5bea7fb33ef2f53cf565410f538a375902d54b073128ea8f33330017b270',
  'release_set_digest': 'sha256:187c61aea963e50c41edce0b74c185d56730a3f4729051905cb6216d8cccc8f7',
  'source_id': 'sci:source:not-in-catalog',
  'evidence_id': 'sci:evidence:not-in-catalog',
  'locator_section': 'fabricated section 999'
}
```

The existing parameterized Store test changes one digest at a time. Even when
it recomputes the inner profile and outer report hashes, it intentionally
leaves at least one linked field inconsistent, so Pydantic rejects the partial
mutation. It does not test a coordinated replacement in which every
caller-controlled field and self-hash agrees.

Impact:

- Candidate or entirely unreviewed provenance can be serialized as `active`
  and persisted as an operational report.
- Report reload and WAL recovery prove only byte/self-hash consistency, not the
  claimed released provenance.
- The structural URL policy deliberately allows ordinary arbitrary path text
  and relies on release review for trust. Once release re-resolution is
  bypassed, a canonical URL containing credential-like bearer text can also be
  persisted. Reintroducing lexical secret guessing is not the fix.

Required closure:

1. Give Store save/load/WAL recovery access to an immutable Catalog/release
   resolver, or require a resolver-produced non-serializable capability at the
   write boundary and re-resolve the persisted snapshot at every read/recovery
   boundary. Historical/superseded releases may remain resolvable, but their
   exact manifests and component bytes must be authoritative.
2. Reconstruct the expected Source/Evidence/locator profile from the selected
   release and require exact equality. Never infer authority from
   `qualification_state == active` plus self-hashes.
3. Bind every `GroundedAnnotation` exactly to one verdict explanation fact and
   require exact Knowledge/Evidence reference coverage and released component
   digests.
4. Add coordinated adversarial matrices for direct Store save, private-file
   load, and WAL recovery. Each case must update all dependent fields and
   hashes together and still fail before publication.
5. Add a candidate-preview-to-report probe that recomputes every profile,
   link, report, and audit hash. The expected result is no report file and no
   operational Evidence link.

## Verified closed behavior

The following portions were independently inspected or exercised and are not
findings in this review:

- `ScienceCatalog._reviewed_source_url_profile()` requires exact pinned Source
  and Evidence components and copies their exact URL and locator.
- The normal `ScienceService._evidence_link()` path rechecks the issued profile
  against the exact release, pinned Evidence/Source objects, quote hash, ACL
  identity, URL, and locator.
- URL syntax validation is structural: canonical ASCII HTTPS, canonical
  hostname/path encoding, no userinfo, port, fragment, or arbitrary query. It
  does not use credential-word or entropy heuristics, and ordinary scientific
  path names remain usable.
- Direct construction without the issuer, mutation of an issued identity,
  copying, and pickle serialization are rejected.
- Existing closed-error probes for LLM settings/output, authoritative
  confirmation, Store save/load, and top-level/nested WAL Pydantic conversion
  passed. Their synthetic secret values were absent from cause, context,
  traceback, args, object dictionaries, and recursively serialized exception
  graphs.
- Partial corruption and noncanonical URLs fail closed. These checks are
  valuable but do not cover the coordinated authority substitutions above.

## Advisory findings

### A1. Rename the structural URL validator to match its real guarantee

`validate_credential_free_https_url()` now correctly states in its docstring
that release review supplies trust, but the function name still suggests it
can prove an arbitrary host/path contains no credential. A name such as
`validate_canonical_stable_https_url()` would make the division explicit:
syntax is structural; trust and secret review come from the exact released
Source identity.

### A2. The broad E/F/I Ruff command is not green under the available repository environment

`ruff 0.12.10` reports 132 `E501` line-length findings over the reviewed
production/test set when run with `--select E,F,I`. `ruff check --select F,I`,
compileall, and the implementation-commit `git diff --check` are green. This is
not an authority-boundary defect, but future reports should state the exact
Ruff version/configuration and should not claim the broad E/F/I command passes
unless it is reproducible.

## Fresh verification evidence

Focused implementation suites:

```text
TMPDIR=/home/chokukil/.cache \
PYTHONPATH=<cached PyYAML Python 3.12 site-packages> \
/home/chokukil/inv-platform/.venv/bin/python -m pytest -q -s \
  tests/test_science_interpretation.py \
  tests/test_science_storage.py \
  tests/test_science_catalog.py

959 passed in 27.79s
```

Complete Science regression:

```text
TMPDIR=/home/chokukil/.cache \
PYTHONPATH=<cached PyYAML Python 3.12 site-packages> \
/home/chokukil/inv-platform/.venv/bin/python -m pytest -q -s \
  tests/test_science*.py

1232 passed in 29.82s
```

Static checks:

```text
ruff check --select F,I <reviewed production and test files>
All checks passed!

python -m compileall -q boi_api/app/science \
  tests/test_science_interpretation.py \
  tests/test_science_catalog.py tests/test_science_storage.py

git diff --check 1f2ee56^..1f2ee56

# compileall and diff check produced no errors
```

The complete regression passing is not an acceptance result: the independent
coordinated probes above exercise authority substitutions absent from the test
suite and reproduce both Important findings.

No production or test code was modified. The only intended repository change
from this cross-review is this report.
