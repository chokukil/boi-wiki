# Science Verifier Application Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose the deterministic kernel through a fail-closed interpretation service, role-safe REST API, document-centered UI, and reproducible reports.

**Architecture:** A router factory receives existing BoI identity, ACL, shell, and role callbacks so the Science package never imports the monolithic `main.py`. The LLM creates only validated claim candidates and explanation prose; the server verifies spans, pins releases, runs the kernel, and stores immutable runtime records before rendering Web, Markdown, or PDF views from one report model.

**Tech Stack:** FastAPI, Jinja2, vanilla JavaScript, httpx, Pydantic v2, ReportLab, pytest, FastAPI TestClient

**Spec:** `docs/superpowers/specs/2026-08-25-science-verifier-design.md`

> **계획 이력 보정(2026-08-25):** 아래 checkbox는 당시의 구현 순서를 보존한다. Qwen의 실연결, 특정 모델의 응답, context 크기 또는 튜닝은 완료·Candidate qualification·Release activation의 조건이 아니다. Qwen은 선택적 실험 해석기이며, 실패해도 LLM 없는 결정론적 경로가 계속 동작해야 한다.

## Global Constraints

- The Science Verifier is a review canvas, not a chat room and not a BoI-owned agent.
- Web interpretation may inherit `BOI_SCIENCE_LLM_*` from `BOI_LLM_*` only when the optional experiment is enabled; endpoint credentials never appear in reports or tracked files.
- LLM failure or schema failure returns an interpretation error and never fabricates a claim, verdict, evidence locator, or citation.
- Only `VIOLATION` receives red shading and underline; only outcome-changing ambiguity receives a purple dotted underline.
- One or two decisive source links remain visible on every correction card; original text, translation, locator, and ontology references are expandable for ordinary users with source access.
- Reports contain no aggregate trust score and no DOE or process-change recommendation.
- User correction changes only the current interpretation; global improvement requires a proposal and never mutates an active release.
- Power User approval is domain-scoped, cannot approve their own proposal, and only moves an interpretation/term/concept-link proposal into a release candidate.
- Laws, equations, models, evidence, rules, final activation, and withdrawal require `science.admin`.
- Markdown and PDF exports render the same immutable `VerificationReport`; neither format recomputes a verdict or asks an LLM to rewrite it.

---

### Task 1: Science authorization and persistent runtime storage

**Files:**
- Create: `boi_api/app/science/authorization.py`
- Create: `boi_api/app/science/storage.py`
- Test: `tests/test_science_authorization.py`
- Test: `tests/test_science_storage.py`
- Modify: `boi_api/app/auth.py`

**Interfaces:**
- Consumes: `AuthIdentity`, full resolved role list, `BOI_SCIENCE_ACCESS_MODE`, and `SCIENCE_RUNTIME_ROOT`.
- Produces: `ScienceAuthorization`, `ScienceRuntimeStore`, immutable `save_interpretation`, `save_report`, `save_proposal`, `approve_proposal`, and `append_audit` methods.

- [ ] **Step 1: Write failing role and self-approval tests**

```python
def test_boi_admin_does_not_imply_science_admin():
    authz = ScienceAuthorization(access_mode="admin_only")
    identity = AuthIdentity(employee_id="7", display_name="generic", roles=["boi.admin"])
    assert not authz.can_access(identity, roles=identity.roles)


def test_power_user_cannot_approve_own_proposal(runtime_store, lithography_power_user):
    proposal = runtime_store.save_proposal(actor="100002", domain="lithography", kind="term_alias", payload={"alias": "PR"})
    with pytest.raises(ScienceAuthorizationError, match="self-approval"):
        runtime_store.approve_proposal(proposal.proposal_id, actor="100002", roles=lithography_power_user.roles)
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_science_authorization.py tests/test_science_storage.py -q`

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement explicit Science roles and pilot access**

Add `science.admin` to the configured development admin identity and `science.power_user:lithography` to the development power-user identity. Do not add fallback logic from `boi.admin`.

```python
def require_admin(self, identity: AuthIdentity, roles: Sequence[str]) -> None:
    if "science.admin" not in set(roles):
        raise ScienceAuthorizationError("science.admin role required")

def power_user_domains(roles: Sequence[str]) -> set[str]:
    return {role.split(":", 1)[1] for role in roles if role.startswith("science.power_user:")}
```

`admin_only` permits only `science.admin`; `pilot` also permits domain-scoped Power Users and `science.user`; `open` permits authenticated BoI viewers for verification but preserves curation restrictions.

- [ ] **Step 4: Implement atomic, immutable JSON storage**

Write each record to a temporary file in the destination directory, `fsync`, then `os.replace`. If an ID exists with different canonical bytes, raise an immutable-record error. Audit rows are append-only JSONL and exclude API keys and endpoint credentials.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_science_authorization.py tests/test_science_storage.py -q`

Expected: PASS.

```bash
git add boi_api/app/science/authorization.py boi_api/app/science/storage.py boi_api/app/auth.py tests/test_science_authorization.py tests/test_science_storage.py
git commit -m "feat: add Science runtime authorization and storage"
```

### Task 2: Fail-closed LLM interpretation and span anchoring

**Files:**
- Create: `boi_api/app/science/anchors.py`
- Create: `boi_api/app/science/llm.py`
- Create: `boi_api/app/science/service.py`
- Test: `tests/test_science_interpretation.py`

**Interfaces:**
- Consumes: document text or an ACL-resolved Wiki document, optional selection anchor, Science catalog interpretation index, and OpenAI-compatible configuration.
- Produces: `resolve_anchor(text, span)`, `ScienceLLMClient.interpret(...)`, and `ScienceService.interpret_document(...)`, `verify_claim(...)`, `verify_document(...)`.

- [ ] **Step 1: Write failing tests for Unicode anchors, ambiguity, and LLM failure**

```python
def test_anchor_uses_unicode_code_points_and_rejects_stale_document():
    text = "웨이퍼😀에서 RPM을 높이면 두께가 증가한다."
    span = make_span(text, "RPM을 높이면 두께가 증가한다")
    assert resolve_anchor(text, span).exact.startswith("RPM")
    with pytest.raises(SpanAnchorError, match="anchor mismatch"):
        resolve_anchor(text.replace("증가", "감소"), span)


def test_invalid_llm_json_does_not_create_claim(fake_llm, science_service):
    fake_llm.response = "not-json"
    with pytest.raises(ScienceInterpretationUnavailable):
        science_service.interpret_document("RPM과 두께의 관계를 검증해줘")
```

- [ ] **Step 2: Run tests and confirm failure**

Run: `pytest tests/test_science_interpretation.py -q`

Expected: FAIL because anchoring and interpretation services do not exist.

- [ ] **Step 3: Implement unique anchor resolution**

First verify `text[start:end] == exact` and prefix/suffix. If offsets fail, search `prefix + exact + suffix`; accept only one match and return newly calculated Unicode code-point offsets. Multiple or zero matches require re-interpretation and must never attach an old red mark.

- [ ] **Step 4: Implement strict OpenAI-compatible extraction**

Use `POST {base_url}/chat/completions` with model inherited as follows: `BOI_SCIENCE_LLM_BASE_URL` → `BOI_LLM_BASE_URL`, `BOI_SCIENCE_LLM_MODEL` → `BOI_LLM_MODEL`, and `BOI_SCIENCE_LLM_API_KEY` → `BOI_LLM_API_KEY`. The system prompt includes the JSON schema and states that verdicts, citations, evidence IDs, and source locators are forbidden outputs. Parse only the assistant content as JSON and validate it with Pydantic.

- [ ] **Step 5: Implement service orchestration and grounded explanations**

`interpret_document` stores model ID, prompt version, ontology refs, ambiguity impact, and document digest when the optional adapter is used. Its unavailability is an interpretation-unavailable result, not a verification failure. `verify_claim` resolves the exact release before calling the pure engine. `verify_document` verifies confirmed, unambiguous claims, stores unresolved ambiguity without a verdict, then assembles scientific explanation paragraphs only from `VerdictPacket.explanation_facts`. Server code injects evidence links from the catalog after generation and rejects sentences with no fact mapping.

The stored `InterpretationRecord` must also persist non-secret model settings, Dictionary Release ID, Ontology Release ID, candidate meanings, per-candidate decision impact, user revision history, confirmed Claim Packet digest, and raw-response digest. Release-pinned `OntologyBinding` objects supply only candidate meanings and may not appear in a `RuleEvaluation` outcome.

- [ ] **Step 6: Run tests and commit**

Run: `pytest tests/test_science_interpretation.py tests/test_science_engine.py -q`

Expected: PASS.

```bash
git add boi_api/app/science/anchors.py boi_api/app/science/llm.py boi_api/app/science/service.py tests/test_science_interpretation.py
git commit -m "feat: add fail-closed scientific claim interpretation"
```

### Task 3: REST router, report exports, and release management

**Files:**
- Create: `boi_api/app/science/routes.py`
- Create: `boi_api/app/science/reports.py`
- Modify: `boi_api/app/main.py`
- Modify: `boi_api/requirements.txt`
- Modify: `.env.example`
- Modify: `.env.local-full.example`
- Modify: `docker-compose.yml`
- Test: `tests/test_science_api.py`

**Interfaces:**
- Consumes: injected `current_identity`, `roles_for`, `access_policy_for_doc`, `app_shell_context`, `templates`, data/runtime roots, and LLM configuration.
- Produces: `/api/science/*`, `/science-verifier`, Markdown export, PDF export, proposal review, and release validation/activation/withdrawal endpoints.

The router contract is fixed:

| Method | Path | Request/response | Science authority |
|---|---|---|---|
| POST | `/api/science/interpret` | document/selection + request ID + idempotency key → proposal Interpretation Record | access-mode user |
| POST | `/api/science/interpretations/{interpretation_id}/confirm` | exact claim IDs + idempotency key + immediate confirmation → immutable confirmed Interpretation version | same authenticated user |
| POST | `/api/science/claims/{claim_id}/verify` | stored confirmed `interpretation_id` + ReleaseSelection → Verdict Packet | access-mode user |
| POST | `/api/science/verify-document` | stored confirmed `interpretation_id` + ReleaseSelection + idempotency key → Verification Report | access-mode user |
| GET | `/api/science/evidence/{evidence_id}` | Evidence detail | access-mode user + source ACL |
| GET | `/api/science/reports/{report_id}` | stored Verification Report | report/source ACL |
| GET | `/api/science/reports/{report_id}/export` | `format=markdown|pdf` bytes | report/source export ACL |
| POST | `/api/science/proposals` | proposal + exact request digest + idempotency key + immediate confirmation → proposal record | access-mode user |
| POST | `/api/science/proposals/{proposal_id}/review` | `approve|reject|withdraw` + exact object digests → append-only review event | domain Power User for alias/term/interpretation/concept-link only; otherwise Admin; no self-approval |
| POST | `/api/science/admin/sources/validate` | source object → validation | Admin |
| POST | `/api/science/admin/evidence/validate` | exact Evidence span + Source digest/locator/hash/scope → validation | Admin |
| POST | `/api/science/admin/knowledge/validate` | knowledge object → validation | Admin |
| POST | `/api/science/admin/rules/{rule_id}/qualify` | rule digest + sealed case-set digest/IDs → result | Admin |
| GET | `/api/science/admin/releases/{release_id}/impact` | conflict set + affected historical/current verdicts | Admin |
| POST | `/api/science/admin/releases/validate` | release ID/digest + sealed holdout-manifest digest → G0..G7 report | Admin |
| POST | `/api/science/admin/releases/{release_id}/activate` | exact release/request digests + idempotency key + immediate confirmation → audit | Admin |
| POST | `/api/science/admin/releases/{release_id}/withdraw` | exact release/request digests + idempotency key + immediate confirmation → fallback audit | Admin |

Verification routes never accept a caller-authored `ClaimPacket`. They load the immutable stored interpretation, require its separate user-confirmation revision, reconstruct the exact confirmed Claim Packet set, and reject any claim ID or digest that is not bound to that record before Catalog/Engine access.

- [ ] **Step 1: Add ReportLab and write failing endpoint tests**

Add `reportlab>=4.2,<5` to `boi_api/requirements.txt`.

```python
def test_report_exports_share_report_digest(science_client):
    interpretation = science_client.post("/api/science/interpret", json=DOCUMENT_FIXTURE).json()
    confirmed = science_client.post(
        f"/api/science/interpretations/{interpretation['interpretation_id']}/confirm",
        json=CONFIRMATION_FIXTURE,
    ).json()
    report = science_client.post(
        "/api/science/verify-document",
        json={
            "interpretation_id": confirmed["interpretation_id"],
            "release_selection": RELEASE_SELECTION,
            "idempotency_key": "report-export-test-1",
        },
    ).json()
    markdown = science_client.get(f"/api/science/reports/{report['report_id']}/export?format=markdown")
    pdf = science_client.get(f"/api/science/reports/{report['report_id']}/export?format=pdf")
    assert markdown.headers["x-science-report-digest"] == report["report_digest"]
    assert pdf.headers["x-science-report-digest"] == report["report_digest"]
    assert pdf.content.startswith(b"%PDF")
```

Cover all endpoints in spec, interpretation confirmation bound to the same authenticated actor, evidence ACL denial, object-kind-specific Power User review, Admin review of Source/Evidence/Knowledge/Rule changes, approve/reject/withdraw events, self-approval denial, user confirmation on mutations, explicit release pinning, impact completeness, and LLM-offline interpretation response.

Add two lifecycle regressions: a superseded/withdrawn release never changes the bytes or release digests of an existing report, and an incompatible/missing catalog raises an HTTP 503 operational error envelope with no `verdict` field.

- [ ] **Step 2: Run tests and confirm 404/import failures**

Run: `pytest tests/test_science_api.py -q`

Expected: FAIL because routes are not registered.

- [ ] **Step 3: Implement one-model report rendering**

`render_report_markdown(report)` and `render_report_pdf(report)` accept only a stored `VerificationReport`. Markdown includes annotated claims, verdict limitations, scientific explanation, ontology references, and decisive evidence links. PDF uses ReportLab with `UnicodeCIDFont("HYSMyeongJo-Medium")`; it embeds the same claim IDs, verdicts, evidence IDs, release IDs, and report digest.

- [ ] **Step 4: Build and inject the router without a circular import**

```python
science_router = create_science_router(
    data_root=DATA_ROOT,
    runtime_root=SCIENCE_RUNTIME_ROOT,
    current_identity_dependency=current_identity,
    roles_for=roles_for,
    access_policy_for_doc=access_policy_for_doc,
    find_doc_by_id=find_doc_by_id,
    templates=templates,
    shell_context=app_shell_context,
    llm_config=ScienceLLMConfig.from_environment(),
)
app.include_router(science_router)
```

Register it after `current_identity`, `roles_for`, and `app_shell_context` are defined. Routes never import `boi_api.app.main`.

- [ ] **Step 5: Implement mutation and release gates**

Every proposal/review/activation/withdrawal request requires `user_confirmed: true` bound to the authenticated actor and request digest. Review records append-only `approve|reject|withdraw` events for exact object digests; validation endpoints never write approval state. Power Users can approve only scoped alias/term/interpretation/concept-link proposals into a Release Candidate. Admin review is required for Source/Evidence/Knowledge/law/equation/Rule changes and final Release activation. Activation fails closed unless every pinned object has an authorized review event, the conflict/affected-verdict impact set is complete, and profile lint, reference/digest checks, qualification suite, source reachability metadata checks, and exact-one-active release enforcement pass before an atomic manifest update. Generic source/body edit routes must reject paths that belong to an active Science release.

- [ ] **Step 6: Add runtime/config persistence**

Document `SCIENCE_RUNTIME_ROOT`, `BOI_SCIENCE_ACCESS_MODE`, and `BOI_SCIENCE_LLM_*` in example env files without the internal host value. Compose passes them through and mounts the Science runtime root. Existing `BOI_LLM_*` remains the default.

- [ ] **Step 7: Run API tests and commit**

Run: `pytest tests/test_science_api.py tests/test_science_authorization.py tests/test_science_storage.py -q`

Expected: PASS.

```bash
git add boi_api/app/science/routes.py boi_api/app/science/reports.py boi_api/app/main.py boi_api/requirements.txt .env.example .env.local-full.example docker-compose.yml tests/test_science_api.py
git commit -m "feat: expose Science Verifier API and reports"
```

### Task 4: Document-centered review canvas and Wiki selection handoff

**Files:**
- Create: `boi_api/app/templates/science_verifier.html`
- Create: `boi_api/app/static/science_verifier.js`
- Modify: `boi_api/app/static/style.css`
- Modify: `boi_api/app/templates/doc.html`
- Modify: `boi_api/app/main.py`
- Test: `tests/test_science_ui.py`
- Create: `scripts/check_science_verifier_ui.mjs`

**Interfaces:**
- Consumes: Science REST endpoints and a Wiki selection transfer containing document ref and text anchors.
- Produces: top-level navigation after SOP, exact-span annotations, correction cards, ambiguity correction, evidence expansion, proposal action, and report export actions.

- [ ] **Step 1: Write failing shell and HTML contract tests**

```python
def test_science_nav_appears_after_sop_for_authorized_user(client):
    html = client.get("/science-verifier?employee_id=100001").text
    assert html.index("SOP") < html.index("Science Verifier") < html.index("Event Broker")
    assert 'data-science-review-canvas' in html
    assert 'data-science-chat' not in html
```

Assert visible source links, expandable evidence fields, absence of aggregate score and DOE text, accessible buttons/details, and role-based nav visibility.

- [ ] **Step 2: Run tests and confirm template failure**

Run: `pytest tests/test_science_ui.py -q`

Expected: FAIL because the page does not exist.

- [ ] **Step 3: Implement the review canvas**

Create a source editor/import panel, annotated-document panel, per-claim correction cards, and a right-side details panel. Escape source text, then split it by validated code-point ranges to create `<mark class="science-violation">` only for `VIOLATION` and `<span class="science-ambiguity">` only for decision-changing ambiguity. Never use raw LLM HTML.

- [ ] **Step 4: Implement correction and evidence interactions**

Each correction card displays verdict label, corrected claim when applicable, a full scientific explanation, limitations, and one or two decisive source links. `<details>` exposes original text, reviewed translation, locator, original URL, evidence hash, and compact ontology terms. “이번 검증에서 수정” reinterprets only that claim; “개선 제안” opens a prefilled, user-confirmed proposal form.

- [ ] **Step 5: Implement Wiki selection transfer with server re-anchoring**

Add a document page action and selection popover. Store the short transfer record in `sessionStorage` under `boi.science.selection.v1`, navigate to `/science-verifier?document_ref=...`, and let the server load the ACL-checked canonical Markdown body. JavaScript sends selected `exact/prefix/suffix`; the server resolves canonical offsets and digest before annotation. Wiki local revision은 원본 `boi:*` ref를 덮어쓰지 않고 server-derived `boi:submitted:*` 계보로 전환한다. 서버는 submit·confirm·`verify_claim`·`verify_document`마다 원본 Wiki ACL과 exact canonical ref/digest를 재확인하며, 재시작 후에도 canonical source lineage가 남아야 한다. lineage가 누락·위조·malformed면 fail closed한다. raw pasted document는 최초 owner만 접근하는 별도 semantics를 유지한다.

- [ ] **Step 6: Add headless browser verification**

Follow existing CDP scripts. Verify desktop and mobile widths, nav order, a real Wiki text selection, exact red/purple spans, evidence expansion, keyboard focus, Markdown/PDF download MIME and digest headers, disabled-Qwen API boundary, Wiki local revision lineage, and absence of browser console errors. Final evidence requires exactly 21 named browser checks and capture hashes; this plan does not claim that the historical 20-check step ran.

- [ ] **Step 7: Run UI checks and commit**

Run: `pytest tests/test_science_ui.py tests/test_science_api.py -q`

Run against a started local API: `node scripts/check_science_verifier_ui.mjs`

Expected: tests PASS and the browser script prints a JSON object with `ok: true`.

```bash
git add boi_api/app/templates/science_verifier.html boi_api/app/static/science_verifier.js boi_api/app/static/style.css boi_api/app/templates/doc.html boi_api/app/main.py tests/test_science_ui.py scripts/check_science_verifier_ui.mjs
git commit -m "feat: add document-centered Science Verifier review"
```
