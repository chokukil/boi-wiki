# Science Verifier Evidence Deck Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver a polished, editable, three-slide 16:9 PPTX that explains the trust architecture, shows the real review UI, and summarizes the final qualification report.

**Architecture:** Slide 1 uses a full-bleed imagegen infographic with editable Korean explanation overlays. Slides 2 and 3 use actual browser/report captures from the verified implementation; a deterministic PPTX build script keeps titles, callouts, metrics, source notes, and `N/3` page numbers editable, then exports every slide to PNG for visual inspection.

**Tech Stack:** Built-in image generation, bundled Node.js/PptxGenJS runtime, LibreOffice/PDF rendering utilities, Pillow, actual Science Verifier screenshots and report artifacts

**Spec:** `docs/superpowers/specs/2026-08-25-science-verifier-design.md`

> **계획 이력 보정(2026-08-25):** Deck의 “final”은 activation 완료의 동의어가 아니다. build 입력은 exact `FINAL` verification manifest, UI capture digest, 검증된 PDF render, tracked clean source여야 한다. Candidate가 inactive인 동안에는 G5·G6·G7 `PENDING`과 release boundary를 보존한다. build scorecard의 사람 육안 검수는 실제 사람이 슬라이드를 확인하기 전까지 `PENDING`이며, 과거 계획의 PNG 생성만으로 PASS라고 기록하지 않는다.

## Global Constraints

- The deck has exactly three content slides and no cover slide.
- Every slide is 16:9 and shows `1/3`, `2/3`, or `3/3` at the bottom right.
- Slide 1 is a full-canvas concept infographic generated with imagegen; exact Korean copy and source notes remain editable PowerPoint text.
- Slide 2 uses an actual running Science Verifier screen showing document-centered red violation annotation, correction explanation, and visible source links.
- Slide 3 uses the actual final implementation-evidence report and displays real counts/digests only after exact `FINAL` manifest verification completes; it must visibly distinguish inactive Candidate qualification from activation.
- No fabricated UI, placeholder metric, or unverified success claim may appear.
- Reader-facing slides contain no production instructions, review reminders, internal credentials, or private endpoint URL.
- The PPTX, per-slide PNGs, a whole-deck preview, production brief, and build evidence are preserved under `artifacts/science-verifier/deck/`.
- Titles, metrics, callouts, evidence labels, source notes, and page numbers remain editable.

---

### Task 1: Production brief and evidence asset inventory

**Files:**
- Create: `artifacts/science-verifier/deck/production-brief.md`
- Create: `artifacts/science-verifier/deck/source-ledger.md`
- Create: `artifacts/science-verifier/deck/assets/manifest.json`
- Test: `tests/test_science_deck.py`

**Interfaces:**
- Consumes: final verification manifest, real UI captures, report Markdown/PDF, and Science design spec.
- Produces: exact slide messages, asset paths/digests, source notes, and visual checking criteria.

- [ ] **Step 1: Write failing deck-contract tests**

```python
def test_deck_brief_defines_three_non_cover_slides(repo_root):
    brief = (repo_root / "artifacts/science-verifier/deck/production-brief.md").read_text()
    assert "슬라이드 수: 3" in brief
    assert "표지: 없음" in brief
    assert "1/3" in brief and "2/3" in brief and "3/3" in brief
```

Also require audience, decision, one-line story, one message per slide, source notes, imagegen role, editable elements, representative evidence slide, speaker-note expectation, and PNG inspection criteria.

- [ ] **Step 2: Run tests and confirm missing brief**

Run: `pytest tests/test_science_deck.py -q`

Expected: FAIL because the deck artifacts do not exist.

- [ ] **Step 3: Write the production brief from verified facts**

Audience is internal Science Verifier pilot reviewers. The story is: “AI의 답을 신뢰하는 대신, 해석은 확인하고 판정은 고정된 과학 지식·규칙·원문 근거로 재현한다.” Slide messages are architecture boundary, real review experience, and measured qualification outcome. Slide 3 is the representative evidence slide.

- [ ] **Step 4: Build the asset manifest with hashes**

Record planned inputs at these exact paths: `artifacts/science-verifier/deck/assets/science-integrity-layer.png`, `review-canvas-desktop.png`, `review-canvas-mobile.png`, `final-qualification-report.png`, `artifacts/science-verifier/qualification-report.md`, and `qualification-report.pdf`. Record exact `FINAL` verification-manifest digest, report digest, release digest, UI capture digests, verified PDF-render digest, and source URLs. The manifest uses workspace-relative paths and SHA-256; no asset may be marked final before its source file exists and the source checkout is tracked-clean.

- [ ] **Step 5: Run tests and commit**

Run: `pytest tests/test_science_deck.py -q`

Expected: PASS for the brief and manifest schema.

```bash
git add artifacts/science-verifier/deck/production-brief.md artifacts/science-verifier/deck/source-ledger.md artifacts/science-verifier/deck/assets/manifest.json tests/test_science_deck.py
git commit -m "docs: brief Science Verifier evidence deck"
```

### Task 2: Generate and inspect the full-bleed concept infographic

**Files:**
- Create: `artifacts/science-verifier/deck/assets/science-integrity-layer.png`
- Modify: `artifacts/science-verifier/deck/assets/manifest.json`

**Interfaces:**
- Consumes: architecture defined by the verified implementation.
- Produces: one 16:9 `scientific-educational` raster asset with no baked-in detailed text or fake branding.

- [ ] **Step 1: Generate the infographic with the built-in image tool**

Use this production prompt:

```text
Use case: scientific-educational
Asset type: full-bleed 16:9 PowerPoint infographic background
Primary request: visualize a scientific integrity layer that receives an untrusted AI claim, separates term interpretation from deterministic verification, checks immutable scientific knowledge/rules/conditions/units, and traces the verdict to exact source evidence
Style/medium: premium editorial technical infographic, crisp geometric layers, subtle semiconductor-process motifs, scientifically sober rather than futuristic fantasy
Composition/framing: wide left-to-right flow with five visually distinct zones and a clear evidence trace returning to the reviewed document; balanced full canvas, no empty placeholder region
Color palette: warm off-white and graphite base, red only for contradiction, purple only for ambiguity, restrained teal/blue for verified knowledge
Text: no detailed labels; use clean iconographic shapes so Korean labels can be overlaid as editable PowerPoint text
Constraints: 16:9, no logos, no watermark, no chat bubbles, no autonomous robot character, no aggregate score, no fake equations, no tiny illegible text
```

- [ ] **Step 2: Copy the selected built-in output into the workspace**

Preserve the generated original under the exact path `artifacts/science-verifier/deck/assets/science-integrity-layer.png`, then update its SHA-256 in the asset manifest.

- [ ] **Step 3: Inspect at original size and in a 16:9 crop**

Reject and regenerate if the flow is unclear, red/purple semantics are mixed, the canvas looks like a chat product, composition leaves a false text placeholder, or artifacts contain pseudo-text/equations. Keep only the selected final asset.

- [ ] **Step 4: Commit the selected visual**

```bash
git add artifacts/science-verifier/deck/assets/science-integrity-layer.png artifacts/science-verifier/deck/assets/manifest.json
git commit -m "art: add Science Verifier integrity infographic"
```

### Task 3: Build the editable PPTX from actual evidence

**Files:**
- Create: `scripts/build_science_verifier_deck.mjs`
- Create: `artifacts/science-verifier/deck/science-verifier-evidence.pptx`
- Create: `artifacts/science-verifier/deck/build-manifest.json`
- Modify: `tests/test_science_deck.py`

**Interfaces:**
- Consumes: infographic, `review-canvas-desktop.png`, `final-qualification-report.png`, `artifacts/science-verifier/qualification-report.{md,pdf}`, production brief, verification manifest, and bundled PptxGenJS path.
- Produces: a three-slide editable PPTX and build manifest.

- [ ] **Step 1: Extend tests to inspect PPTX structure**

```python
def test_pptx_has_three_slides_and_page_numbers(deck_path):
    with zipfile.ZipFile(deck_path) as deck:
        slides = sorted(name for name in deck.namelist() if re.fullmatch(r"ppt/slides/slide\d+\.xml", name))
        assert len(slides) == 3
        text = "".join(deck.read(name).decode("utf-8") for name in slides)
        for page in ("1/3", "2/3", "3/3"):
            assert page in text
```

Also assert widescreen dimensions, title text, absence of internal endpoint/credentials, presence of real report/release digest fragments, and notes/source fields.

- [ ] **Step 2: Run tests and confirm the PPTX is missing**

Run: `pytest tests/test_science_deck.py -q`

Expected: FAIL on the PPTX assertions.

- [ ] **Step 3: Implement the deck builder**

Use bundled workspace dependencies and `pptx.layout = "LAYOUT_WIDE"`. Slide 1 places the infographic full bleed with semi-opaque editable Korean labels: “신뢰하지 않는 AI 입력”, “용어·주장 해석”, “결정론적 규칙 검증”, “불변 Science Release”, “원문 Evidence 추적”. Slide 2 uses the actual annotated review screenshot with three callouts for exact red span, sufficient scientific explanation, and always-visible source links. Slide 3 uses the report screenshot and editable metric blocks for actual case count, false-red, broken locator, nondeterminism, Web/REST/MCP parity, release/report digest, and limitations.

- [ ] **Step 4: Add quiet sources and page numbering**

Every slide has a small editable source note in a safe reading zone. Add `N/3` at `x=12.15`, `y=7.05`, `w=0.75`, `h=0.2`, right-aligned, and use the same placement on all slides.

- [ ] **Step 5: Build, test, and commit**

Run: `node scripts/build_science_verifier_deck.mjs`

Run: `pytest tests/test_science_deck.py -q`

Expected: PPTX opens as a valid archive, has exactly three widescreen slides, and contains only verified metrics.

```bash
git add scripts/build_science_verifier_deck.mjs artifacts/science-verifier/deck/science-verifier-evidence.pptx artifacts/science-verifier/deck/build-manifest.json tests/test_science_deck.py
git commit -m "docs: build Science Verifier evidence deck"
```

### Task 4: Render slides, inspect visuals, and correct weak pages

**Files:**
- Generate: `artifacts/science-verifier/deck/rendered/slide-1.png`
- Generate: `artifacts/science-verifier/deck/rendered/slide-2.png`
- Generate: `artifacts/science-verifier/deck/rendered/slide-3.png`
- Generate: `artifacts/science-verifier/deck/rendered/whole-deck.png`
- Generate: `artifacts/science-verifier/deck/rendered/representative-evidence-slide.png`
- Create: `artifacts/science-verifier/deck/quality-scorecard.md`

**Interfaces:**
- Consumes: final PPTX.
- Produces: one PNG per slide, a whole-deck preview, a full-size slide 3 evidence preview, and a completed visual quality scorecard.

- [ ] **Step 1: Export PPTX to PDF and each slide to PNG**

Use the available bundled or system LibreOffice renderer, then `pdftoppm` or the bundled PDF renderer at a legible resolution. Create the whole-deck contact sheet without changing slide aspect ratios.

- [ ] **Step 2: Inspect every slide at full size**

Check text overflow/collision, title reading zones, source visibility, actual screenshot cropping, infographic balance, metric units, Korean spelling, and page number placement. Slide 3 must remain readable independently and separate metrics from the busy report screenshot. Record this as human visual QA: `PENDING` until an actual reviewer inspects the rendered slides; rendering itself is not visual approval.

- [ ] **Step 3: Fix only failing slides and re-render**

Adjust the builder rather than editing the generated PPTX by hand. Re-run until all scorecard items pass; do not regenerate the whole deck unless the story spine fails.

- [ ] **Step 4: Save final previews and commit**

```bash
git add scripts/build_science_verifier_deck.mjs artifacts/science-verifier/deck/rendered artifacts/science-verifier/deck/quality-scorecard.md artifacts/science-verifier/deck/science-verifier-evidence.pptx
git commit -m "test: visually verify Science Verifier deck"
```

## Controller-only Delivery Gate

After all five implementation plans, full verification, visual QA, and final whole-branch review pass, the primary agent performs this delivery step. It is not delegated and it does not merge.

```bash
test "$(git branch --show-current)" = "codex/science-verifier"
test -z "$(git status --porcelain)"
git push -u origin codex/science-verifier
git fetch origin codex/science-verifier
test "$(git rev-parse HEAD)" = "$(git rev-parse origin/codex/science-verifier)"
```

Expected: clean worktree, current branch `codex/science-verifier`, feature branch push succeeds, and local/remote SHA match. Do not check out `main`, create a merge commit, press a merge button, or merge the pull request; the user will review and merge.
