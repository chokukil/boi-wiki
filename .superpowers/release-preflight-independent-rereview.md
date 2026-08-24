# Science Release Preflight Independent Re-review

- Review date: 2026-08-25 (Asia/Seoul)
- Reviewed fix: `46b441da50f5300af6081c623cb716b90b376075`
- Review mode: read-only product review; exact commit also tested from an isolated archive
- Result: **PASS**
- Critical: **0**
- Important: **0**
- Advisory: **1**

The two prior release-normality bypasses are closed. A copied BoI tree whose
Evidence locator contains only `{"junk": "x"}` is rejected before the candidate
builder can repin it. A copied tree whose Source declares
`content_hash: sha256:deadbeef` is rejected at the same boundary. The G1
inventory independently flags both malformed states, while the unmodified
candidate still contains 50 valid Evidence objects and 440 passing public
qualification cases.

## Critical findings

None.

## Important findings

None.

## Authority-path review

### Candidate construction fails before repinning invalid provenance

Locations:

- `scripts/build_science_release_candidate.py:55-66`
- `boi_api/app/science/catalog.py:197-239`
- `boi_api/app/science/profile.py:305-338`
- `boi_api/app/science/profile.py:365-379`

`build_candidate()` constructs a fresh `ScienceCatalog` before it calculates
or writes any component digest map. Catalog loading runs
`validate_sci_profile_metadata()` for every Science object and raises on any
profile error. Consequently a malformed Evidence locator or short Source hash
cannot be normalized into a new candidate manifest.

The isolated probes produced:

```text
MALFORMED_LOCATOR_RETURN_CODE= 1
MALFORMED_LOCATOR_REJECTED_WITH_EXPECTED_ERROR= True
... science.locator must be a closed medium-specific Evidence locator

SHORT_SOURCE_HASH_RETURN_CODE= 1
SHORT_SOURCE_HASH_REJECTED_WITH_EXPECTED_ERROR= True
... science.content_hash must be an exact SHA-256 digest
```

The probes copied the complete `data/boi` tree, changed only the specified
frontmatter field, and invoked the real candidate-builder subprocess. Neither
copy produced a repinned Release.

### One closed locator validator covers PDF, HTML, and API JSON

Locations:

- `boi_api/app/science/profile.py:122-151`
- `boi_api/app/science/profile.py:305-338`
- `boi_api/app/science/models.py:20-23`
- `boi_api/app/science/models.py:758-801`

`validate_evidence_locator()` first validates through the closed
`EvidenceLocator` model (`extra="forbid"`). It then requires the shared URL,
hash, retrieval-time, and hash-scope fields plus the exact medium-specific
location fields:

- PDF: `section`, `pdf_page_index`, and `printed_page`;
- HTML: `heading`, `sentence_ordinal`, `prefix`, `suffix`, and
  `retrieved_resource_hash`;
- API JSON: `section`, `field_path`, and `record_path`.

All three URL identities must be present, URL syntax is validated by the typed
model, `resource_url` must equal `resolved_url`, `exact` must be true, and hash
fields must be full lowercase `sha256:<64 hex>` identities.

An independent 50-check matrix started from one real locator of each medium
and removed every required field in turn. It also tried an unknown field, a
short content hash, HTTP resource URL, missing requested URL, mismatched
resource/resolved URLs, and `exact=false`:

```text
MEDIUM_VALIDATOR_CHECKS= 50
MEDIUM_VALIDATOR_FAILURES= []
MEDIUM_VALIDATOR_BASES= ['api_json', 'html', 'pdf']
```

### G1 uses the same locator validator and rejects short Source hashes

Locations:

- `boi_api/app/science/qualification.py:21-24`
- `boi_api/app/science/qualification.py:131-157`
- `boi_api/app/science/qualification.py:307-329`

G1's `_structurally_broken_evidence()` calls the same imported
`validate_evidence_locator()` used by the profile/Catalog path. It additionally
requires every linked Source content hash to match a complete SHA-256 identity
and recomputes each Evidence original-text hash.

Direct G1 inventory probes produced:

```text
G1_CLEAN_BROKEN= []
G1_JUNK_LOCATOR_FLAGGED= True
G1_SHORT_SOURCE_HASH_LINKED_COUNT= 2
G1_SHORT_SOURCE_HASH_ALL_LINKED_FLAGGED= True
```

Thus the builder boundary and the qualification inventory independently reject
the two previous malformed states.

## Normal-corpus regression

The clean isolated copy was rebuilt with the real candidate builder and then
qualified:

```text
CLEAN_BUILDER_RETURN_CODE= 0
CLEAN_EVIDENCE_COUNT= 50
CLEAN_LOCATOR_FAILURES= {}
CLEAN_MEDIUM_COUNTS= {'api_json': 2, 'html': 7, 'pdf': 41}
CLEAN_PUBLIC_CASE_COUNT= 440
CLEAN_G0_G4= ['PASS', 'PASS', 'PASS', 'PASS', 'PASS']
CLEAN_BROKEN_EVIDENCE= []
CLEAN_ACTIVATION_ELIGIBLE= False
```

The result remains candidate-only: G5-G7 are pending and activation remains
false. This review does not represent human review, approval, qualification, or
Release activation.

## Advisory findings

### A1. Share the Source hash predicate as well as the locator validator

The locator policy is correctly shared between profile validation and G1.
The full Source SHA-256 requirement currently has equivalent but duplicated
implementations: `_SHA256_PATTERN` in `profile.py` and an inline `re.fullmatch`
in `qualification.py`. They agree now and every probe passes, so this is not an
Important defect. A small shared `validate_source_content_hash()` predicate
would prevent a future profile/G1 drift.

## Fresh verification

Focused profile and release qualification:

```text
pytest -q -s tests/test_science_profile.py \
  tests/test_science_release_qualification.py
59 passed in 11.32s
```

Relevant profile, release, domain, ledger, and Catalog regression:

```text
pytest -q -s tests/test_science_profile.py \
  tests/test_science_release_qualification.py \
  tests/test_science_domain_packs.py \
  tests/test_science_source_ledger.py tests/test_science_catalog.py
164 passed in 33.01s
```

Exact `46b441d` archive, all 15 Science test files present at that commit:

```text
EXACT_46B_TEST_FILE_COUNT= 15
EXACT_46B_FULL_SCIENCE_RETURN_CODE= 0
1328 passed in 67.24s
```

OKF and static checks:

```text
python scripts/okf_lint.py --root data --include-logs \
  --strict-media --strict-links
OKF lint checked 477 markdown docs and 0 log materialized items;
found 731 markdown graph links and 25 markdown image links.
OKF lint passed

ruff 0.12.10 check --select F,I <five files changed by 46b441d>
All checks passed!

python -m compileall -q <changed Python files>
git diff --check 46b441d^..46b441d
# no errors
```

No production or test code was modified. The only intended repository change
from this re-review is this report.
