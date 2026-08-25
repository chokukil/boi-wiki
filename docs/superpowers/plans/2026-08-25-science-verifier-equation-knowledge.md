# Science Verifier Equation Knowledge Implementation Plan

> **Execution rule:** extend the existing Science Verifier in place. Preserve its untrusted-Agent boundary, deterministic verdict engine, inactive Candidate Release, exact Evidence lineage, role separation, report parity, and final evidence workflow.

**Goal:** add a closed, digest-bound Equation Knowledge contract from Source/Evidence transcription through deterministic Rule qualification, untrusted Claim interpretation, structured explanation, and identical Web/REST/MCP/Markdown/PDF equation identities without making LaTeX, a CAS, an LLM, or an ontology an authority.

**Trust boundary:** the versioned semantic expression and an explicitly linked closed evaluator are the only equation inputs eligible for a deterministic Rule. LaTeX is display-only. Unsupported expressions remain `explanation_only`. All repository Science objects remain draft/pending Admin review; no implementation task activates a Release or claims independent holdout completion.

## Phase 0 — Preserve the optional-adapter boundary

1. Add failing tests proving an enabled but invalid Qwen configuration cannot break alias detection or manual Claim submission, while `/interpret` still returns fail-closed `invalid_configuration`.
2. Make Qwen client construction interpretation-only and keep the deterministic service available independently.
3. Strengthen the browser evidence check so `adapter_disabled_real_server` requires the exact endpoint, HTTP 503, public error code, and `adapter_disabled` diagnostic. Add a negative fixture proving timeout/connection diagnostics cannot satisfy it.
4. Run focused API, interpretation, and browser-check contract tests; commit this boundary fix separately.

## Phase 1 — Closed Equation Knowledge schema

1. Add failing model tests for a closed `science-expression/0.1` AST, equation roles/uses, variables, dimensions, constraints, applicability, original notation mapping, Evidence use, evaluator link, and exact `equation_digest`.
2. Implement the closed semantic node/operator allowlist. It must reject undeclared fields, arbitrary code/functions, non-finite literals, incomplete node shapes, duplicate or undefined variables, ambiguous duplicate symbols, and unsupported deterministic operators.
3. Implement dimension propagation and domain checks for the reviewed deterministic subset. Addition/comparison require equal dimensions; multiplication/division/power derive dimensions; log/exp require dimensionless arguments; singularity/domain requirements must be declared. Chemical reactions, general integrals, matrices, and other non-evaluable structures are allowed only as `explanation_only` or `formal_reference`.
4. Add exact equation digest verification excluding only the digest field. Display LaTeX, plain text, and accessibility reading are required but never evaluated for a verdict.
5. Add a repository `data/okf/profiles/sci-profile.yaml` contract and bind `profile.py` validation to the typed equation model for Knowledge documents that contain equations. Knowledge without equations remains valid.
6. Add Source/Evidence equation-transcription models and validation for exact expression hash, variable-context hash, relation notation, coordinate/sign/unit conventions, transcription method/review state, locator, and Evidence-use scope. Deterministic eligibility requires exact variable context and an Equation locator.

## Phase 2 — Rule and Release binding

1. Add failing Rule/Catalog tests requiring each formula-driven evaluator to declare an exact `equation_ref`, `equation_digest`, evaluator ID/version, and complete BoI-variable-to-Claim-quantity mapping.
2. Extend `EquationConstraint` without replacing its current audited evaluator. Resolve the referenced equation only through the same release-pinned Knowledge component and reject digest mismatch, `explanation_only`, unsupported operators, missing mappings, or unreviewed Evidence eligibility.
3. Make Catalog validate equation IDs are unique across Knowledge, source notation maps every declared variable, Evidence references/locators are exact, and active decision components have authorized Admin review. Candidate qualification may inspect pending objects but cannot issue operational verdicts.
4. Migrate all current formula-driven Rule drafts to exact Equation Knowledge references. Rebuild the inactive Release Candidate manifest/digests; do not change its status.

## Phase 3 — Untrusted equation Claim proposals

1. Add failing REST/MCP/model tests for an optional equation proposal containing exact expression span, closed semantic candidate, symbol/concept/quantity/unit/condition proposals, reference direction, and ontology references.
2. Re-anchor the equation span against the submitted document and selected Claim. Reject incomplete, overlapping, external, or non-unique spans; undeclared/invented symbols; unknown ontology refs; unknown quantity roles; and Agent-added units/conditions/context.
3. Record outcome-changing symbol ambiguity as a user-confirmation issue. A symbol such as `V` that can denote voltage or volume must remain purple/unresolved until the user selects its meaning. Outcome-neutral notation differences are recorded without blocking.
4. Keep client verdict, Rule, Evidence, and correction fields forbidden. Qwen failures produce no equation Claim, verdict, Evidence, or red annotation.
5. Expose the same proposal contract through MCP and the repository/public harness without trusting the client kind.

## Phase 4 — Structured grounded explanation

1. Add failing model/service/storage-authority tests for ordered explanation blocks: principle/model, reviewed equation, variables, applicability, Claim mapping, scientific consequence, correction, limits, and exact Evidence.
2. Bind every block to `fact_id`, Knowledge ID/digest, optional Equation ID/digest, decisive Rule ID, Evidence ID/digest, Source ID/digest, and quote hash. Stored report validation and Catalog revalidation must reject any self-consistent forged identity.
3. Build blocks only from release-pinned fields and deterministic templates. Do not invent missing variables, intermediate conditions, numbers, recommendations, or prose beyond Evidence/Knowledge scope. Missing required information yields an insufficient/outside/empirical result, never a guessed explanation.
4. Preserve existing non-equation explanations while using the same structured block model.

## Phase 5 — Safe Web equation review

1. Add local KaTeX assets and license to the served static bundle. Configure `strict: "error"`, `trust: false`, bounded macro expansion, no custom macros, no raw HTML/URL/file/image commands, and no external CDN.
2. Render only stored, release-bound display LaTeX. Never pass Agent proposal text to KaTeX. Use `textContent` for plain/accessibility fallback, fail visibly to the fallback, and keep verdict/red state unchanged on rendering failure.
3. Display equation ID/digest, reviewed formula, plain-text/LaTeX copy controls, accessibility reading, variable meanings, applicability/invalid-outside/boundary constraints, exact Evidence locator, original/translation/source URL, and auxiliary ontology trace.
4. Add horizontal equation scrolling and narrow-screen layout. Preserve the document-first canvas, two-source summary, purple outcome ambiguity, per-Claim re-verification, and separate global improvement proposal.
5. Extend the strict Chromium checker with exact equation identity, safe-render/fallback, copy, link, accessibility, no-overflow, and no-red-without-authority checks.

## Phase 6 — Markdown/PDF channel parity

1. Add `export_digest` headers/transport fields distinct from semantic `report_digest`; preserve the existing MCP content hash under the explicit export identity.
2. Markdown must emit the same equation ID/digest, display-math LaTeX, plain fallback, variables, applicability, Rule, and Evidence locator from the stored report.
3. Replace the PDF plain `drawString` equation path with deterministic MathML rendering from the closed semantic expression. Use a local renderer and embedded fonts; do not parse arbitrary LaTeX. Record renderer version only in export metadata so changing it cannot alter the scientific report digest.
4. Add automated extraction/raster tests and an actual PDF fixture covering fraction, exponent, subscript, Greek, sum, integral, differential, matrix/vector, chemical species/reaction arrow, and adjacent Korean text. Complex forms are display-tested but remain `explanation_only` unless an explicit evaluator supports them.
5. Assert Web/REST/MCP/Markdown/PDF parity for equation ID/digest, variables, conditions, Evidence, verdict, Rule, and report identity.

## Phase 7 — Generic knowledge pack and qualification

1. Add reviewed-structure draft Equation Knowledge examples across physics, chemistry, circuits, semiconductor devices, materials science, and spin coating. Use existing authoritative Sources where the exact formula plus variable context is already captured; otherwise enrich Source/Evidence with exact locators or mark the equation `explanation_only` and explicitly block decision use.
2. Add qualification cases for reviewed unit conversion, allowlisted rearrangement, sign/exponent/operator/relation errors, missing/ambiguous variables, dimensions, validity boundaries, singularities, approximation overclaim, extrapolation, tolerance boundaries, notation false-red, unsupported expressions, and malicious/excessive LaTeX.
3. Keep spin coating as one application example, not a special code path. Do not add a DOE starting-point recommendation.
4. Run the public qualification matrix and disclose all formulas that remain explanation-only.

## Phase 8 — Harnesses, skills, and operations documentation

1. Before changing skills, add pressure tests that demonstrate the current Curator and Verifier instructions do not enforce the equation package completeness and explanation-vs-decision boundary.
2. Add one mirrored `science-equation-knowledge-harness.md`; update source-curation, knowledge-authoring, rule-qualification, and verification harnesses to reference it. Update indexes/responsibility matrix and synchronization tooling.
3. Update `boi-science-curator` to block incomplete Equation packages and reserve equation approval for Admin. Update `boi-science-verifier` to prohibit memory-derived formulas, inactive equation refs, invented variables, universalized approximations/fits, unverified calculations, and process recommendations.
4. Update design, API/MCP, operator, report, UI, release, and artifact-generation documentation. Keep user-facing Korean terminology intuitive: 표준 표현, 원문 표기, 변수 의미, 적용 조건.

## Phase 9 — Exact final evidence and handoff

1. Run focused model/profile/catalog/rule/service/storage/API/MCP/report/UI tests while developing, then the entire regression suite.
2. Run real Chromium desktop/mobile E2E with Qwen disabled and equation paths included. Capture the actual Candidate UI; verify formula clipping, fallback, accessibility text, source links, purple/red gates, and console cleanliness.
3. Generate the exact Markdown/PDF verification report from the final implementation commit, rasterize and visually inspect the PDF pages, and store screenshots plus digests. Clearly label Candidate/fixture evidence and inactive Release status.
4. Regenerate the exact test-suite contract, JUnit evidence, qualification report, verification manifest, and 3-slide PPT from the same final commit. Slide 2/3 may show formulas only from actual UI/report captures; keep exactly three content slides and human visual scorecard evidence.
5. Request independent whole-branch code review and close every Critical/Important finding. Re-run the exact regression and artifact build after the final code commit.
6. Commit only owned artifacts and documentation, push `codex/science-verifier`, and report separately: implemented equation features, automated checks, browser/PDF visual checks, unsupported expression types, explanation-only formulas, Admin/holdout pending work, and inactive Release state. Do not merge.

## Completion gates

- Implementation gate: closed schema, typed profile validation, Evidence transcription, Rule/evaluator binding, untrusted proposal revalidation, grounded explanation, safe Web, Markdown/PDF parity, automated tests, visual QA, independent review, docs, artifacts, and pushed branch all pass on one exact commit lineage.
- Scientific activation gate: still **not met** until a human Admin reviews exact Source/Evidence/Knowledge/Equation/Rule digests and an independent sealed holdout is run. The repository Candidate Release remains inactive regardless of implementation test results.
