# Science Verifier 설계 명세

- 상태: 설계 승인, 구현 전
- 작성일: 2026-08-25
- 대상 저장소: `boi-wiki`
- 대상 브랜치: `codex/science-verifier`

## 1. 제품 정의

Science Verifier는 문서나 질문에 포함된 과학적 주장을 찾아 검증하는 BoI Wiki의 새 기능이다. 전역 메뉴에서 `SOP` 바로 다음에 배치한다.

사용자가 문서를 붙여 넣거나 Wiki 문서의 일부를 선택하면, Science Verifier는 과학적으로 문제가 있는 정확한 구간을 표시하고 다음 내용을 함께 제공한다.

- 판정과 조건
- 교정문
- 충분한 과학적 설명
- 적용한 법칙·모델·검증 규칙
- 정확한 원문 근거와 위치
- 적용 범위와 확인하지 못한 사항

Science Verifier는 또 하나의 대화형 Agent가 아니다. Codex, Claude 등 사용자가 선택한 Agent와 웹 UI가 같은 검증 API를 사용하며, BoI Wiki는 검토된 지식과 결정적 판정을 제공한다.

핵심 전제는 다음과 같다.

> AI의 답변은 과학적 근거로 신뢰하지 않는다. AI는 주장을 해석하고 설명을 표현할 수 있지만, 참·거짓 판정과 인용을 만들거나 바꿀 수 없다.

## 2. 목표와 제외 범위

### 목표

1. 문서 중심 검토 경험을 제공한다.
2. 과학적 모순이 재현될 때만 빨간색으로 표시한다.
3. 판정이 달라지는 해석 모호성은 사용자가 확인할 수 있게 한다.
4. 모든 결정적 판정을 검토된 지식·규칙·Evidence Span으로 추적한다.
5. 동일한 Claim Packet과 Science Release 조합에는 동일한 판정을 반환한다.
6. 물리·화학·회로·재료·반도체 소자에 공통으로 확장되는 기반을 만든다.
7. Spin Coating을 범용 기반의 응용 사례로 입증한다.
8. 사용자의 Agent가 MCP/API로 같은 검증 기능을 사용하게 한다.

### 제외 범위

- BoI Wiki가 자체 Science Agent를 제공하는 것
- 일반 RAG 검색 결과나 LLM 답변을 판정 근거로 사용하는 것
- 근거가 부족한 주장을 강제로 참·거짓으로 분류하는 것
- 종합 신뢰 점수로 판정을 대신하는 것
- 사용자가 직접 활성 과학 지식을 수정하거나 자유롭게 승격하는 것
- Spin Coating recipe 변경량이나 DOE 시작점을 권고하는 것
- 초기 릴리스에서 모든 과학 분야와 반도체 공정을 포괄하는 것
- 모든 수학·과학 주장을 Lean으로 형식 검증하는 것

Lean 등 형식 증명 도구는 중요한 수학적 귀결을 검증할 수 있는 확장 지점으로만 남긴다. 실제 재료나 공정의 적용 여부는 실험과 Qualified Evidence가 책임진다.

## 3. 신뢰 불변조건

다음 조건은 구현 편의를 위해 약화할 수 없다.

1. LLM 출력은 Evidence가 아니다.
2. Source 자체는 판정 근거가 아니다. 정확한 Evidence Span이 필요하다.
3. Evidence Span을 검토된 Scientific Knowledge 없이 일반화하지 않는다.
4. Scientific Knowledge는 Verification Rule 없이 문서 주장을 자동 판정하지 않는다.
5. Verification Rule은 새로운 과학 사실을 만들지 않는다.
6. 온톨로지 관계는 주장을 해석하고 관련 지식을 찾는 데 사용하며 판정을 대신하지 않는다.
7. 활성 Science Release는 수정하지 않는다. 변경은 새 Release로 만든다.
8. 해결되지 않은 과학적 충돌은 다수결이나 LLM 선택으로 해소하지 않는다.
9. 사용자가 볼 수 없는 Evidence를 일반 사용자용 결정 근거로 사용하지 않는다.
10. 정보가 부족하면 빨간색으로 표시하지 않는다.
11. 과거 보고서는 당시 사용한 Claim Packet과 Release 조합을 유지한다.
12. 설명의 결정적 문장에는 Evidence 또는 검토된 Knowledge 연결이 있어야 한다.

## 4. 사용자와 권한

### User

- 문서와 선택 영역을 검증한다.
- 원문 근거·번역·과학 설명을 열람한다.
- 이번 검증에서 AI의 용어·주장 해석을 수정한다.
- 용어·해석·지식 개선을 제안한다.
- 전역 과학 지식과 판정 규칙을 직접 바꾸지 않는다.

### Power User

지정된 도메인에서 다음 제안을 검토해 Release Candidate에 포함할 수 있다.

- 별칭
- 용어 의미
- 해석 힌트
- 개념 연결
- 모호성 해소 패턴

자신이 작성한 제안을 스스로 승인할 수 없다. 법칙·수식·모델 적용 범위·Evidence Span·판정 규칙·최종 Release 활성화 권한은 없다.

### Admin

- Science Source와 Evidence Span을 검토한다.
- Scientific Knowledge, 법칙, 모델, 수식, Verification Rule을 승인한다.
- 과학적 충돌을 해결하거나 해당 항목을 격리한다.
- Release Qualification Report를 검토한다.
- Release를 활성화·대체·철회한다.

초기 운영은 Admin만 사용한다. 안정화 후 일부 인원을 Power User로 지정해 Pilot을 진행한다.

내부 권한 식별자는 `science.admin`, `science.power_user:<domain>`을 사용하고, 일반 인증 사용자는 User로 본다. Pilot에서는 기존 `boi.admin`을 `science.admin`에 명시적으로 매핑할 수 있지만, 일반 문서 승격 권한인 `boi.promoter`가 Science Release 활성화 권한을 자동으로 얻어서는 안 된다.

## 5. 사용자 경험

### 5.1 진입점

전역 메뉴 순서는 다음과 같다.

```text
BoI Wiki · BoI Inbox · SOP · Science Verifier · Event Broker · Action · Advanced
```

Science Verifier의 기본 진입점은 전용 검토 화면이다. Wiki 문서의 선택 영역 메뉴에서도 같은 검토 화면으로 들어간다. 채팅방처럼 보이는 UI는 사용하지 않는다.

### 5.2 문서 중심 검토 화면

기본 화면은 다음 영역으로 구성한다.

1. 원문 문서
2. 과학적 표시가 적용된 검토 본문
3. 선택한 표시 구간의 교정 카드
4. 근거와 과학 설명을 여는 상세 패널

판정 표시는 정확한 문자 범위에 고정한다.

- 빨간 음영과 밑줄: 재현 가능한 과학적 모순
- 보라색 점선: 결과가 달라질 수 있는 해석 모호성
- 중립 표시: 정보 부족, 적용 범위 이탈, 실증 확인 필요

결과에 영향을 주지 않는 표현 차이는 화면을 방해하지 않고 Interpretation Record에만 남긴다.

### 5.3 교정 카드

교정 카드에는 다음 순서로 표시한다.

1. 판정과 중요한 조건
2. 교정문
3. 왜 문제가 되는지에 대한 짧은 설명
4. 핵심 근거 출처 1~2개
5. `과학적 설명 펼쳐보기`

펼쳐보기에는 다음 내용을 제공한다.

- 물리·화학적 메커니즘
- 필요한 수식과 변수 의미
- 가정과 적용 조건
- 모델의 유효 범위와 한계
- 원문 Evidence Span
- 정확한 페이지·절·수식 위치
- 원문 링크
- 검토된 번역
- 판정에 사용한 Knowledge와 Rule
- 주장 해석에 사용한 온톨로지 참고 항목

`주장 해석 완료`, `조건 5개 확인` 같은 기술적 체크리스트는 일반 사용자 화면에 두지 않는다. 사용자는 과학적 이유와 원문 근거를 먼저 본다.

### 5.4 모호성 확인

모호성은 판정을 바꾸는 경우에만 사용자에게 묻는다.

예를 들어 `RPM`이 dispense 단계인지 final spin 단계인지, `두께`가 wet film인지 post-bake dry film인지에 따라 결과가 달라진다면 해당 구간을 보라색으로 표시한다.

사용자가 의미를 선택하거나 주장을 수정하면 그 Claim만 다시 검증한다. 다른 Claim은 재실행하지 않는다.

### 5.5 피드백 선순환

두 동작을 분리한다.

- `이번 검증에서 수정`: 현재 Claim Packet만 바꾸고 즉시 재검증
- `개선 제안`: 원문·해석·개념·근거를 채운 Proposal 생성

Proposal은 활성 지식을 바로 바꾸지 않는다. Power User 또는 Admin 검토를 거쳐 다음 Release Candidate 후보가 된다.

### 5.6 보고서

운영 화면은 Claim별 판정과 근거를 보여주는 문서형 보고서를 사용한다. 같은 데이터를 Markdown과 PDF로 내보낼 수 있어야 한다.

종합점수는 핵심 판단 기준으로 사용하지 않는다. 보고서에는 검증 범위, 판정된 Claim, 보류된 Claim, 사용 Release, 근거와 한계를 기록한다.

## 6. 판정 체계

Primary Verdict는 다섯 가지다.

| Verdict | 의미 |
|---|---|
| `VIOLATION` | 명시된 조건 안에서 검토된 지식·규칙과 모순됨 |
| `CONSISTENT` | 검사한 범위 안에서 적용 규칙과 모순이 발견되지 않음 |
| `INSUFFICIENT_INFORMATION` | 판정에 필요한 대상·조건·관계가 부족함 |
| `OUTSIDE_VALIDITY_DOMAIN` | 적용한 모델·규칙의 검증 범위를 벗어남 |
| `EMPIRICAL_VERIFICATION_REQUIRED` | 이론만으로 특정 장비·재료·수치를 확정할 수 없고 실측이 필요함 |

`CONSISTENT`는 진실·안전·승인·공정 적합성을 뜻하지 않는다. 보고서는 어떤 Claim과 Rule을 검사했는지 함께 표시해야 한다.

지식 Pack 누락은 `INSUFFICIENT_INFORMATION`에 `KNOWLEDGE_COVERAGE_MISSING` reason code를 붙인다. 호환되지 않는 Release 조합이나 실행 장애는 과학적 Verdict로 위장하지 않고 별도의 운영 오류로 처리한다.

## 7. 검증 흐름과 AI 경계

```text
문서 또는 질문
  → Claim 후보 추출
  → Dictionary·Ontology 기반 용어 해석
  → Interpretation Record와 Claim Packet 초안
  → 결과를 바꾸는 모호성 확인
  → 확정 Claim Packet
  → Science Release에서 Knowledge·Rule 해결
  → 결정적 검증기
  → Verdict Packet
  → 근거가 고정된 과학 설명과 문서 표시
```

### LLM이 맡는 일

- 자연어에서 Claim 후보 찾기
- 용어·물리량·조건·관계 후보 만들기
- 판정을 바꾸는 모호성 후보 찾기
- 결정적 Verdict Packet을 읽기 쉬운 설명으로 표현하기

### LLM이 맡지 않는 일

- 판정 선택 또는 변경
- Evidence 생성
- Citation 생성
- 검토되지 않은 지식으로 설명 보완
- Source 검색 결과를 직접 판정 근거로 채택
- 빠진 조건을 추측해 채우기

서버가 승인된 Evidence locator와 링크를 삽입한다. 설명 문장마다 사용한 Knowledge 또는 Evidence가 연결되어야 한다. 연결하지 못한 결정적 문장은 결과에서 제외한다.

자연어 해석은 비결정적일 수 있다. 재현성 보장은 다음 경계부터 적용한다.

> 동일한 확정 Claim Packet과 동일한 Foundation·Domain·Application Release 조합은 동일한 Verdict와 근거 경로를 반환한다.

### 7.1 결정적 검증기

결정적 검증기는 LLM과 분리된 서버 구성요소다.

1. Claim Packet schema validator
2. 용어·물리량·단위 정규화기
3. 조건·적용 범위 matcher
4. 단위·차원·수식 검사기
5. allowlist 기반 Rule evaluator
6. Knowledge·Evidence resolver
7. Verdict Packet builder

Rule은 YAML/JSON 기반의 제한된 선언형 DSL로 표현한다. 임의 Python이나 shell 코드를 Rule로 실행하지 않는다. 수식 엔진은 차원, 단위 변환, 부호, 단조 방향, 허용 범위와 단순 대수 귀결을 결정적으로 검사한다.

`sci-profile`과 Pack graph의 구조 검증은 JSON Schema/Pydantic과 SHACL 계열 제약을 사용할 수 있다. 구조 검증 통과는 과학적 참을 뜻하지 않으며, 필요한 필드와 관계가 갖춰졌다는 뜻으로만 사용한다. Lean은 중요 수학 귀결을 형식 검증하는 후속 adapter로 남기며 경험적 전제를 대신하지 않는다.

## 8. RAG와 온톨로지의 경계

RAG는 판정 경로에 들어가지 않는다. 향후 Source 후보를 발견하거나 관리자가 검토할 자료를 찾는 보조 수단으로만 사용할 수 있다.

기존 Dictionary와 Ontology는 다음 역할을 맡는다.

- 약어와 현장 표현 해석
- 개념 후보와 상·하위 관계 탐색
- 물리량·단위·재료·공정·소자 연결
- 관련 Science Knowledge 후보 검색
- 결과를 바꾸는 의미 차이 발견

개인·팀 Dictionary의 별칭은 Claim 해석에 사용할 수 있지만 활성 Science Knowledge와 Rule을 덮어쓰지 않는다. Science Verifier는 정확히 고정된 Science Release만 판정에 사용한다.

온톨로지 관계에는 `declared`, `extracted`, `inferred` 출처를 남긴다. 판정에 영향을 주는 관계는 활성 Release에 포함된 검토된 `declared` 관계여야 한다.

## 9. 데이터 객체

### 9.1 저장 객체

| 객체 | 책임 |
|---|---|
| Science Source | 저자·판·URL·DOI·접근 상태·보존본·checksum |
| Evidence Span | 원문의 정확한 범위와 locator, 번역, quote hash |
| Scientific Knowledge | 정의·원리·법칙·메커니즘·모델·조건부 관계 |
| Verification Rule | 조건 비교, 모순 기준, Verdict와 reason code |
| Qualification Case | 입력·기대 결과·경계 및 실패 사례 |
| Science Pack | Knowledge·Rule·Source 의존성 묶음 |
| Science Release | 활성화할 정확한 객체 버전과 digest |

### 9.2 실행 객체

| 객체 | 책임 |
|---|---|
| Claim Packet | 문서 안 주장의 정규화된 의미 |
| Interpretation Record | 원문, LLM·prompt 버전, 온톨로지 참고, 사용자 확인 |
| Verdict Packet | Verdict, Rule, 조건 비교, 근거 경로, 한계 |
| Verification Report | 문서 표시, 설명, 출처, Release와 내보내기 데이터 |

실행 객체는 과학 지식으로 승격하지 않는다.

### 9.3 Packet 최소 계약

Claim Packet은 LLM의 산문 답변이 아니라 검증기가 읽을 수 있는 구조여야 한다.

```yaml
claim_packet:
  claim_id: claim:...
  document_ref: ...
  document_digest: sha256:...
  source_span:
    offset_encoding: unicode_code_point
    start: 120
    end: 151
    exact: "..."
    prefix: "..."
    suffix: "..."
  normalized_claim:
    subject_concept_id: ...
    relation_kind: monotonic_direction
    predicate: increases
    object_concept_id: ...
    polarity: positive
    quantities: []
    conditions: []
    process_stage: ...
    material_state: ...
  interpretation:
    ontology_refs: []
    ambiguity_ids: []
    user_confirmed: false
```

문서 span은 Unicode code point offset과 `exact/prefix/suffix` anchor를 함께 저장한다. 문서가 바뀌어 anchor가 일치하지 않으면 기존 위치에 빨간 표시를 강제로 붙이지 않고 재해석을 요청한다.

Interpretation Record는 다음을 저장한다.

- 원문 digest와 Claim 후보
- 사용한 model ID와 설정, prompt version
- Dictionary·Ontology Release와 참고 개념
- 후보 의미와 결과 영향
- 사용자의 선택·수정 이력
- 확정 Claim Packet digest

API key나 비밀 endpoint credential은 기록하지 않는다.

Verdict Packet은 자연어 설명보다 먼저 완성된다.

```yaml
verdict_packet:
  claim_id: claim:...
  claim_packet_digest: sha256:...
  verifier_version: ...
  releases:
    foundation: ...
    domains: []
    applications: []
  verdict: VIOLATION
  reason_codes: []
  condition_evaluations: []
  decisive_rule_ids: []
  knowledge_refs: []
  evidence_refs: []
  corrected_claim: "..."
  explanation_facts:
    - fact_id: ...
      knowledge_refs: []
      evidence_refs: []
  limitations: []
```

LLM은 `explanation_facts`만 자연어로 연결한다. 서버는 최종 문장의 근거 연결을 검사하고 Citation을 삽입한다.

## 10. `sci-profile`

`sci-profile`은 `boi-profile`을 대체하지 않는다. `boi-profile`은 ACL·소유권·공통 문서 상태를 계속 관리하고, `sci-profile`은 과학적 의미만 추가한다.

```yaml
okf_version: "0.1"
boi_profile_version: "0.1"
sci_profile_version: "0.1"

type: boi/science-knowledge
title: Model validity domain
boi_id: boi:public:science:knowledge:common:model-validity
visibility: public
classification: internal
owner: science-admin
acl_policy: acl:public
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:science:evidence:...

science:
  knowledge_id: sci:common:model-validity
  pack_id: science-foundation
  knowledge_kind: model
  assurance_basis: derived_model
  statement: "..."
  assumptions: []
  applicability: {}
  limitations: []
  evidence_refs: []
  related_knowledge: []
```

`knowledge_kind`와 `assurance_basis`를 분리한다.

- `knowledge_kind`: definition, invariant, law, mechanism, model, conditional_relation, qualified_rule, observation, measurement
- `assurance_basis`: formal_theorem, physical_law, derived_model, empirical_correlation, vendor_process_rule, internal_qualified_rule, hypothesis

`confidence: 0.93` 같은 단일 수치는 두지 않는다. 과학적 보증은 근거의 종류, 적용 범위, 검토 상태로 표현한다.

Source와 Evidence는 별도 객체로 관리한다.

```yaml
science:
  source_id: sci-source:...
  source_role: normative_definition
  title: "..."
  authors: []
  edition_or_version: "..."
  original_url: "..."
  doi_or_isbn: "..."
  retrieved_at: "..."
  archived_content_ref: "..."
  content_hash: "sha256:..."
```

```yaml
science:
  evidence_id: sci-evidence:...
  source_id: sci-source:...
  locator:
    page: 42
    section: "3.2"
    equation: "Eq. 7"
  original_text: "..."
  original_text_hash: "sha256:..."
  language: en
  reviewed_translation: "..."
  supports_knowledge: []
```

기존 `source_refs`는 OKF 호환 링크를 유지하고, `science.evidence_refs`는 관계 역할까지 표현한다. Lint가 두 참조의 불일치를 차단한다.

Science Knowledge에는 자유로운 성숙도 승격 단계를 두지 않는다. 작성 중 상태와 무관하게 실제 판정에 사용할 수 있는지는 활성 Science Release 포함 여부로 결정한다.

## 11. 과학 지식 구조

업무 목표와 과학 지식 종류를 한 계층에 섞지 않는다.

### 거버넌스 영역

- 예측 가능성
- 재현성
- 안전한 공정
- 설명 가능성

### 과학 기반 영역

- 정의와 물리량
- 불변조건과 보존 제약
- 원리와 법칙
- 메커니즘
- 모델과 수식
- 조건부 관계

### 적용 영역

- Qualified Rule
- Observation
- Measurement
- Vendor·사내 적용 범위

Evidence는 어느 영역에도 연결할 수 있지만, 모든 것을 단순 graph edge로 축약하지 않는다. 조건·예외·수식·설명은 지식 객체 본문과 `sci-profile`에 둔다.

## 12. General Science Foundation

첫 Foundation Release는 다음 12개 공통 주제를 실제 원자 지식으로 구축한다.

| ID | 주제 | 주요 판정 경계 |
|---|---|---|
| SCI-COM-001 | quantity·value·unit·dimension | 물리량과 수치·단위 혼동 |
| SCI-COM-002 | dimensional homogeneity | 차원 일관성은 필요조건이지만 충분조건은 아님 |
| SCI-COM-003 | unit conversion | 곱셈·affine·log·절차형 변환 구분 |
| SCI-COM-004 | measurand·measurement result | 무엇을 어떤 조건에서 측정했는지 확인 |
| SCI-COM-005 | uncertainty·error | 불확도와 실제 오차 혼동 방지 |
| SCI-COM-006 | accuracy·precision·trueness | 용어와 산업 표기 문맥 구분 |
| SCI-COM-007 | repeatability·intermediate precision·reproducibility | 반복 조건과 재현 조건 구분 |
| SCI-COM-008 | model·assumptions·validity | 모델 검증과 보편적 진실 구분 |
| SCI-COM-009 | system boundary·balance | 경계·유입·유출·생성·소비 확인 |
| SCI-COM-010 | equilibrium·steady state | 정상상태와 평형 구분 |
| SCI-COM-011 | conditional dependence·controlled variables | 단순 `A → B` 관계 금지 |
| SCI-COM-012 | correlation·causation | 연관성과 인과 주장의 근거 의무 구분 |

모델·조건·측정 상태가 빠지면 `INSUFFICIENT_INFORMATION` 또는 `OUTSIDE_VALIDITY_DOMAIN`으로 멈춘다. 명확한 모순만 `VIOLATION`으로 표시한다.

### 12.1 원자 지식 분해

각 SCI-COM 문서는 탐색용 주제 문서이고, 실제 판정에는 다음 원자 객체를 사용한다.

| ID | 원자 객체 | 핵심 규칙 |
|---|---|---|
| 001 | quantity, quantity kind, quantity value, measurement unit, dimension | 수치·단위·물리량을 서로 대체하지 않음 |
| 002 | quantity equation, dimensional homogeneity, dimensional sufficiency limit | 차원 불일치는 위반, 차원 일치만으로 식의 참을 확정하지 않음 |
| 003 | multiplicative, affine, logarithmic, procedure-defined conversion | 등록된 변환 종류와 정의만 실행 |
| 004 | measurand, measurement procedure, influence quantity, measurement result | 측정값은 measurand와 조건 없이 비교하지 않음 |
| 005 | measurement error, measurement uncertainty | 불확도를 알려진 실제 오차로 해석하지 않음 |
| 006 | accuracy, trueness, precision, manufacturer accuracy expression | `accuracy ±1%` 같은 문구는 정의 확인 전 자동 위반 처리하지 않음 |
| 007 | repeatability condition, intermediate precision condition, reproducibility condition | 조건 집합이 다른 정밀도 개념을 혼용하지 않음 |
| 008 | model, assumption, validity domain, validation, limitation, extrapolation | 가정 충돌은 범위 이탈, 조건 누락은 정보 부족, 높은 R²만으로 모델을 참이라 하지 않음 |
| 009 | system, boundary, control volume, inventory, flow, source/sink, balance, conservation invariant | 전체 질량과 화학종 수지를 구분하고 경계 밖 흐름을 검사 |
| 010 | steady state, equilibrium, dynamic equilibrium, nonequilibrium steady state | 정상상태에서 흐름이 0이라고 가정하지 않고 평형에서 미시 과정이 멈춘다고 하지 않음 |
| 011 | factor, response, controlled variable, conditional relation, valid range, regime transition | 방향 관계에 고정 조건·단계·상태·범위를 함께 요구 |
| 012 | association, correlation, causal claim, confounder, intervention evidence, causal mechanism | 상관만으로 인과가 증명됐다는 주장을 위반으로 처리 |

SCI-COM-008의 모델은 `theoretical`, `semi_empirical`, `empirical_fit` basis를 구분한다. SCI-COM-009의 balance는 `accumulation = inflow - outflow + generation - consumption`이라는 공통 틀을 쓰되, 어떤 항이 허용되는지는 질량·화학종·에너지·전하 등 대상에 따라 결정한다.

SCI-COM-011의 조건부 관계는 최소한 input quantity, response quantity, direction 또는 functional form, held-constant variables, process stage, material state, temporal basis, valid range, regime transition, evidence basis를 가져야 한다. 단순 `A influences B` edge는 판정에 사용하지 않는다.

## 13. Pack 구조와 의존성

```text
General Science Foundation
 ├─ Physical Principles
 ├─ Chemical Principles
 ├─ Circuit Principles
 └─ Materials Science
      └─ Semiconductor Devices

Spin Coating Application
 ├─ Physical Principles
 ├─ Chemical Principles
 └─ Materials Science
```

허용하는 Pack 관계는 `depends_on`, `uses`, `specializes`, `adds_evidence`, `validated_by`, `supersedes`다. 일반적인 `override`는 허용하지 않는다.

Application Pack은 Foundation이나 Domain Pack을 재정의하지 않고 더 좁은 조건으로 구체화한다. 해결된 정확한 Release ID와 component digest를 Verification Record에 저장한다.

### Physical Principles

- 위치·속도·가속도
- 힘·관성·운동량
- 일·에너지·전력
- 회전속도와 각속도
- 압력·밀도·응력·점도
- 유동·flux·no-slip
- 확산과 물질전달
- 열·온도·열전달
- 열역학 제1법칙
- 정상상태와 과도상태

### Chemical Principles

- 물질·화학종·원소·화합물
- 몰·물질량·농도·분율
- 용액·용질·용매
- 상·상변화·증기압·증발
- 화학 평형과 반응지수
- 반응속도와 온도
- 촉매가 속도와 평형에 미치는 영향의 구분
- 실험적 상관과 기전

### Circuit Principles

- 전하·전류·전압
- node·branch·loop
- KCL·KVL
- 저항과 Ohm model
- 전력과 에너지
- 동일 전압·동일 전류 조건
- 이상 전압원·전류원
- capacitor·inductor
- DC 정상상태와 transient
- 선형 모델과 적용 범위
- 실제 소자와 이상 모델
- 측정기 loading

### Materials Science

- 원자 결합과 재료 구조
- 결정·비정질·고분자
- 격자·결정방향·결정립
- point defect·dislocation·grain boundary
- 상·상분율·상변태
- 조성과 미세구조
- 확산과 활성화 과정
- 표면·계면·박막
- 응력·변형률·탄성·점탄성
- 등방성·이방성
- 전기·열·광학 물성
- 공정–구조–물성–성능 관계
- bulk와 thin film 모델의 차이

### Semiconductor Devices

다음 네 층을 분리한다.

```text
재료 조성·구조
  → 전자 상태와 수송
    → 소자 내부 물리
      → 회로용 소자 모델
```

초기 범위는 다음과 같다.

- conductor·insulator·semiconductor
- energy band·band gap·Fermi level
- intrinsic·extrinsic semiconductor
- donor·acceptor·doping
- electron·hole·carrier concentration
- mobility·conductivity·drift·diffusion
- generation·recombination·temperature dependency
- p-n junction·depletion region·bias·breakdown
- diode I–V와 적용 조건
- MOS capacitor와 accumulation·depletion·inversion
- threshold voltage·oxide capacitance·interface charge
- MOSFET operating region·body effect·subthreshold·leakage
- physical device와 compact circuit model
- large-signal·small-signal·bias point·transconductance
- BJT 기본 구조와 operating region

FinFET, GAA, 고급 compact model은 초기 Release의 필수 범위가 아니다. 확장 지점만 유지한다.

### Spin Coating Application

- dispense·spread·final spin·edge bead·bake 단계
- wet film·dry film·post-bake film 구분
- resist 점도·고형분·휘발성
- 회전·배기·온도·습도 조건
- 방사 방향 유출·점성 저항·용매 증발
- Emslie 계열 이상 모델
- 증발을 포함한 Meyerhofer 계열 모델
- 다성분·건조 거동을 다룬 후속 모델
- Vendor spin curve와 사내 Qualified Rule
- 두께 측정 시점·sampling·유효 공정 범위

Spin Coating은 Semiconductor Devices에 억지로 의존하지 않는다. 패턴 결과와 소자 성능을 연결하는 후속 Application에서 두 Pack을 함께 사용한다.

## 14. Source 전략

자료를 단일 권위 순위로 세우지 않고 역할을 부여한다.

| Source 역할 | 예시 |
|---|---|
| 표준 정의·단위 | BIPM, JCGM, IUPAC, NIST |
| 기본 물리 원리 | Feynman, MIT, 검토된 교재 |
| 수식과 유도 | 교재, 강의 자료, 원 논문 |
| 이해하기 쉬운 설명 | Feynman, Chem1, OpenStax, All About Circuits |
| 특정 모델 | 모델 원 논문과 후속 검증 논문 |
| 재료·소자 | MIT 3.091·3.012·3.024·6.012, Chenming Hu |
| 제품·공정 | Vendor 자료, 장비 문서, 사내 Qualified 문서 |
| 실제 적용 | 측정 데이터, 실험 보고서, 승인된 사내 문서 |

초기 무료 Source 후보:

- [The Feynman Lectures on Physics](https://www.feynmanlectures.caltech.edu/)
- [BIPM SI Brochure](https://www.bipm.org/en/publications/si-brochure)
- [JCGM VIM](https://jcgm.bipm.org/vim/en/)
- [IUPAC Gold Book](https://goldbook.iupac.org/)
- [MIT 5.111 Principles of Chemical Science](https://ocw.mit.edu/courses/5-111-principles-of-chemical-science-fall-2008/)
- [MIT 6.002 Circuits and Electronics](https://ocw.mit.edu/courses/6-002-circuits-and-electronics-spring-2007/)
- [MIT 3.091 Introduction to Solid-State Chemistry](https://ocw.mit.edu/courses/3-091-introduction-to-solid-state-chemistry-fall-2018/)
- [MIT 3.012 Fundamentals of Materials Science](https://ocw.mit.edu/courses/3-012-fundamentals-of-materials-science-fall-2005/)
- [MIT 3.024 Electronic, Optical and Magnetic Properties of Materials](https://ocw.mit.edu/courses/3-024-electronic-optical-and-magnetic-properties-of-materials-spring-2013/)
- [MIT 6.012 Microelectronic Devices and Circuits](https://ocw.mit.edu/courses/6-012-microelectronic-devices-and-circuits-fall-2009/)
- [Chem1 Virtual Textbook](https://www.chem1.com/acad/webtext/virtualtextbook.html)
- [OpenStax Science](https://openstax.org/subjects/science)
- [Chenming Hu, Modern Semiconductor Devices for Integrated Circuits](https://www.chu.berkeley.edu/modern-semiconductor-devices-for-integrated-circuits-chenming-calvin-hu-2010/)

Feynman은 설명과 물리적 사고의 주축이지만 유일한 결정 권위가 아니다. 공식 온라인판은 무료 열람 권한과 재배포 권한이 다르므로 전체 내용을 복제하지 않는다. 원본 링크, 허용 범위의 검토 Evidence Span, BoI의 독자적 설명을 저장한다.

Atkins와 Agarwal & Lang 등 유료 자료는 사내에서 정당하게 접근할 수 있는 판본이 있을 때 Source로 등록한다. 판본이 없으면 서지정보만 등록하고 Evidence가 있는 것처럼 사용하지 않는다.

NIST 등 기관 저장소의 데이터도 기관 이름만으로 검토 완료라고 간주하지 않는다. 개별 데이터셋의 생성 방법·불확도·검토 상태를 기록한다.

## 15. Source와 지식 구축 절차

```text
Source 후보
  → Source Ledger
  → Evidence Span 검토
  → 원자 Scientific Knowledge 작성
  → 온톨로지 연결
  → Verification Rule 작성
  → Qualification Case 실행
  → Release Candidate
  → Admin 활성화
```

### Source Ledger

- 제목·저자·판·발행일
- 공식 URL·DOI·ISBN·course version
- source 역할
- 접근·보존 범위
- retrieval timestamp와 checksum
- 정정·철회·대체 여부

### Evidence 검토

- 원문과 일치하는가
- 문맥을 잘라 의미를 바꾸지 않았는가
- locator가 정확한가
- 번역이 원문보다 강한 주장을 만들지 않는가
- 해당 Knowledge를 실제로 지지하는가

### Knowledge 작성

- 한 객체에 하나의 원자 주장
- 변수·단위·가정·적용 범위
- 예외·한계·invalid outside
- Evidence와 관련 Knowledge

### Rule 작성

Rule에는 사람이 읽는 조건과 기계가 실행하는 조건을 함께 둔다. Rule은 이미 검토된 Knowledge를 비교·적용하며 새로운 사실을 만들지 않는다.

### Qualification

각 결정 규칙에는 최소한 명확한 위반, 조건 내 일치, 필수 조건 누락, 적용 범위 이탈, 실증 필요, 부정문, 단위 변형, 모호성, paraphrase, false-red 방지 사례가 있어야 한다.

## 16. Science Release

Science Release는 Source·Evidence·Knowledge·Rule·Ontology binding·Qualification Case의 정확한 버전을 고정한 불변 패키지다.

```yaml
release:
  release_id: science-foundation/2026.1.0
  schema_version: sci-profile/0.1
  content_hash: sha256:...
  status: release_candidate
  component_digests: []
  known_limitations: []
```

상태는 `release_candidate`, `active`, `superseded`, `withdrawn`을 사용한다. 활성 Release의 객체를 직접 수정하지 않는다.

### Release Gate

| Gate | 확인 내용 |
|---|---|
| G0 구조 | schema, ID, 참조, 필수 필드 |
| G1 근거 | 결정 Knowledge의 정확한 Evidence Span |
| G2 과학 검토 | 정의·수식·조건·예외·범위 |
| G3 규칙 검증 | 단위·조건·부호·범위·결정성 |
| G4 판정 사례 | 다섯 Verdict와 경계 사례 |
| G5 독립 실패 사례 | 개발에 쓰지 않은 holdout |
| G6 설명 추적 | 빨간 표시에서 원문까지의 경로 |
| G7 권한 | 필요한 검토·승인·활성화 기록 |

종합점수로 Gate 실패를 상쇄하지 않는다. 다음 항목은 활성화 시 0건이어야 한다.

- 깨진 Evidence locator
- 원문 hash 불일치
- 근거 없는 결정 규칙
- 해결되지 않은 결정 경로 충돌
- 동일 Claim Packet의 비결정적 판정
- 필수 holdout 오판
- 모호한 주장의 false-red
- 근거 연결이 없는 결정적 설명 문장

미지원 범위는 실패가 아니다. Release manifest에 지원·부분 지원·미지원 범위를 명시한다.

### 충돌 처리

같은 용어인지, 가정·범위·측정 방법이 같은지 먼저 확인한다. 조건이 다른 결론은 충돌이 아닐 수 있다. 동일 대상·조건·범위에서 결론이 양립하지 않을 때만 실제 충돌 후보로 다룬다.

해결되지 않은 항목은 Release Candidate에서 격리하고 활성 판정 경로에서 제외한다. Source 수, 인용 수, LLM 선택으로 결정하지 않는다.

잘못된 활성 Release는 삭제하지 않고 `withdrawn`으로 바꾼다. 새 검증은 마지막 안전 Release로 되돌리거나 안전한 Release가 없으면 운영 오류로 멈춘다. 과거 보고서는 자동 재판정하지 않는다.

## 17. API와 MCP 계약

이름은 구현 계획에서 기존 route 규칙에 맞게 확정하되 책임은 다음처럼 분리한다.

### 일반 검증

- `science_aliases_detect`: 문서에서 등록된 별칭과 정확한 text span을 결정론적으로 반환
- `science_claim_submit`: 사용자·Codex·Claude·Qwen 등이 만든 구조화 Claim 후보를 untrusted proposal로 제출; 서버가 span·개념 역할·ontology refs·조건을 재검증
- `science_interpret`: 선택적·실험적 Qwen 해석 어댑터. 실패 시 어떤 Claim·판정·빨간 표시도 만들지 않음
- `science_verify_claim`: 확정 Claim Packet을 결정적으로 검증
- `science_verify_document`: 여러 Claim의 검증 작업 조정
- `science_evidence_get`: 사용자가 볼 수 있는 원문·번역·locator 반환
- `science_report_get`: 저장된 Verification Report 반환
- `science_report_export`: Markdown·PDF 내보내기
- `science_proposal_create`: 해석·용어·지식 개선 제안

### 관리

- `science_source_validate`
- `science_knowledge_validate`
- `science_rule_qualify`
- `science_release_validate`
- `science_release_activate`
- `science_release_withdraw`

모든 endpoint는 BoI Profile ACL과 Science 역할 권한을 함께 검사한다. MCP는 같은 API를 감싸며 자체 판정 로직을 갖지 않는다.

## 18. Harness와 Skill

### Harness

1. Science Source Curation Harness
   - 공식 Source·판·URL·checksum
   - Evidence Span·번역·locator 검증
2. Science Knowledge Authoring Harness
   - 원자 지식·가정·범위·관계
   - `sci-profile`과 Evidence 연결
3. Science Rule Qualification Harness
   - 단위·수식·조건 검사
   - 다섯 Verdict·false-red·holdout
4. Science Verification Harness
   - span 정렬·Claim Packet·Verdict Packet
   - 문장별 근거·Markdown·PDF 동등성

### 사용자 Agent Skill

`boi-science-verifier`는 Codex·Claude 등 사용자의 Agent가 설치해 사용한다.

- 선택 영역이나 문서를 BoI API/MCP에 제출한다.
- 결과를 바꾸는 모호성만 사용자에게 확인한다.
- BoI가 반환한 Verdict를 변경하지 않는다.
- Evidence와 원문 링크를 함께 표시한다.
- 자체 지식으로 Citation이나 판정을 보완하지 않는다.

### 관리자 Skill

`boi-science-curator`는 Admin과 Power User의 Source·Knowledge·Rule 작성 작업을 돕는다. Skill은 초안과 검증 요청을 만들 수 있지만 자기 결과를 승인하지 못한다.

두 Skill은 과학 지식 본문을 내장하지 않고 활성 Science Release를 API/MCP로 사용한다.

## 19. 저장소와 자료 보관

OKF Markdown과 Git은 Science metadata와 검토된 지식의 정본이다. 검색 index, embedding, ontology projection은 다시 만들 수 있는 read model로 유지한다.

권장 구조:

```text
data/boi/public/science/
  sources/
  evidence/
  knowledge/
    common/
    physics/
    chemistry/
    circuits/
    materials/
    semiconductor-devices/
    spin-coating/
  rules/
  packs/
  qualification/
  releases/

harness/
  science-source-curation-harness.md
  science-knowledge-authoring-harness.md
  science-rule-qualification-harness.md
  science-verification-harness.md

skills/
  boi-science-verifier/
  boi-science-curator/
```

긴 PDF·원본 파일·데이터셋은 자료 보관함에 두고 OKF에는 ACL URL, Source metadata, checksum, locator, profile을 남긴다. Agent와 UI는 저장소에 직접 접속하지 않고 BoI API/MCP를 사용한다.

일반 사용자용 결정 Evidence는 그 사용자가 열람할 수 있어야 한다. Restricted Source를 사용한 팀 전용 Rule은 같은 ACL을 가진 사용자에게만 적용한다.

## 20. LLM 구성

Science Verifier 웹 경로의 기본 동작은 LLM을 요구하지 않는다. 결정론적 별칭 탐지와 사용자가 확인·수정한 구조화 Claim만으로 검증을 완료할 수 있다. Qwen은 기존 OpenAI-compatible 설정을 재사용할 수 있는 선택적·실험적 해석 어댑터로만 보존한다.

```text
BOI_SCIENCE_LLM_BASE_URL → BOI_LLM_BASE_URL 상속
BOI_SCIENCE_LLM_MODEL → BOI_LLM_MODEL 상속
BOI_SCIENCE_LLM_API_KEY → BOI_LLM_API_KEY 상속
```

Pilot 배포에서는 사용자가 지정한 사내 LM Studio endpoint와 `qwen/qwen3.8-27b`를 추적되지 않는 `.env` overlay로 설정한다. 내부 endpoint를 저장소 문서·코드·fixture에 하드코딩하지 않는다.

실험적 어댑터는 기본값이 비활성이다. 연결 실패, timeout, 빈 content, invalid JSON, schema mismatch를 모두 fail-closed 처리한다. 이 경우 Claim, Evidence, Rule, verdict, 빨간 표시를 만들지 않으며 모델 재시도·튜닝을 운영 검증의 전제 조건으로 삼지 않는다.

- Claim Packet이 확정돼 있으면 결정적 검증은 계속할 수 있다.
- 새 자연어 해석은 결정론적 별칭 탐지 뒤 사용자가 직접 작성하거나 Codex·Claude 등 외부 Agent가 후보를 제출할 수 있다.
- Evidence·Verdict는 LLM 가용성과 무관하게 보존한다.

## 21. Spin Coating 응용 증명

입력 예시:

> Photo Track에서 Spin Coating 두께를 높이려면 RPM을 높여야 한다.

처리 흐름:

1. `RPM`을 회전속도 후보로, `두께`를 film thickness 후보로 해석한다.
2. dispense·spread·final spin 중 어느 단계인지 확인한다.
3. wet·dry·post-bake thickness 중 어느 측정 상태인지 확인한다.
4. resist, viscosity, solids, time, temperature, exhaust와 유효 범위를 확인한다.
5. 모델 가정·수지·유동·증발 Knowledge를 해결한다.
6. 조건이 확정되고 검토된 관계와 반대이면 `VIOLATION`을 반환한다.
7. 조건이 빠졌으면 보라색 모호성 또는 `INSUFFICIENT_INFORMATION`으로 멈춘다.
8. 특정 장비의 수치 변화량은 Qualified Data가 없으면 `EMPIRICAL_VERIFICATION_REQUIRED`로 판정한다.

교정 설명은 final spin 속도 증가가 방사 방향 유출과 박막화를 강화한다는 메커니즘을 설명하되, 실제 지수와 변화량은 resist·장비·환경에 따라 달라짐을 명시한다. 공정 변경량이나 DOE 시작점을 제안하지 않는다.

Spin Coating 전용 예외 코드를 두지 않는다. 같은 Foundation 규칙은 다음 사례에도 적용되어야 한다.

- 섭씨–켈빈 affine 변환
- 정확도와 정밀도 혼동
- 높은 R²를 모델의 진실로 해석하는 오류
- 정상 유동과 평형 혼동
- 개방계 질량 감소와 보존 위반 혼동
- 고정 전압·고정 전류에서 저항–전력 관계
- 촉매와 평형상수 관계
- 박막과 bulk 물성의 무조건적 동일시
- doping과 mobility·conductivity의 조건부 관계
- MOS gate current와 이상 모델의 범위

## 22. Qualification Report

최종 PoC는 성공 화면만 보여주지 않고 다음 보고서를 만든다.

- 사용한 Foundation·Domain·Application Release
- 검증 대상과 미지원 범위
- Claim별 기대 판정과 실제 판정
- 검출한 과학적 오류
- 놓친 오류
- false-red
- 잘못된 용어·주장 해석
- 적용 범위 처리 오류
- 잘못되거나 끊어진 Evidence locator
- 근거 없는 설명 문장
- 수정한 Knowledge·Rule
- 재발 방지 테스트

가장 심각한 실패는 과학적으로 확정할 수 없는 문장을 빨간색으로 표시하는 false-red다. 독립 holdout에는 반드시 모호성·조건 누락·이상 모델·범위 이탈 사례를 포함한다.

## 23. 구현 단계의 완료 기준

구현 계획은 이 명세 승인 후 별도로 작성한다. 제품 완료 주장은 최소한 다음 조건을 요구한다.

1. `SOP` 다음에 Science Verifier 메뉴가 보인다.
2. 전용 문서 검토 화면과 Wiki 선택 영역 진입이 같은 검증 흐름을 사용한다.
3. 빨간 표시와 보라색 표시가 정확한 원문 span에 고정된다.
4. 결과가 달라지는 모호성만 사용자에게 확인한다.
5. 동일 Claim Packet과 Release는 동일 Verdict와 Evidence 경로를 반환한다.
6. LLM이 Verdict·Citation을 만들거나 변경할 수 없다.
7. 일반 사용자가 펼쳐보기에서 원문·번역·locator·설명을 확인한다.
8. Markdown·PDF 보고서가 같은 판정 데이터를 사용한다.
9. User·Power User·Admin 권한 경계와 자기 승인 금지가 검증된다.
10. 활성 Release가 직접 수정되지 않는다.
11. SCI-COM-001~012와 여섯 Domain/Application Pack이 자격 검사를 통과한다.
12. 범용 실패 사례와 Spin Coating 사례를 포함한 독립 보고서가 생성된다.
13. false-red, 깨진 Evidence locator, 근거 없는 결정 규칙이 0건이다.
14. Web·REST·MCP가 같은 Verdict Packet을 반환한다.
15. 기존 OKF·SOP·Inbox·Action 기능과 core DB-less 경계가 유지된다.

## 24. 구현 순서 원칙

구현 계획은 다음 의존 순서를 따라야 한다.

1. `sci-profile`과 저장 객체 계약
2. Release manifest·lint·qualification 기반
3. Claim Packet·Verdict Packet과 결정적 검증기
4. Science Source·Evidence·Foundation 지식
5. Physical·Chemical·Circuit Domain Pack
6. Materials Science·Semiconductor Devices Domain Pack
7. Spin Coating Application Pack
8. 문서 중심 Web UX와 보고서 내보내기
9. MCP·사용자 Agent Skill·관리자 Harness
10. 독립 holdout과 최종 Qualification Report

UI부터 만들고 뒤늦게 지식을 끼워 넣거나, Source를 대량 수집한 뒤 판정 계약을 정하는 순서는 피한다. 먼저 어떤 객체와 규칙이 판정 자격을 갖는지 고정한 다음 지식과 화면을 확장한다.
