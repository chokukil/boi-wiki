# Science Verifier Agent Integration and Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make external Codex/Claude agents use the canonical Science Verifier through REST/MCP, document safe curation workflows, and prove Web/REST/MCP/report parity without creating a BoI-owned scientific agent.

**Architecture:** FastMCP tools remain thin API adapters and expose typed packets unchanged. Two small skills bootstrap user agents and curators into the API and four mirrored harnesses define Source, Knowledge, Rule, and end-to-end verification gates; final scripts exercise the running system and produce a user-readable failure report.

**Tech Stack:** FastMCP, httpx, Markdown skills/harnesses, pytest, Node CDP browser checks, Python integration scripts

**Spec:** `docs/superpowers/specs/2026-08-25-science-verifier-design.md`

## Global Constraints

- BoI Wiki must not provide a new autonomous Science agent; user-owned agents call REST or MCP.
- MCP contains no rule engine, retrieval verdict, citation synthesis, or LLM fallback; it returns the API packet unchanged.
- External-agent skills contain workflow and safety instructions, not embedded scientific truths.
- Mutating MCP tools require explicit `user_confirmed: true` and preserve the caller identity; a service-token admin identity may not silently approve curation.
- User Agent output must preserve BoI verdict labels and limitations and must not upgrade `CONSISTENT` into true/safe/approved.
- General users can retrieve decisive public original Evidence, reviewed translation, locator, and source URL.
- Web, REST, MCP, Markdown, and PDF share claim IDs, verdicts, release pins, evidence IDs, and report digest.
- Existing OKF/SOP/Inbox/Action behavior and DB-less core remain regression requirements.

---

### Task 1: Thin MCP tools and capability groups

**Files:**
- Modify: `boi_wiki_mcp/app/main.py`
- Modify: `tests/test_boi_wiki_mcp.py`
- Modify: `scripts/check_boi_wiki_mcp.py`

**Interfaces:**
- Consumes: `/api/science/*` REST endpoints.
- Produces: `science_interpret`, `science_interpretation_confirm`, `science_verify_claim`, `science_verify_document`, `science_evidence_get`, `science_report_get`, `science_report_export`, `science_proposal_create`, `science_source_validate`, `science_evidence_validate`, `science_knowledge_validate`, `science_rule_qualify`, `science_release_validate`, `science_release_activate`, and `science_release_withdraw`.

- [ ] **Step 1: Write failing MCP parity tests**

```python
@pytest.mark.asyncio
async def test_science_verify_claim_is_a_thin_api_adapter(monkeypatch, mcp_module):
    expected = {"verdict": "VIOLATION", "claim_packet_digest": "sha256:a", "evidence_refs": ["sci-evidence:x"]}
    async def fake_post(path, **kwargs):
        assert path == "/api/science/claims/claim:x/verify"
        assert kwargs["payload"]["claim_packet"]["claim_id"] == "claim:x"
        return expected
    monkeypatch.setattr(mcp_module, "api_post", fake_post)
    assert await mcp_module.science_verify_claim("claim:x", CLAIM_PACKET, RELEASES) == expected
```

Cover all 15 tools, capability list, `Science Verifier` IA group, bridge dispatch, explicit confirmation, and identity preservation. Replace brittle exact total-count assertions with required-tool set assertions plus a minimum count.

- [ ] **Step 2: Run tests and confirm missing tools**

Run: `pytest tests/test_boi_wiki_mcp.py -q`

Expected: FAIL because Science tools are absent.

- [ ] **Step 3: Add capability metadata and wrappers**

Each wrapper calls `api_get` or `api_post` exactly once. Export returns base64 plus content type only when the MCP transport cannot return binary content; packet metadata and digest stay unchanged.

- [ ] **Step 4: Extend the HTTP MCP bridge safely**

Add the Science tools to `MCP_TOOL_IA_GROUPS` and `mcp_bridge_call()`. Read-only service-token calls remain possible. Outcome-changing ambiguity uses the explicit `science_interpretation_confirm` tool; proposal review remains Web/REST-only. Release activation and withdrawal wrappers require an authenticated caller mapping and must reject a service-token-only identity. Keep `user_confirmed` visible in the payload.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_boi_wiki_mcp.py -q`

Run: `python scripts/check_boi_wiki_mcp.py`

Expected: PASS and all 15 Science tools appear.

```bash
git add boi_wiki_mcp/app/main.py tests/test_boi_wiki_mcp.py scripts/check_boi_wiki_mcp.py
git commit -m "feat: expose Science Verifier MCP tools"
```

### Task 2: User Agent and curator skills

**Files:**
- Create: `skills/boi-science-verifier/SKILL.md`
- Create: `skills/boi-science-curator/SKILL.md`
- Modify: `skills/boi-wiki-agent/SKILL.md`
- Test: `tests/test_science_skills.py`

**Interfaces:**
- Consumes: Science REST/MCP tool contracts and harness documents.
- Produces: installable thin instructions for external user agents and Science curators.

- [ ] **Step 1: Write failing skill-contract tests**

```python
def test_verifier_skill_cannot_override_boi_verdict(repo_root):
    text = (repo_root / "skills/boi-science-verifier/SKILL.md").read_text()
    assert "science_interpret" in text and "science_verify_document" in text
    assert "BoI가 반환한 Verdict를 변경하지 않는다" in text
    assert "자체 지식으로 Citation" in text
    assert "VIOLATION" in text and "CONSISTENT" in text
```

Assert that the curator skill requires separate proposer/reviewer, supports Power User domain boundaries, reserves law/equation/evidence/rule/release changes for Admin, and does not contain domain facts or source excerpts.

- [ ] **Step 2: Run tests and confirm missing skills**

Run: `pytest tests/test_science_skills.py -q`

Expected: FAIL because the skills do not exist.

- [ ] **Step 3: Author `boi-science-verifier`**

Startup sequence: resolve relevant Dictionary/Ontology terms, call `science_interpret`, ask only outcome-changing ambiguity, resubmit the corrected Claim, call `science_verify_document`, display BoI verdict/limitations and source links, and retrieve detailed Evidence on demand. It must treat service outage as unavailable verification and must not answer from agent memory as a substitute.

- [ ] **Step 4: Author `boi-science-curator` and update the parent skill**

The curator follows Source → Evidence → Knowledge → Rule → Qualification → Release Candidate, uses the four harnesses, creates proposals only, and never approves its own output. The parent BoI skill routes scientific fact checking to the new verifier skill without duplicating its full rules.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_science_skills.py -q`

Expected: PASS.

```bash
git add skills/boi-science-verifier/SKILL.md skills/boi-science-curator/SKILL.md skills/boi-wiki-agent/SKILL.md tests/test_science_skills.py
git commit -m "docs: add Science Verifier agent skills"
```

### Task 3: Source, Knowledge, Rule, and Verification harnesses

**Files:**
- Create: `harness/science-source-curation-harness.md`
- Create: `harness/science-knowledge-authoring-harness.md`
- Create: `harness/science-rule-qualification-harness.md`
- Create: `harness/science-verification-harness.md`
- Create: `data/boi/public/harness/science-source-curation-harness.md`
- Create: `data/boi/public/harness/science-knowledge-authoring-harness.md`
- Create: `data/boi/public/harness/science-rule-qualification-harness.md`
- Create: `data/boi/public/harness/science-verification-harness.md`
- Modify: `harness/README.md`
- Modify: `harness/harness-responsibility-matrix.md`
- Modify: `data/boi/public/harness/index.md`
- Test: `tests/test_science_harnesses.py`

**Interfaces:**
- Consumes: Science profile, release gates, role boundaries, and runtime packet contracts.
- Produces: mirrored operational checklists used by repository workers and external agents.

- [ ] **Step 1: Write failing mirror and coverage tests**

```python
@pytest.mark.parametrize("name", [
    "science-source-curation-harness.md", "science-knowledge-authoring-harness.md",
    "science-rule-qualification-harness.md", "science-verification-harness.md",
])
def test_repo_and_public_harness_rules_match(repo_root, name):
    repo_text = normalize_harness((repo_root / "harness" / name).read_text())
    public_text = normalize_harness((repo_root / "data/boi/public/harness" / name).read_text())
    assert repo_text in public_text
```

Check for G0–G7, exact locator/hash/translation review, ten case kinds, all five verdicts, false-red, span anchoring, Web/REST/MCP parity, Markdown/PDF parity, and role/self-approval requirements.

- [ ] **Step 2: Run tests and confirm missing harnesses**

Run: `pytest tests/test_science_harnesses.py -q`

Expected: FAIL because the files do not exist.

- [ ] **Step 3: Author the four repository harnesses**

Each harness has Purpose, Inputs, Observation, Context, Control, Action, State, Verification, Failure Artifacts, and release-blocking conditions. Source Curation covers official source/version/checksum/span; Knowledge Authoring covers atomic claims/conditions/limits; Rule Qualification covers deterministic evaluator and 10-case matrix; Verification covers exact spans, explanation grounding, evidence visibility, parity, and exports.

- [ ] **Step 4: Create public OKF mirrors and navigation**

Public mirrors include valid BoI frontmatter, reviewer, source refs, and links to Science objects. Keep the normative body synchronized and add the four entries to both responsibility matrices and harness indexes.

- [ ] **Step 5: Run harness and lint tests, then commit**

Run: `pytest tests/test_science_harnesses.py -q`

Run: `python scripts/okf_lint.py --root data --strict-links --strict-media`

Expected: PASS.

```bash
git add harness data/boi/public/harness tests/test_science_harnesses.py
git commit -m "docs: add Science Verifier harnesses"
```

### Task 4: End-to-end qualification, failure report, and regression verification

**Files:**
- Create: `scripts/check_science_verifier.py`
- Create: `scripts/check_science_llm_live.py`
- Create: `scripts/capture_science_evidence.mjs`
- Create: `tests/test_science_end_to_end.py`
- Modify: `README.md`
- Modify: `data/boi/public/boi-wiki-manual/guide/final-operator-guide.md`
- Generate: `artifacts/science-verifier/qualification-report.md`
- Generate: `artifacts/science-verifier/qualification-report.pdf`
- Generate: `artifacts/science-verifier/verification-manifest.json`
- Generate: `artifacts/science-verifier/deck/assets/review-canvas-desktop.png`
- Generate: `artifacts/science-verifier/deck/assets/review-canvas-mobile.png`
- Generate: `artifacts/science-verifier/deck/assets/final-qualification-report.png`
- Generate: `artifacts/science-verifier/deck/assets/capture-manifest.json`

**Interfaces:**
- Consumes: running BoI API/MCP, the inactive v0.1 Release candidate, public qualification cases, and an independently authored sealed holdout file created after the Rule-freeze commit.
- Produces: parity evidence, a human-readable success/failure report, and final verification manifest with command outputs and digests.

- [ ] **Step 1: Write failing end-to-end parity tests**

```python
def test_spin_and_general_claims_have_rest_mcp_report_parity(science_system):
    for fixture in ["spin-rpm-wrong", "celsius-affine", "circuit-fixed-v", "catalyst-equilibrium", "bulk-thin-film", "mos-ideal-real"]:
        rest = science_system.verify_rest(fixture)
        mcp = science_system.verify_mcp(fixture)
        report = science_system.report(rest["report_id"])
        assert mcp["verdict_packets"] == rest["verdict_packets"]
        assert report["report_digest"] == rest["report_digest"]
```

Also cover missed violation, false-red, wrong interpretation, outside-domain, empirical-required, broken Evidence, unsupported scope, persistence after application reload, and unchanged historic report bytes after a newer release becomes active or the current release is withdrawn.

- [ ] **Step 2: Run tests and confirm missing checker**

Run: `pytest tests/test_science_end_to_end.py -q`

Expected: FAIL because the integration checker does not exist.

- [ ] **Step 3: Freeze Rules and commission the independent holdout**

Record the current commit as `rule_freeze_commit`. A separate reviewer agent receives the design spec, public Source/Evidence/Knowledge IDs, Claim Packet schema, and domain scope, but is not given the Rule source or public qualification cases. After the freeze it writes the actual holdout JSON only to the ACL-controlled path in untracked `SCIENCE_HOLDOUT_PATH`, with at least two cases per Rule and more non-Spin than Spin cases. Store only its SHA-256, case counts, domain distribution, reviewer identity, and freeze commit in the tracked holdout manifest. Any later Rule change invalidates this holdout and requires a new independent set.

- [ ] **Step 4: Implement the checker and report inventory**

The checker calls the public REST and MCP interfaces rather than importing the engine. It asks the Admin validation API to run `G0..G7` using the rule-frozen sealed holdout and confirms every gate passes for the exact inactive Release Candidate. It must not synthesize approval events or activate the candidate. Activation is tested separately with authorization fixtures; an operational Release can activate only after a human Admin has reviewed the original material and exact object digests. The checker writes case ID, claim text, expected/actual verdict, decisive Rule, Evidence URLs, limitations, interpretation refs, and classification into the report. It has explicit sections for detected errors, missed errors, false-red, interpretation errors, validity errors, broken locators, ungrounded explanations, changed Knowledge/Rules, and regression tests. No aggregate trust score is emitted.

The final report of record is `artifacts/science-verifier/qualification-report.{md,pdf}`. It embeds the digest of `data/boi/public/science/qualification/reports/release-gate-preflight-science-release-0.1.0.md`; the preflight document is not presented as the final result. Automated tests extract claim/verdict/Evidence/release/report identifiers from Markdown and PDF and require equality.

- [ ] **Step 5: Document operation and internal LLM setup**

README and operator guide explain the new menu, access mode, role assignment, Science runtime volume, MCP tools, report exports, release activation/withdrawal, and external agent skills. Show environment variable names and a local example without committing the internal LM Studio URL or credentials.

- [ ] **Step 6: Exercise the configured Qwen interpreter without trusting its verdict**

Load the untracked workspace `.env` and run `python scripts/check_science_llm_live.py --require-live-llm --expected-model qwen/qwen3.8-27b`. The script calls the OpenAI-compatible `/v1/chat/completions` endpoint through `ScienceLLMClient` and submits at least one cross-domain claim and the Spin-Coating claim. It asserts that the actual response model resolves to `qwen/qwen3.8-27b`, JSON validates as an interpretation candidate, and the response contains no verdict, Evidence ID, locator, or citation fields. Feed the validated candidate through the deterministic API and record only sanitized model ID, non-secret settings, prompt version, Dictionary/Ontology Release, response digest, HTTP timing, Claim Packet digest, release digest, and Verdict Packet digest in `verification-manifest.json`; never record endpoint or credentials. Failure is release-blocking.

- [ ] **Step 7: Capture real UI and final-report evidence**

Run the server with the exact validated candidate pinned in Admin preview mode, or with a separately human-reviewed active Release, and the live stored report; then execute `node scripts/capture_science_evidence.mjs`. It must use the real `/science-verifier` route, not fixture HTML, and save the exact desktop/mobile/report paths listed in this Task. `capture-manifest.json` records viewport, timestamp, Git commit, report ID/digest, Release ID/digest, lifecycle state, and URL path with host/credentials removed. The script fails if the violation span, source links, scientific explanation, final report digest, or candidate/active label is absent.

- [ ] **Step 8: Run the complete verification matrix**

Run narrow checks first, then:

```bash
pytest tests -q -s
python scripts/okf_lint.py --root data --include-logs --strict-links --strict-media
python scripts/check_science_llm_live.py --require-live-llm --expected-model qwen/qwen3.8-27b
python scripts/check_science_verifier.py
python scripts/check_boi_wiki_mcp.py
node scripts/check_science_verifier_ui.mjs
```

Expected: all commands exit 0; qualification report shows zero missed required violation, zero false-red, zero broken decisive Evidence locator, zero ungrounded decision Rule/explanation, and exact REST/MCP/export packet parity.

- [ ] **Step 9: Inspect generated artifacts and commit documentation**

Open the Markdown and PDF reports and compare their claim IDs, verdicts, evidence IDs, release IDs, and digest. Record actual command timestamps, Git commit, release digest, model ID used only for interpretation, and browser dimensions in `verification-manifest.json`.

```bash
git add scripts/check_science_verifier.py scripts/check_science_llm_live.py scripts/capture_science_evidence.mjs tests/test_science_end_to_end.py README.md data/boi/public/boi-wiki-manual/guide/final-operator-guide.md artifacts/science-verifier
git commit -m "test: verify Science Verifier end to end"
```
