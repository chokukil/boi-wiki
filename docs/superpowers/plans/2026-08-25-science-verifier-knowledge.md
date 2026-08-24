# Science Verifier Knowledge Packs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Curate a versioned, source-grounded v0.1 Science Release spanning common scientific reasoning, physics, chemistry, circuits, materials, semiconductor devices, and Spin Coating as one application proof.

**Architecture:** Each public OKF Science document represents one reviewed object and carries both `boi-profile` and `sci-profile`. Small Evidence Spans link authoritative sources to atomic Knowledge; allowlisted Rules consume that Knowledge; every rule has ten public qualification variants, while an external sealed holdout manifest preserves independent evaluation.

**Tech Stack:** OKF Markdown/YAML, existing OKF link graph, Science catalog and deterministic engine, pytest, a qualification CLI

**Spec:** `docs/superpowers/specs/2026-08-25-science-verifier-design.md`

## Global Constraints

- The active release must contain all `SCI-COM-001` through `SCI-COM-012` topics and all six Domain/Application Packs named by the spec.
- Spin Coating may specialize common Physics, Chemistry, and Materials rules but may not introduce a special verdict path.
- Every decision rule has ten cases: clear violation, in-scope consistency, missing required condition, outside validity domain, empirical verification required, negation, unit variation, decision-changing ambiguity, paraphrase, and false-red prevention.
- Each Evidence Span stores official URL/DOI, source version, stable locator, short original text, reviewed Korean translation, exact-text hash, and contextual limitations.
- Evidence text remains a minimal span; source files and paid books are not copied into Git.
- MIT OCW, Feynman, IUPAC, BIPM/JCGM, NIST/NASA, Chenming Hu, AIP articles, and vendor TDS are represented with access and licensing caveats.
- Atkins and Agarwal/Lang may appear in the Source Ledger only when a lawfully accessible internal copy and locator are available; v0.1 verdicts may not depend on an inaccessible span.
- OpenStax is not used as runtime LLM evidence without a separate permission decision because the current site publishes an LLM-ingestion restriction.
- Source count or popularity never resolves a conflict; identical subject, conditions, range, measurement state, and incompatible outcome must be reviewed explicitly.
- General-purpose holdouts across units, metrology, chemistry, circuits, materials, and devices must outnumber Spin-Coating-only holdouts.

---

### Task 1: Source Ledger and reviewed Evidence Spans

**Files:**
- Create: `data/boi/public/science/index.md`
- Create: `data/boi/public/science/sources/index.md`
- Create: `data/boi/public/science/sources/bipm-si-brochure-9-v4-01.md`
- Create: `data/boi/public/science/sources/jcgm-vim-3-2012.md`
- Create: `data/boi/public/science/sources/nist-tn-1297.md`
- Create: `data/boi/public/science/sources/nasa-std-7009b.md`
- Create: `data/boi/public/science/sources/nist-statistics-handbook.md`
- Create: `data/boi/public/science/sources/iupac-gold-book.md`
- Create: `data/boi/public/science/sources/feynman-lectures.md`
- Create: `data/boi/public/science/sources/mit-8-01sc.md`
- Create: `data/boi/public/science/sources/mit-2-25.md`
- Create: `data/boi/public/science/sources/mit-5-111.md`
- Create: `data/boi/public/science/sources/chem1-virtual-textbook.md`
- Create: `data/boi/public/science/sources/mit-6-002.md`
- Create: `data/boi/public/science/sources/all-about-circuits.md`
- Create: `data/boi/public/science/sources/mit-3-091.md`
- Create: `data/boi/public/science/sources/mit-3-012.md`
- Create: `data/boi/public/science/sources/mit-3-024.md`
- Create: `data/boi/public/science/sources/mit-6-012.md`
- Create: `data/boi/public/science/sources/chenming-hu-devices.md`
- Create: `data/boi/public/science/sources/emslie-1958.md`
- Create: `data/boi/public/science/sources/meyerhofer-1978.md`
- Create: `data/boi/public/science/sources/merck-az-125nxt-01-24.md`
- Create: `data/boi/public/science/evidence/index.md`
- Create: `data/boi/public/science/evidence/common/{quantity-unit-dimension,celsius-kelvin,measurand-result,uncertainty-error,accuracy-precision,repeatability-reproducibility,model-validity,correlation-causation,steady-state,equilibrium,system-balance}.md`
- Create: `data/boi/public/science/evidence/physics/{rotation-angular-speed,force-momentum,work-energy-power,viscosity-flow,control-volume-flux}.md`
- Create: `data/boi/public/science/evidence/chemistry/{amount-concentration,substance-phase,evaporation-vapor-pressure,reaction-equilibrium,catalyst-kinetics}.md`
- Create: `data/boi/public/science/evidence/circuits/{kcl-kvl,ohm-model,electric-power,series-parallel,capacitor-inductor,measurement-loading}.md`
- Create: `data/boi/public/science/evidence/materials/{structure-grain,defects-microstructure,phase-transformation,diffusion-arrhenius,bulk-thin-film}.md`
- Create: `data/boi/public/science/evidence/semiconductor-devices/{bands-fermi-level,carrier-conductivity,drift-diffusion,pn-junction,mos-capacitor,transistor-operating-region}.md`
- Create: `data/boi/public/science/evidence/spin-coating/{emslie-model,meyerhofer-model,vendor-spin-curve}.md`
- Create: `data/boi/public/science/source-evidence-ledger-v0.1.yaml`
- Test: `tests/test_science_source_ledger.py`

**Interfaces:**
- Consumes: official source URLs and the Science profile validator.
- Produces: `sci-source:*` and `sci-evidence:*` objects referenced by all later Knowledge.

- [ ] **Step 1: Write failing ledger tests**

```python
def test_every_ledger_evidence_has_a_reviewed_okf_span(science_root):
    ledger = yaml.safe_load((science_root / "source-evidence-ledger-v0.1.yaml").read_text())
    catalog = ScienceCatalog(science_root.parents[1])
    for item in ledger["evidence"]:
        evidence = catalog.evidence(item["evidence_id"])
        assert evidence.source_id == item["source_id"]
        assert evidence.original_text_hash == "sha256:" + hashlib.sha256(evidence.original_text.encode()).hexdigest()
        assert evidence.reviewed_translation.strip()
        assert evidence.locator.section or evidence.locator.page or evidence.locator.equation or evidence.locator.term_id
```

Also assert HTTPS/DOI original links, retrieval date, content hash, source version, access/license note, no source body copied into Git, and every Evidence original span is short enough to remain contextual rather than a substitute for the source.

- [ ] **Step 2: Run tests and confirm the missing ledger**

Run: `pytest tests/test_science_source_ledger.py -q`

Expected: FAIL because the Science source tree does not exist.

- [ ] **Step 3: Curate official source records**

Use these canonical starting points and record exact redirected URLs and checksums after retrieval: BIPM SI Brochure DOI `10.59161/AUEZ1291`, JCGM VIM DOI `10.59161/JCGM200-2012`, NIST TN 1297, NASA-STD-7009B, NIST/SEMATECH e-Handbook, IUPAC Gold Book term DOIs, MIT OCW course pages, Feynman Lectures official site, Chem1, All About Circuits, Chenming Hu official downloads, Emslie DOI `10.1063/1.1723300`, Meyerhofer DOI `10.1063/1.325357`, and Merck AZ 125nXT TDS revision `01/24`.

- [ ] **Step 4: Author short Evidence objects with exact locators**

PDF locators include printed page, PDF page index, section/equation/figure, and document checksum. HTML locators include heading/term ID, sentence ordinal, retrieval date, exact/prefix/suffix, and page checksum. A translation may not be stronger than the original sentence. Emslie/Meyerhofer verdict evidence remains inactive if the lawful full-text locator cannot be reviewed; a vendor curve remains a product-scoped rule only.

- [ ] **Step 5: Run source checks and commit**

Run: `pytest tests/test_science_source_ledger.py tests/test_science_profile.py -q`

Run: `python scripts/okf_lint.py --root data --strict-links --strict-media`

Expected: PASS with no broken Science source/evidence link.

```bash
git add data/boi/public/science tests/test_science_source_ledger.py
git commit -m "docs: add reviewed Science source ledger"
```

### Task 2: General Science Foundation and 12 common qualification matrices

**Files:**
- Create: `data/boi/public/science/knowledge/common/index.md`
- Create: `data/boi/public/science/ontology-bindings/common/{quantity,unit,dimension,measurement-error,measurement-uncertainty,accuracy,precision,model,steady-state,equilibrium,correlation,causation}.md`
- Create: `data/boi/public/science/knowledge/common/sci-com-001.md` through `sci-com-012.md`
- Create: `data/boi/public/science/rules/common/index.md`
- Create: `data/boi/public/science/rules/common/r-com-001.md` through `r-com-012.md`
- Create: `data/boi/public/science/qualification/cases/common/q-com-001.md` through `q-com-012.md` as `boi/science-qualification-matrix` objects
- Create: `data/boi/public/science/packs/science-foundation.md`
- Test: `tests/test_science_foundation_pack.py`

**Interfaces:**
- Consumes: reviewed Evidence IDs from Task 1.
- Produces: Pack `sci-pack:science-foundation/0.1.0`, Knowledge `sci:common:001..012`, Rules `sci-rule:common:001..012`, and 120 public qualification cases.

- [ ] **Step 1: Write failing completeness and behavioral tests**

```python
def test_foundation_has_twelve_topics_and_ten_cases_per_rule(science_catalog):
    pack = science_catalog.pack("sci-pack:science-foundation/0.1.0")
    assert pack.rule_refs == [f"sci-rule:common:{n:03d}" for n in range(1, 13)]
    for rule_id in pack.rule_refs:
        cases = science_catalog.qualification_cases(rule_id)
        assert {case.case_kind for case in cases} == REQUIRED_TEN_CASE_KINDS
```

Behavioral assertions include Celsius/Kelvin affine conversion, uncertainty versus error, accuracy versus precision, repeatability versus reproducibility, model validity, open-system balance, steady state versus equilibrium, controlled-variable directional claims, and correlation versus causation.

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_science_foundation_pack.py -q`

Expected: FAIL because the pack is absent.

- [ ] **Step 3: Author the 12 atomic Knowledge and Rules**

Use the exact spec topics `SCI-COM-001..012`. Each Knowledge document states one claim, definitions, assumptions, applicability, limitations, `invalid_outside`, related Knowledge, and Evidence roles. Each Rule uses one of the closed evaluator kinds and names required conditions explicitly. Common Ontology Binding objects map Korean/English aliases to one concept, declare meaning and domain, and record terms that are close but must not be collapsed; they support interpretation only and are pinned into the Release.

- [ ] **Step 4: Author ten cases per common rule**

Each `q-com-NNN.md` is one explicit `QualificationMatrix` container with `matrix_id`, `rule_id`, `release_refs`, and ten structured `cases`. Every nested case has `case_id`, `case_kind`, complete `claim_packet`, `expected_verdict` or `expected_gate: ambiguity_gate`, rationale, and expected Evidence path. No case may be an assertion-only duplicate; paraphrase and negation must exercise interpretation-normalized claims, and false-red cases must differ in condition or validity range.

- [ ] **Step 5: Run qualification and commit**

Run: `pytest tests/test_science_foundation_pack.py tests/test_science_engine.py -q`

Expected: PASS for all 120 public cases.

```bash
git add data/boi/public/science/knowledge/common data/boi/public/science/rules/common data/boi/public/science/qualification/cases/common data/boi/public/science/packs/science-foundation.md tests/test_science_foundation_pack.py
git commit -m "docs: add General Science Foundation pack"
```

### Task 3: Domain and application packs

**Files:**
- Create: `data/boi/public/science/knowledge/{physics,chemistry,circuits,materials,semiconductor-devices,spin-coating}/index.md`
- Create: `data/boi/public/science/ontology-bindings/domain/{angular-speed,viscosity,catalyst,equilibrium-constant,resistance,electric-power,bulk-property,thin-film-property,semiconductor,mobility,conductivity,spin-speed,film-thickness,photoresist}.md`
- Create: `data/boi/public/science/rules/{physics,chemistry,circuits,materials,semiconductor-devices,spin-coating}/index.md`
- Create: `data/boi/public/science/qualification/cases/{physics,chemistry,circuits,materials,semiconductor-devices,spin-coating}/index.md`
- Create: `data/boi/public/science/packs/physical-principles.md`
- Create: `data/boi/public/science/packs/chemical-principles.md`
- Create: `data/boi/public/science/packs/circuit-principles.md`
- Create: `data/boi/public/science/packs/materials-science.md`
- Create: `data/boi/public/science/packs/semiconductor-devices.md`
- Create: `data/boi/public/science/packs/spin-coating.md`
- Test: `tests/test_science_domain_packs.py`

**Interfaces:**
- Consumes: Foundation Pack and reviewed domain Evidence.
- Produces: five Physics, five Chemistry, six Circuit, five Materials, six Semiconductor, and five Spin-Coating Rules, their atomic Knowledge, and 320 public cases.

- [ ] **Step 1: Write failing pack dependency and cross-domain tests**

```python
EXPECTED_RULE_COUNTS = {
    "physical-principles": 5,
    "chemical-principles": 5,
    "circuit-principles": 6,
    "materials-science": 5,
    "semiconductor-devices": 6,
    "spin-coating": 5,
}

def test_domain_packs_depend_on_foundation_without_override(science_catalog):
    for name, count in EXPECTED_RULE_COUNTS.items():
        pack = science_catalog.pack_by_name(name)
        assert len(pack.rule_refs) == count
        assert "override" not in pack.model_dump_json()
        assert len(science_catalog.qualification_cases_for_pack(pack.pack_id)) == count * 10
```

Assert fixed-voltage versus fixed-current resistor power, catalyst versus equilibrium constant, bulk versus thin-film properties, doping/mobility/conductivity, ideal versus real MOS gate current, and ambiguous/wrong/in-scope Spin-Coating claims.

- [ ] **Step 2: Run tests and confirm missing packs**

Run: `pytest tests/test_science_domain_packs.py -q`

Expected: FAIL because the domain packs are absent.

- [ ] **Step 3: Author 27 domain Rules and Knowledge objects**

Use rule IDs `sci-rule:physics:001..005`, `chemistry:001..005`, `circuits:001..006`, `materials:001..005`, and `semiconductor-devices:001..006`. Encode validity and required conditions rather than broad `influences` edges. Domain Ontology Bindings expose aliases, broader/narrower distinctions, stage/state candidates, and decision impact but no outcome direction. Application-independent cases must demonstrate all five verdicts before Spin Coating is added.

- [ ] **Step 4: Author five Spin-Coating specialization Rules**

Rules cover process/measurement state, Emslie assumptions, evaporation-aware model limits, vendor-curve scope, and equipment-specific empirical boundaries. The clear contradiction case is valid only when final coat spin, the same resist/viscosity/solids/spin time/environment, dry/post-bake measurement state, and qualified curve range are confirmed. No Rule returns an RPM setting, percentage change, DOE starting point, or recipe recommendation.

- [ ] **Step 5: Author ten cases per Rule and prove generality**

At least 270 of the 320 new public cases are non-Spin cases. Include unit variants, negations, paraphrases, condition changes, and ideal-model extrapolation traps. The same engine and rule kinds must process all packs.

- [ ] **Step 6: Run all pack tests and commit**

Run: `pytest tests/test_science_foundation_pack.py tests/test_science_domain_packs.py tests/test_science_engine.py -q`

Expected: PASS for 440 public qualification cases in total.

```bash
git add data/boi/public/science/knowledge data/boi/public/science/rules data/boi/public/science/qualification/cases data/boi/public/science/packs tests/test_science_domain_packs.py
git commit -m "docs: add scientific domain and application packs"
```

### Task 4: Release candidate, independent holdout contract, and preflight report

**Files:**
- Create: `data/boi/public/science/qualification/holdouts/manifest.md`
- Create: `data/boi/public/science/releases/science-release-0.1.0.md`
- Create: `scripts/qualify_science_release.py`
- Create: `tests/test_science_release_qualification.py`
- Generate: `data/boi/public/science/qualification/reports/release-gate-preflight-science-release-0.1.0.md`

**Interfaces:**
- Consumes: all v0.1 Source/Evidence/Knowledge/Rule/Pack/case objects plus optional external holdout JSON named by environment.
- Produces: preflight results for `G0..G4`, explicit pending results for `G5..G7`, case-level actual/expected verdicts, error inventories, exact component digests, and one immutable `release_candidate`. Activation is deliberately deferred until Web/MCP/Harness/independent holdout work exists.

- [ ] **Step 1: Write failing release-gate tests**

```python
def test_release_preflight_has_no_compensating_score(qualification_result):
    assert list(qualification_result.gates) == [f"G{n}" for n in range(8)]
    assert qualification_result.aggregate_score is None
    assert qualification_result.gates["G5"].status == "PENDING"
    assert qualification_result.gates["G6"].status == "PENDING"
    assert qualification_result.gates["G7"].status == "PENDING"
    assert qualification_result.broken_evidence_locators == []
    assert qualification_result.false_red_cases == []
    assert qualification_result.ungrounded_explanation_facts == []
    assert qualification_result.nondeterministic_cases == []
```

Also assert exact pack dependencies using the closed `PackRelationKind` enum, 440 public cases, holdout manifest digest/ACL URL/count, no unresolved conflict, and report inventory of missed violations, wrong interpretations, range errors, and unsupported scope.

- [ ] **Step 2: Run tests and confirm missing release runner**

Run: `pytest tests/test_science_release_qualification.py -q`

Expected: FAIL because the release and runner do not exist.

- [ ] **Step 3: Implement the qualification CLI**

The CLI accepts `--boi-root`, `--release-id`, optional `--holdout-path`, and `--output`. It runs profile/reference/hash gates, evaluates each public case twice for deterministic byte identity, validates Evidence paths and Rule grounding, and exits nonzero when `G0..G4` fails. Missing sealed data is `G5 PENDING`; absent Web/MCP is `G6 PENDING`; absent final actor approval is `G7 PENDING`. Any pending gate prevents activation but does not invalidate local public regression checks.

- [ ] **Step 4: Create the sealed-holdout manifest and release candidate**

The manifest stores external ACL URL, SHA-256, reviewer role, rule-freeze commit, domain distribution, and at least two cases per rule. The actual claims and expected verdicts remain outside the development tree until qualification. The release candidate pins all component IDs and digests, declares supported/partial/unsupported scopes, known limitations, and `last_safe_release_id`.

- [ ] **Step 5: Run public preflight and keep the Release inactive**

Run: `python scripts/qualify_science_release.py --boi-root data/boi --release-id sci-release:0.1.0 --output data/boi/public/science/qualification/reports/release-gate-preflight-science-release-0.1.0.md`

Expected: `G0..G4` PASS, `G5..G7` PENDING, release status remains `release_candidate`, and zero false-red, broken locator, ungrounded rule, and nondeterminism in public cases.

- [ ] **Step 6: Run lint/tests and commit**

Run: `pytest tests/test_science_release_qualification.py tests/test_science_foundation_pack.py tests/test_science_domain_packs.py -q`

Run: `python scripts/okf_lint.py --root data --include-logs --strict-links --strict-media`

Expected: PASS.

```bash
git add data/boi/public/science/qualification data/boi/public/science/releases scripts/qualify_science_release.py tests/test_science_release_qualification.py
git commit -m "feat: qualify Science release 0.1.0"
```
