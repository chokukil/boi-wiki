# Science Verifier Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the typed, deterministic, release-pinned Science Verifier kernel and the `sci-profile` validation gate.

**Architecture:** Science knowledge remains OKF Markdown under `data/boi/public/science`, while a focused `boi_api.app.science` package loads immutable releases and evaluates allowlisted rule kinds. LLM output never enters the verdict evaluator directly: only a validated `ClaimPacket` and an explicit `ResolvedRelease` may be supplied to the pure `verify_claim` function.

**Tech Stack:** Python 3.12, Pydantic v2, PyYAML, Pint, pytest, existing OKF lint utilities

**Spec:** `docs/superpowers/specs/2026-08-25-science-verifier-design.md`

## Global Constraints

- `PrimaryVerdict` has exactly five values: `VIOLATION`, `CONSISTENT`, `INSUFFICIENT_INFORMATION`, `OUTSIDE_VALIDITY_DOMAIN`, `EMPIRICAL_VERIFICATION_REQUIRED`.
- `CONSISTENT` means consistent only with the evaluated rules and release scope; it never means true, safe, approved, or complete.
- Ontology and Dictionary references may interpret terms and retrieve candidates, but they never determine a verdict.
- A verdict must be a deterministic function of the canonical `ClaimPacket`, verifier version, and exact Foundation/Domain/Application release digests.
- Python `eval`, dynamic imports, arbitrary plugins, shell execution, embedding similarity, and LLM voting are forbidden in the verdict path.
- `knowledge_kind` and `assurance_basis` remain separate, and no scalar confidence score is permitted.
- Active release content is immutable; correction creates a new version and withdrawn content remains auditable.
- Document offsets use Unicode code points plus `exact`, `prefix`, and `suffix` anchors.
- Existing BoI ACL metadata remains mandatory; `sci-profile` extends rather than replaces `boi-profile`.
- Science authority is explicit: `science.admin` and domain-scoped `science.power_user:<domain>` are not implied by `boi.promoter` or generic `boi.admin`.

---

### Task 1: Typed packets and canonical digests

**Files:**
- Create: `boi_api/app/science/__init__.py`
- Create: `boi_api/app/science/models.py`
- Create: `boi_api/app/science/digests.py`
- Test: `tests/test_science_models.py`
- Modify: `boi_api/requirements.txt`

**Interfaces:**
- Consumes: Pydantic v2 and JSON-serializable values.
- Produces: the complete stored/runtime models below, `canonical_json_bytes(value)`, and `sha256_digest(value)`.

- [ ] **Step 1: Add the runtime unit dependency and write failing packet tests**

```python
from boi_api.app.science.digests import canonical_json_bytes, sha256_digest
from boi_api.app.science.models import ClaimPacket, PrimaryVerdict


def test_primary_verdict_is_closed_and_claim_digest_is_stable():
    assert {item.value for item in PrimaryVerdict} == {
        "VIOLATION", "CONSISTENT", "INSUFFICIENT_INFORMATION",
        "OUTSIDE_VALIDITY_DOMAIN", "EMPIRICAL_VERIFICATION_REQUIRED",
    }
    packet = ClaimPacket.model_validate(CLAIM_FIXTURE)
    assert sha256_digest(packet) == sha256_digest(packet.model_dump(mode="json"))
    assert canonical_json_bytes({"b": 1, "a": 2}) == b'{"a":2,"b":1}'
```

Add `pint>=0.25,<1` to `boi_api/requirements.txt`.

- [ ] **Step 2: Run the focused tests and confirm the import failure**

Run: `pytest tests/test_science_models.py -q`

Expected: FAIL because `boi_api.app.science.models` does not exist.

- [ ] **Step 3: Implement closed enums and strict packets**

```python
class PrimaryVerdict(str, Enum):
    VIOLATION = "VIOLATION"
    CONSISTENT = "CONSISTENT"
    INSUFFICIENT_INFORMATION = "INSUFFICIENT_INFORMATION"
    OUTSIDE_VALIDITY_DOMAIN = "OUTSIDE_VALIDITY_DOMAIN"
    EMPIRICAL_VERIFICATION_REQUIRED = "EMPIRICAL_VERIFICATION_REQUIRED"


class SourceSpan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    offset_encoding: Literal["unicode_code_point"] = "unicode_code_point"
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    exact: str = Field(min_length=1)
    prefix: str = ""
    suffix: str = ""

    @model_validator(mode="after")
    def valid_range(self) -> "SourceSpan":
        if self.end <= self.start or self.end - self.start != len(self.exact):
            raise ValueError("source span does not match Unicode code-point length")
        return self
```

`NormalizedClaim` contains `subject_concept_id: str`, `relation_kind: RelationKind`, `predicate: str`, `object_concept_id: str`, `polarity: Literal["positive", "negative"]`, `quantities: list[ClaimQuantity]`, `conditions: list[ClaimCondition]`, `process_stage: str | None`, and `material_state: str | None`. `ClaimPacket` contains `claim_id`, `document_ref`, `document_digest`, `source_span`, `normalized_claim`, and an `interpretation: ClaimInterpretation` with `ontology_refs`, `ambiguity_ids`, and `user_confirmed`.

Define the remaining interfaces exactly:

```python
class ConversionKind(str, Enum):
    MULTIPLICATIVE = "multiplicative"
    AFFINE = "affine"
    LOGARITHMIC = "logarithmic"
    PROCEDURE_DEFINED = "procedure_defined"

class RuleKind(str, Enum):
    DIRECTIONAL_RELATION = "directional_relation"
    EQUATION_CONSTRAINT = "equation_constraint"
    DIMENSION_CONSTRAINT = "dimension_constraint"
    VALIDITY_DOMAIN = "validity_domain"
    EMPIRICAL_BOUNDARY = "empirical_boundary"

class PackRelationKind(str, Enum):
    DEPENDS_ON = "depends_on"
    USES = "uses"
    SPECIALIZES = "specializes"
    ADDS_EVIDENCE = "adds_evidence"
    VALIDATED_BY = "validated_by"
    SUPERSEDES = "supersedes"

class ReleaseSelection(BaseModel):
    foundation: str
    domains: list[str] = Field(default_factory=list)
    applications: list[str] = Field(default_factory=list)

class ResolvedComponent(BaseModel):
    ref: str
    kind: Literal["source", "evidence", "knowledge", "rule", "ontology_binding", "qualification_matrix", "pack"]
    declared_digest: str
    actual_digest: str

class ResolvedRelease(BaseModel):
    release_id: str
    schema_version: Literal["sci-profile/0.1"]
    content_hash: str
    status: Literal["release_candidate", "active", "superseded", "withdrawn"]
    components: tuple[ResolvedComponent, ...]
    component_digests: dict[str, str]
    known_limitations: list[str]

class RuleEvaluation(BaseModel):
    rule_id: str
    applicability: Literal["IN_SCOPE", "MISSING_CONDITIONS", "OUTSIDE_DOMAIN", "EMPIRICAL_ONLY", "NOT_APPLICABLE"]
    outcome: Literal["CONTRADICTS", "SUPPORTS", "UNDECIDED"]
    reason_codes: list[str]
    condition_evaluations: list[ConditionEvaluation]
    knowledge_refs: list[str]
    evidence_refs: list[str]

class InterpretationRecord(BaseModel):
    interpretation_id: str
    document_digest: str
    candidate_claims: list[ClaimPacket]
    model_id: str
    model_settings: dict[str, str | int | float | bool]
    prompt_version: str
    dictionary_release_id: str
    ontology_release_id: str
    ontology_refs: list[str]
    candidate_meanings: list[dict[str, Any]]
    decision_impact: list[dict[str, Any]]
    user_revision_history: list[dict[str, Any]]
    confirmed_claim_packet_digest: str | None
    response_digest: str

class VerificationReport(BaseModel):
    report_id: str
    document_ref: str | None
    document_digest: str
    release_selection: ReleaseSelection
    release_digests: dict[str, str]
    interpretation_ids: list[str]
    verdict_packets: list[VerdictPacket]
    unresolved_ambiguities: list[dict[str, Any]]
    annotations: list[dict[str, Any]]
    created_at: datetime
    created_by: str
    report_digest: str
```

All contracts use `extra="forbid"`. Add reusable fixtures under `tests/fixtures/science/claims.json`, `tests/fixtures/science/releases/`, and `tests/fixtures/science/rules/`; tests load named entries rather than relying on undefined module constants.

- [ ] **Step 4: Implement canonical serialization without timestamps or secrets**

```python
def canonical_json_bytes(value: Any) -> bytes:
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json", exclude_none=False)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sha256_digest(value: Any) -> str:
    return "sha256:" + hashlib.sha256(canonical_json_bytes(value)).hexdigest()
```

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_science_models.py -q`

Expected: PASS.

```bash
git add boi_api/app/science boi_api/requirements.txt tests/test_science_models.py
git commit -m "feat: add Science Verifier packet contracts"
```

### Task 2: `sci-profile` validation and cross-reference gate

**Files:**
- Create: `boi_api/app/science/profile.py`
- Modify: `boi_api/app/okf.py`
- Test: `tests/test_science_profile.py`

**Interfaces:**
- Consumes: parsed OKF metadata and a `Path` inside the BoI root.
- Produces: `is_science_document(metadata) -> bool`, `validate_sci_profile_metadata(metadata) -> list[str]`, and science errors included by `lint_markdown_file`.

- [ ] **Step 1: Write failing validation tests for each stored object kind**

```python
def test_science_knowledge_requires_evidence_and_disallows_confidence():
    metadata = valid_science_knowledge_metadata()
    metadata["science"]["confidence"] = 0.93
    errors = validate_sci_profile_metadata(metadata)
    assert "science.confidence is forbidden" in errors
    del metadata["science"]["evidence_refs"]
    errors = validate_sci_profile_metadata(metadata)
    assert "science.evidence_refs is required" in errors
```

Cover source, evidence, knowledge, rule, pack, qualification case, and release profiles, plus mismatch between OKF `source_refs` and `science.evidence_refs`.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `pytest tests/test_science_profile.py -q`

Expected: FAIL because the validator does not exist.

- [ ] **Step 3: Implement object-kind-specific required fields**

```python
SCIENCE_TYPE_REQUIREMENTS = {
    "boi/science-source": {"source_id", "source_role", "original_url", "content_hash"},
    "boi/science-evidence": {"evidence_id", "source_id", "locator", "original_text", "original_text_hash", "reviewed_translation"},
    "boi/science-knowledge": {"knowledge_id", "pack_id", "knowledge_kind", "assurance_basis", "statement", "assumptions", "applicability", "limitations", "evidence_refs"},
    "boi/science-rule": {"rule_id", "pack_id", "rule_kind", "inputs", "outcomes", "knowledge_refs", "evidence_refs"},
    "boi/science-pack": {"pack_id", "version", "dependencies", "knowledge_refs", "rule_refs", "qualification_refs"},
    "boi/science-ontology-binding": {"binding_id", "ontology_release_id", "concept_id", "aliases", "meaning", "domain"},
    "boi/science-qualification-matrix": {"matrix_id", "rule_id", "cases", "release_refs"},
    "boi/science-release": {"release_id", "schema_version", "content_hash", "status", "component_digests", "known_limitations", "components", "qualification_report"},
}
```

Validate `knowledge_kind` and `assurance_basis` against the exact spec lists, forbid `confidence`, require public source URLs to use HTTPS, and check `original_text_hash` against the actual UTF-8 evidence span.

- [ ] **Step 4: Wire validation into existing OKF lint only for Science types**

```python
errors = (
    validate_okf_core_metadata(metadata)
    + validate_boi_profile_metadata(metadata)
    + validate_boi_profile_path_acl(metadata, path, boi_root)
    + validate_sci_profile_metadata(metadata)
)
```

- [ ] **Step 5: Run lint tests and commit**

Run: `pytest tests/test_science_profile.py tests/test_okf_lint.py -q`

Expected: PASS.

```bash
git add boi_api/app/science/profile.py boi_api/app/okf.py tests/test_science_profile.py
git commit -m "feat: validate Science OKF profiles"
```

### Task 3: Immutable catalog and explicit release resolver

**Files:**
- Create: `boi_api/app/science/catalog.py`
- Create: `boi_api/app/science/exceptions.py`
- Test: `tests/test_science_catalog.py`

**Interfaces:**
- Consumes: `Path` pointing at the BoI root (`repo/data/boi`), release IDs/selections, and OKF Science documents.
- Produces: `ScienceCatalog(boi_root)`, `resolve_release(release_id)`, `resolve_release_set(selection)`, `active_release()`, `source(id)`, `evidence(id)`, `knowledge(id)`, `rule(id)`, `ontology_binding(id)`, `pack(id)`, `pack_by_name(name)`, `qualification_matrix(id)`, `qualification_cases(rule_id)`, `qualification_cases_for_pack(pack_id)`, and `claim_fixture(case_id)`.

- [ ] **Step 1: Write failing catalog tests with a temporary Science tree**

```python
def test_release_resolver_rejects_digest_drift(science_tree):
    catalog = ScienceCatalog(science_tree)
    resolved = catalog.resolve_release("sci-release:0.1.0")
    assert resolved.release_id == "sci-release:0.1.0"
    science_tree.joinpath("public/science/rules/rule.md").write_text("changed", encoding="utf-8")
    with pytest.raises(ScienceCatalogError, match="component digest mismatch"):
        ScienceCatalog(science_tree).resolve_release("sci-release:0.1.0")
```

Also test zero active releases, multiple active releases, a withdrawn active pointer, broken refs, duplicate science IDs, and deterministic ordering.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_science_catalog.py -q`

Expected: FAIL because `ScienceCatalog` does not exist.

- [ ] **Step 3: Implement indexed loading and byte-stable component digests**

```python
class ScienceCatalog:
    def __init__(self, boi_root: Path):
        self.science_root = boi_root / "public" / "science"
        self._objects = self._load_objects()

    def resolve_release(self, release_id: str) -> ResolvedRelease:
        release = self._require("release", release_id)
        components = tuple(self._resolve_component(ref) for ref in release.components)
        for component in components:
            if component.declared_digest != component.actual_digest:
                raise ScienceCatalogError(f"component digest mismatch: {component.ref}")
        return ResolvedRelease.from_components(release, components)
```

Compute each component digest from normalized metadata plus body, excluding mutable filesystem timestamps. Never follow arbitrary paths from frontmatter; resolve only indexed science IDs.

- [ ] **Step 4: Implement safe active/withdrawn selection**

`active_release()` returns exactly one `active` release. If the active release is withdrawn, it returns the latest declared `last_safe_release_id`; absence of a safe release raises `ScienceOperationalError` and never falls back to a candidate.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_science_catalog.py tests/test_science_profile.py -q`

Expected: PASS.

```bash
git add boi_api/app/science/catalog.py boi_api/app/science/exceptions.py tests/test_science_catalog.py
git commit -m "feat: resolve immutable Science releases"
```

### Task 4: Deterministic unit and rule engine

**Files:**
- Create: `boi_api/app/science/units.py`
- Create: `boi_api/app/science/rules.py`
- Create: `boi_api/app/science/engine.py`
- Test: `tests/test_science_engine.py`

**Interfaces:**
- Consumes: `ClaimPacket`, `ResolvedRelease`, and allowlisted `VerificationRule` objects.
- Produces: `validate_quantity(quantity)`, `evaluate_rule(rule, claim) -> RuleEvaluation`, and `verify_claim(claim, release, verifier_version="science-verifier/0.1.0") -> VerdictPacket`.

- [ ] **Step 1: Write failing tests for all five verdicts and false-red protection**

```python
@pytest.mark.parametrize(("case_id", "expected"), [
    ("spin-rpm-increase-thickness-increase", "VIOLATION"),
    ("ohm-voltage-current-fixed-resistance", "CONSISTENT"),
    ("boiling-point-pressure-omitted", "INSUFFICIENT_INFORMATION"),
    ("ideal-gas-condensed-phase", "OUTSIDE_VALIDITY_DOMAIN"),
    ("unqualified-device-lifetime", "EMPIRICAL_VERIFICATION_REQUIRED"),
])
def test_primary_verdict_cases(qualified_catalog, case_id, expected):
    case = qualified_catalog.qualification(case_id)
    packet = verify_claim(case.claim_packet, qualified_catalog.resolve(case.release_refs))
    assert packet.verdict.value == expected


def test_different_conditions_do_not_create_false_violation(qualified_catalog):
    packet = qualified_catalog.claim("spin-different-resist-viscosity")
    assert verify_claim(packet, qualified_catalog.active_release()).verdict.value == "INSUFFICIENT_INFORMATION"
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_science_engine.py -q`

Expected: FAIL because the evaluator does not exist.

- [ ] **Step 3: Implement unit parsing with a locked registry**

```python
ureg = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)


def normalized_quantity(value: Decimal, unit: str) -> NormalizedQuantity:
    quantity = ureg.Quantity(value, unit).to_base_units()
    return NormalizedQuantity(
        magnitude=Decimal(str(quantity.magnitude)),
        unit=f"{quantity.units:~}",
        dimensionality=str(quantity.dimensionality),
    )
```

Reject undefined units, NaN, infinity, and dimensionally incompatible comparisons. Unit parsing must not load definitions from user-controlled files.

- [ ] **Step 4: Implement a closed rule-kind dispatcher**

```python
RULE_EVALUATORS: dict[RuleKind, RuleEvaluator] = {
    RuleKind.DIRECTIONAL_RELATION: evaluate_directional_relation,
    RuleKind.EQUATION_CONSTRAINT: evaluate_equation_constraint,
    RuleKind.DIMENSION_CONSTRAINT: evaluate_dimension_constraint,
    RuleKind.VALIDITY_DOMAIN: evaluate_validity_domain,
    RuleKind.EMPIRICAL_BOUNDARY: evaluate_empirical_boundary,
}


def evaluate_rule(rule: VerificationRule, claim: NormalizedClaim) -> RuleEvaluation:
    return RULE_EVALUATORS[rule.rule_kind](rule, claim)
```

Each evaluation reports matched concepts, compared conditions, applicability, outcome, reason codes, knowledge refs, and evidence refs. Unknown rule kinds are validation errors, never dynamically executed.

- [ ] **Step 5: Implement precedence and grounded packet construction**

Use this precedence: unresolved decision-changing ambiguity stops before the engine; missing coverage or required conditions → `INSUFFICIENT_INFORMATION`; explicit validity mismatch → `OUTSIDE_VALIDITY_DOMAIN`; empirical-only question without qualified observation → `EMPIRICAL_VERIFICATION_REQUIRED`; only an `IN_SCOPE` evaluation with every decision-changing condition satisfied may produce deterministic contradiction → `VIOLATION` or checked support → `CONSISTENT`. Build `corrected_claim` only for an in-scope deterministic contradiction. Every `explanation_fact` must have at least one release-resolved Knowledge ref and Evidence ref.

Add this non-negotiable regression:

```python
def test_contradiction_candidate_cannot_override_missing_conditions_or_domain():
    missing = verify_claim(claim_fixture("spin-stage-missing"), release_fixture())
    outside = verify_claim(claim_fixture("newtonian-model-shear-thinning"), release_fixture())
    assert missing.verdict is PrimaryVerdict.INSUFFICIENT_INFORMATION
    assert outside.verdict is PrimaryVerdict.OUTSIDE_VALIDITY_DOMAIN
    assert not missing.corrected_claim and not outside.corrected_claim
```

- [ ] **Step 6: Prove byte stability and commit**

Run: `pytest tests/test_science_models.py tests/test_science_profile.py tests/test_science_catalog.py tests/test_science_engine.py -q`

Expected: PASS, including an assertion that two runs produce identical `canonical_json_bytes(VerdictPacket)`.

```bash
git add boi_api/app/science/units.py boi_api/app/science/rules.py boi_api/app/science/engine.py tests/test_science_engine.py
git commit -m "feat: add deterministic scientific rule engine"
```
