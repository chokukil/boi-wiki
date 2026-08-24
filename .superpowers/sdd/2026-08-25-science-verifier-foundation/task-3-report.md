# Science Verifier Foundation — Task 3 Report

## Scope completed

- Added `ScienceCatalog`, rooted strictly at `<boi_root>/public/science`; it indexes only recognized Science frontmatter documents and resolves stored IDs without following frontmatter paths.
- Added canonical component digests from normalized frontmatter and normalized Markdown body, independent of filesystem timestamps and frontmatter key order.
- Added immutable, defensive-copy accessors for Source, Evidence, Knowledge, Rule, Ontology Binding, Pack, Qualification Matrix, Qualification Cases, and Claim fixtures.
- Added fail-closed Release resolution: exact manifest/component agreement, indexed-component checks, digest verification, deterministic component/release/case ordering, and duplicate-ID/reference rejection.
- Added explicit active-release selection. Exactly one pointer is required; a withdrawn explicit pointer may use only its declared non-candidate, non-withdrawn `last_safe_release_id`.

## RED evidence

1. Wrote `tests/test_science_catalog.py` with literal temporary Science documents before either catalog module existed. Each test names its protected break: digest drift, path-like ID lookup, case/release ordering, missing or multiple active releases, withdrawn-pointer safety, broken references, and duplicate IDs.
2. The requested command initially hit this WSL session's inherited Windows temporary-directory capture teardown (`FileNotFoundError`) before collection. Re-ran with capture disabled to expose the real RED result:

   ```bash
   pytest tests/test_science_catalog.py -q -s
   ```

   Result: `9 failed`; each failure was `ModuleNotFoundError: No module named 'boi_api.app.science.catalog'`.
3. Added the stale explicit-pointer test before changing its branch and ran:

   ```bash
   pytest tests/test_science_catalog.py::test_explicit_active_pointer_rejects_a_nonactive_nonwithdrawn_release -q -s
   ```

   Result: failed because the catalog returned a superseded release instead of raising an operational error.
4. Added the cross-kind duplicate-ID test before changing indexing and ran its node. Result: failed because the same ID was accepted as both a Source and a Rule.
5. Added the defensive-copy test before changing public accessors and ran its node. Result: failed because mutating a returned Rule changed the catalog's next lookup.

## GREEN evidence

1. Implemented the indexed catalog and its `ScienceCatalogError` / `ScienceOperationalError` boundaries without adding any path-resolution API.
2. Ran the requested regression command with a Linux temporary directory, which avoids the unrelated pytest capture teardown defect:

   ```bash
   TMPDIR=/tmp pytest tests/test_science_catalog.py tests/test_science_profile.py -q
   ```

   Result: `36 passed in 0.29s`.
3. Ran neighboring Science model contracts as an additional regression:

   ```bash
   TMPDIR=/tmp pytest tests/test_science_models.py tests/test_science_profile.py tests/test_science_catalog.py -q
   ```

   Result: `40 passed in 0.29s`.
4. Ran `python -m compileall -q boi_api/app/science` and `git diff --check`; both exited successfully with no output.

## Self-review and boundaries

- A changed component with still-valid identity produces the exact `component digest mismatch` failure. A component that disappears or loses its Science identity fails closed as an unknown component/reference, never as an implicit file fallback.
- Every component reference is resolved from the catalog's ID index. Mapping component entries accept only `ref`; arbitrary `path` data is never interpreted.
- Release component and digest-map keys must be identical. A Release may be resolved for qualification while it is a candidate, but it cannot become the operational active release by accident.
- The catalog does not validate a Release's declared `content_hash`: this task's release contract pins and verifies every component digest, while `content_hash` remains the immutable manifest value carried by `ResolvedRelease` for the later release-qualification task.
- Mutation check: changing a body, changing the active-state branch, accepting an ID collision, using a dangling component, making cases/filesystem traversal order observable, or exposing the stored mutable object is caught by the catalog tests.

## Fix Round 1

### RED evidence

1. Added a standard-library-only digest oracle to `tests/test_science_catalog.py`. It canonicalizes literal fixture metadata with `json.dumps(sort_keys=True, separators=(",", ":"))` and SHA-256; it does not call catalog internals or `sha256_digest`.
2. Added tests before production changes for all Release-manifest mutations (`status`, `known_limitations`, `qualification_report`, components/digests, and body), a fixed literal manifest digest, metadata-key reordering, malformed OKF/BoI/ACL documents, coexistence of an explicit and status-active marker, valid withdrawn fallback, and a dangling safe-release ID.
3. Ran:

   ```bash
   TMPDIR=/tmp pytest tests/test_science_catalog.py -q
   ```

   Result: `12 failed, 14 passed in 0.65s`. The failures were the intended missing safeguards: every mutated Release resolved, malformed BoI metadata was indexed, an explicit marker hid a status-active Release, and a missing safe Release leaked `ScienceCatalogError` rather than operational unavailability.

### GREEN evidence

1. Release resolution now first verifies `science.content_hash` against canonical normalized metadata plus body after removing only `science.content_hash`; all other manifest fields and the body remain pinned.
2. Catalog indexing now calls the existing OKF core, BoI profile, path/ACL, and Science profile validators with the real document path and constructor BoI root before inserting any Science object.
3. Active selection counts the union of `science.active: true` and `science.status: active`, so neither marker can mask another. A lone status-active Release still works; a withdrawn marker can resolve only its declared safe non-candidate/non-withdrawn Release.
4. Missing safe-release IDs now become `ScienceOperationalError` with the unavailable ID.
5. Ran the required regression command:

   ```bash
   TMPDIR=/tmp pytest tests/test_science_catalog.py tests/test_science_profile.py tests/test_science_models.py -q
   ```

   Result: `54 passed in 0.52s`.
6. Ran `python -m compileall -q boi_api/app/science` and `git diff --check`; both exited successfully with no output.
