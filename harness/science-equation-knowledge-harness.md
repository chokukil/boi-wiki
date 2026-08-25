---
title: Science Equation Knowledge Harness
type: boi/harness
status: draft
---

# Science Equation Knowledge Harness

## Purpose

Science Knowledge에 수식이 있을 때 원문 표기부터 결정론적 Rule, 설명, Web·Markdown·PDF 표시까지 하나의 검토된 Equation identity로 연결한다. 수식이 없는 Knowledge에는 이 계약을 강제하지 않는다. AI, Agent, LaTeX renderer, CAS는 과학적 판정 권한이 없다.

## Inputs

- `equation_id`, immutable version, `scientific_role`, `decision_use`, `equation_digest`
- versioned closed `semantic_expression`, `display_latex`, `plain_text`, `accessibility_reading`
- 각 `variable_id`의 symbol, concept_ref, `quantity_kind`, dimension, unit convention, definition, domain, `sign_constraints`
- assumptions, applicability, `invalid_outside`, `boundary_conditions`, approximation/error/validity range
- `original_notation`, `notation_mapping`, EvidenceUse, exact equation locator와 source/hash identity
- 제안자 identity, 별도의 `science.admin` reviewer, `user_confirmed: true`인 exact digest mutation

`scientific_role`은 `definition | invariant | law | derived_model | approximation | empirical_fit | qualified_relation` 중 하나다. `decision_use`는 `explanation_only | deterministic_rule | formal_reference` 중 하나다.

## Observation

`semantic_expression이 권위`이고 LaTeX는 권위가 아닌 표시 표현이다. semantic expression은 versioned closed schema와 reviewed operator allowlist로만 작성한다. arbitrary Python expression, 임의 코드, Agent가 보낸 LaTeX, 범용 CAS/LLM 동치 판정은 Truth Path에서 실행하지 않는다.

`deterministic_rule`은 명시적 `equation_id`, Rule variable mapping, 지원 evaluator ID/version, 허용 변환 목록이 모두 연결된 경우에만 가능하다. evaluator가 지원하지 않는 합·적분·미분·행렬·벡터·화학 반응식 등은 검토된 설명과 표시에 쓸 수 있지만 기본값은 `explanation_only`이며 그 수식만으로 빨간 표시를 만들지 않는다. Lean/formal proof는 optional `formal_reference`이고 필수 경로가 아니다.

## Context

Equation Knowledge 객체는 최소한 다음 identity를 보존한다.

- identity: `equation_id`, schema/equation version, digest algorithm, `equation_digest`
- meaning: `scientific_role`, `decision_use`, closed `semantic_expression`
- display: `display_latex`, `plain_text`, `accessibility_reading`, renderer compatibility/fallback
- variables: `variable_id`, symbol, concept_ref, `quantity_kind`, dimension, unit convention, definition, domain/range/`sign_constraints`
- scope: assumptions, applicability, `invalid_outside`, `boundary_conditions`, approximation kind, error/tolerance 또는 validity/fitting range
- provenance: exact `original_notation`, `notation_mapping`, EvidenceUse, Source/Evidence digests와 equation locator

Source/Evidence에는 original URL/document digest, PDF page index와 printed page, section, Equation number, 정확한 원문 수식 전사, 전후 변수 정의 문장, 좌표계·reference direction·sign convention·unit system, equality/approximation/proportionality/inequality 종류, OCR/visual transcription method와 review state를 보존한다. original text/expression hash와 claim scope는 별도 hash scope다.

원문과 표준 표현의 mapping에서 부정, 등호/부등호, sign, exponent, subscript, parentheses, differential, numerator, denominator, unit, approximation condition, validity range가 달라지면 validation 실패다. equation locator만 있고 변수 정의나 좌표·부호·단위 convention을 확인할 수 없으면 `deterministic_rule`로 승격하지 않는다.

## Control

- 모든 Equation/variable/mapping 산출물은 proposal-only `draft/pending_review/release-blocked`다.
- `science.admin`만 법칙·수식·Evidence·Rule과 Equation Knowledge를 승인한다.
- Power User는 지정 domain의 별칭·용어·해석·concept link 제안만 승인하며 Equation/variable binding을 운영 승인하지 않는다.
- proposer/reviewer self-approval을 금지한다.
- 승인·변경·withdraw에는 exact object digest와 `user_confirmed: true`가 필요하다.
- inactive Equation, pending Evidence, 미지원 expression은 operational verdict나 red annotation에 들어가지 않는다.
- renderer failure, display_latex, accessibility failure는 verdict를 생성·변경할 수 없다.

## Action

1. 원문 URL/document digest와 exact equation locator를 고정하고 수식 및 전후 변수 정의를 전사한다.
2. OCR 또는 시각 전사를 별도 사람이 원문과 대조하고 sign/exponent/subscript/numerator/denominator/unit/range를 확인한다.
3. 원문 기호마다 `variable_id`, concept, `quantity_kind`, dimension, unit, domain/range를 정의하고 `notation_mapping`을 작성한다.
4. `scientific_role`, equality/approximation/empirical 성격, assumptions/applicability/`invalid_outside`/`boundary_conditions`를 고정한다.
5. reviewed operator allowlist로 versioned closed `semantic_expression`을 만들고 세 표시 표현과 EvidenceUse를 연결한다.
6. 모든 변수가 정의되고 concept/quantity가 연결되는지, 차원 일관성, 중복 symbol ambiguity, singularity, divide by zero, log/square-root domain, fitting parameter source를 validation한다.
7. 지원 evaluator와 허용 변환이 명시적으로 연결된 수식만 `deterministic_rule`로 제안한다. 나머지는 `explanation_only` 또는 `formal_reference`로 제한한다.
8. 별도 Admin review queue로 보내며 승인 전 Release에 운영 capability를 부여하지 않는다.

## State

Equation proposal, transcription review, notation mapping, evaluator binding, qualification, rendering profile은 append-only version이다. approved object는 immutable하고 변경은 새 version과 supersedes digest로 만든다. renderer version 또는 export bytes 변경은 scientific `report_digest`, verdict, `equation_digest`를 바꾸지 않으며 별도 `export_digest`에만 반영한다.

User·Codex·Claude·Qwen의 equation claim proposal은 untrusted다. 후보는 exact source span, parsed expression candidate, symbol별 concept/quantity 후보, unit/condition, sign/reference direction, ontology refs만 제출한다. 서버는 문서에 실제 존재하는 complete/non-overlapping span인지, 모든 symbol이 span 또는 확인된 context에 있는지, concept/quantity/ontology 역할이 유효한지, Agent가 변수를 발명하지 않았는지, 단위·조건을 확인 없이 추가하지 않았는지 다시 검증한다. `V`가 voltage인지 volume인지처럼 판정 결과가 달라지면 purple dotted ambiguity로 사용자 확인 전 중단한다.

## Verification

### Authoring and source review

- 모든 variable이 정의되고 concept_ref/`quantity_kind`/dimension/unit/domain에 연결되는지 확인한다.
- exact/approximation/empirical_fit/derived model이 구분되고 assumptions/applicability/`invalid_outside`가 완결되는지 확인한다.
- singular point, zero denominator, logarithm/square-root domain, fitting range/parameter provenance를 확인한다.
- 원문 표기와 표준 semantic expression의 `notation_mapping` 및 EvidenceUse가 source claim scope를 넘지 않는지 확인한다.

### Rule qualification

수식형 Rule은 기존 qualification matrix와 독립 sealed holdout에 더해 다음 case를 실제 evaluator 입력으로 실행한다.

- 같은 의미의 unit conversion과 허용된 algebraic rearrangement
- wrong sign, exponent, operator, equality/approximation/inequality confusion
- missing variable, symbol ambiguity, dimension mismatch
- validity boundary, divide by zero/singular point, log/square-root domain
- approximation overclaim, empirical extrapolation, numerical tolerance boundary
- notation-only false-red prevention, unsupported expression
- malicious/excessive LaTeX, raw HTML/URL/file/image/macro/expansion abuse

Agent가 expected verdict를 만들거나 qualification을 통과시킬 수 없다. unsupported expression은 `explanation_only` 또는 판정 보류이지 evaluator fallback이 아니다.

### Explanation and channel parity

stored report의 설명은 다음 순서의 구조화 block을 쓴다: 적용 원리·법칙·모델, reviewed Equation, 변수 의미, 적용 조건, Claim-to-variable mapping, 결정에 필요한 과학적 consequence, correction, 한계/적용 불가 범위, exact Evidence/locator. 각 fact/block은 `fact_id`, `knowledge_ref`, `equation_ref`, decisive `rule_ref`, `evidence_ref`, `source_ref`, 각 object digest와 `quote_hash`에 묶는다. 정의되지 않은 변수나 중간 조건은 AI가 채우지 않고 정보 부족 또는 판정 보류로 남긴다.

Web은 검토된 Equation, variables/conditions 펼쳐보기, 항상 보이는 source 1~2개, 원문·검토 번역·equation locator·original URL, 보조 ontology 경로를 보인다. 좁은 모바일 화면은 수식을 가로 scroll하고 LaTeX/plain-text copy, MathML 또는 `accessibility_reading`, 명확한 `rendering fallback`을 제공한다. local renderer는 strict command allowlist를 쓰며 raw HTML, external URL/file/image, dangerous macro, unbounded macro expansion을 차단한다. Agent 문자열을 innerHTML로 넣지 않는다.

Web, REST, MCP, Markdown, PDF는 같은 stored equation_id/digest, variables, conditions, Evidence, locator, verdict, Rule identity를 사용한다. Markdown은 display math와 plain-text fallback을 함께 둔다. PDF는 동일 reviewed Equation에서 생성한 deterministic SVG/MathML-equivalent path로 fraction, exponent, subscript, Greek, sum/integral/differential, matrix/vector, chemical reaction arrow를 읽을 수 있게 한다. scientific `report_digest`와 rendering bytes의 `export_digest`를 구분한다.

## Failure Artifacts

Equation ID/version/digest, Source/Evidence/locator digests, transcription diff, symbol/variable mapping diff, semantic schema/operator/evaluator version, dimension/domain/tolerance failure, qualification case, renderer/fallback/export digest를 저장한다. raw document, credential, chain-of-thought, arbitrary executable expression은 저장하지 않는다.

## Release-Blocking Conditions

- equation/variable/semantic/Evidence field 누락 또는 원문 transcription 불일치
- 정의되지 않거나 ambiguous한 symbol, 차원 오류, singular/domain/range 누락
- explanation_only/unsupported Equation이 deterministic 판정 또는 red annotation에 사용됨
- Agent/user LaTeX, arbitrary Python/CAS/LLM 결과가 Truth Path에 사용됨
- unsafe renderer 또는 accessible plain/MathML fallback 부재
- Web/REST/MCP/Markdown/PDF identity/parity 불일치
- Admin 승인 부재, 독립 holdout 부재, self-approval, inactive Release 사용

| Gate | 이 하네스의 통과 조건 |
|---|---|
| G0 | Equation schema, semantic operator allowlist, identity/digest가 유효하다. |
| G1 | 원문 전사·변수 정의·locator·EvidenceUse가 재현되고 Admin review 가능하다. |
| G2 | 변수·차원·정의역·조건·근사/경험 범위가 완결된다. |
| G3 | explicit evaluator와 허용 변환에 연결된 deterministic_rule만 판정에 쓰인다. |
| G4 | 공개 equation qualification에서 missed violation/false-red/unsafe input이 없다. |
| G5 | freeze 후 독립 sealed holdout이 equation boundary를 통과한다. |
| G6 | Web/REST/MCP/Markdown/PDF의 Equation/report/export identity와 접근성 표시가 검증된다. |
| G7 | 별도 사람 Admin 승인과 activation audit 뒤 immutable Equation만 활성 Release에 들어간다. |
