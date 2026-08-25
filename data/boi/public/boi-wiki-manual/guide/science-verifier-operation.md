---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Science Verifier 운영과 신뢰 경계
description: 문서 중심 Science Verifier의 LLM 없는 검증 경로, 외부 Agent 연결, 역할, Release 승인, 장애 처리와 검증 기준
tags: [Manual, ScienceVerifier, Evidence, MCP, REST, TrustBoundary]
timestamp: 2026-08-25T18:00:00+09:00
boi_id: boi:public:boi-wiki-manual:guide:science-verifier-operation
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: draft
source_refs:
  - type: repo
    ref: boi_api/app/science/
  - type: repo
    ref: boi_wiki_mcp/app/main.py
  - type: repo
    ref: harness/science-verification-harness.md
  - type: repo
    ref: harness/science-equation-knowledge-harness.md
  - type: repo
    ref: docs/superpowers/specs/2026-08-25-science-verifier-design.md
review:
  reviewer: pending-human-admin
  review_status: pending
---

# Summary

Science Verifier는 AI 답변을 신뢰하는 기능이 아니다. 사용자·Codex·Claude·Qwen은 문서에서 찾은 과학적 주장의 **구조화된 해석 후보**만 제출한다. 서버가 문서 구간, 등록 별칭, ontology reference, subject/relation/object 역할, 조건을 다시 검사하고, 사람이 확인한 Claim만 활성 Science Release의 Rule·적용 조건·Evidence로 결정론적으로 판정한다.

현재 저장소의 Science Release는 후보 상태다. 구현과 자동 검증이 끝나더라도 독립 holdout과 사람 Admin 승인이 없으면 활성 Release 또는 운영 검증 완료로 표현하지 않는다.

# 기본 사용자 흐름

1. `SOP` 다음의 `Science Verifier`를 열고 문서를 붙여 넣거나 Wiki 문서의 선택 영역에서 검토 화면으로 이동한다.
2. `등록 용어 찾기`가 서버의 `POST /api/science/aliases/detect`를 호출한다. 이 단계는 Claim이나 verdict를 만들지 않는다.
3. 사용자가 subject, relation, object, 조건과 문서 구간을 확인·수정한다. Codex·Claude 같은 외부 Agent가 같은 구조의 후보를 제출해도 서버 검사는 동일하다.
   - Agent가 넣은 수량·조건은 곧바로 Rule 적용 사실이 되지 않는다. 사용자 화면에서 값과 단위를 명시적으로 확인하고 `client_kind=user`의 새 Claim으로 다시 제출해야 한다.
   - Agent가 넣은 공정 단계·물질 상태도 자기 선언한 모호성 여부와 무관하게 차단한다. 사용자가 화면에서 직접 작성한 새 Claim만 적용 조건 후보가 된다.
   - 수식이 있으면 Agent는 정확한 수식 구간, 의미식 후보, 기호별 개념·수량·단위·조건 후보만 제출할 수 있다. 이것도 해석 제안일 뿐이다. 서버가 문서에 실제로 있는 완전한 구간인지, 기호가 실제 문맥에 있는지, 등록되지 않은 변수를 만들지 않았는지 다시 검사한다.
4. 결과를 바꿀 수 있는 모호성만 보라색 점선으로 표시한다. 사용자가 확인하면 그 Claim만 새 immutable interpretation으로 다시 검증한다.
   - 직접 붙여 넣은 문서를 수정할 때는 서버가 돌려준 submitted document ref와 이전 digest를 함께 보낸다. 서버가 같은 actor의 실제 선행 Claim을 확인한 경우에만 `supersedes_claim_id` 계보를 잇고, 이전 record는 변경하지 않는다. raw pasted document는 이 owner-only semantics를 유지한다.
   - Wiki local revision은 원본 `boi:*`를 고치지 않는다. 서버가 원본 Wiki의 exact ref/digest와 source ACL을 다시 확인한 뒤에만 server-derived `boi:submitted:*` lineage를 만든다. 이 canonical source ref/digest는 submit, confirm, `verify_claim`, `verify_document`마다 재확인되고 저장소 재시작 뒤에도 보존된다. lineage가 누락·위조·malformed면 예전 record나 client payload로 보완하지 않고 fail closed한다.
5. 활성 Release가 없거나 Rule·적용 조건·정확한 Evidence locator가 부족하면 판정을 보류한다. 빨간 표시를 만들지 않는다.
6. 결정론적 `VIOLATION`에만 빨간 밑줄과 음영을 표시한다. 교정 카드에는 충분한 과학적 설명과 출처 1~2개를 항상 보이고, 펼쳐보기에서 원문·검토된 번역·locator·원본 URL을 제공한다.

# 수식 지식과 설명 경로

수식은 LaTeX 문자열 하나로 저장하거나 평가하지 않는다. 수식을 포함한 Science Knowledge만 다음 정보를 가진 검토된 Equation 객체를 함께 보존한다.

- 고정된 `equation_id`, `equation_digest`, 과학적 역할과 `decision_use`
- 허용된 연산자만 사용하는 versioned closed semantic expression
- 표시용 LaTeX, 일반 텍스트, 접근성용 읽기 표현
- 모든 변수의 기호·개념·quantity kind·차원·단위·정의역·부호·범위
- assumptions, applicability, invalid-outside, boundary condition, 근사·오차·fitting 범위
- 원문 표기, BoI 표준 변수와의 대응, EvidenceUse, 원본 URL·digest와 정확한 equation locator·quote hash

의미 표현과 표시 표현은 분리한다. LaTeX는 읽기 위한 표현이며 판정 권한이 없다. `deterministic_rule`은 지원 evaluator의 정확한 ID·version·digest와 Rule variable mapping이 검토된 Equation에 묶인 경우에만 판정에 사용할 수 있다. 합·적분·미분·행렬·벡터·화학 반응식처럼 현재 evaluator가 지원하지 않는 복잡한 표현은 `explanation_only`로 보존하고 보여줄 수 있지만, 그 수식만으로 빨간 표시를 만들 수 없다. 범용 CAS, 임의 코드, LLM 수식 동치 판단은 운영 Truth Path에 포함하지 않는다.

과학적 설명도 Agent의 자유로운 prose 한 덩어리가 아니다. stored report는 적용 원리, 검토된 수식, 변수 의미, 적용 조건, Claim과 변수의 대응, 과학적 귀결, 교정문, 한계, Evidence 순서의 grounded block을 저장한다. 각 block은 Knowledge·Equation·Rule·Evidence·Source의 정확한 ID와 digest, locator, quote hash 범위에 묶인다. 정의되지 않은 값이나 중간 조건은 채워 넣지 않고 판정을 보류한다.

Web 설명은 검토된 수식과 읽기 표현을 함께 제공하고, 변수 의미와 적용 조건을 펼쳐볼 수 있게 한다. 모바일의 긴 수식은 가로로 스크롤하며, LaTeX와 일반 텍스트를 각각 복사할 수 있다. 로컬 renderer는 외부 URL·파일·이미지, raw HTML, 위험한 macro와 무제한 확장을 차단하고 저장된 SVG digest를 다시 확인한다. 렌더링이 실패하면 일반 텍스트 fallback을 명확히 보이되 verdict나 빨간 표시를 만들거나 바꾸지 않는다.

# REST와 MCP 계약

| 단계 | REST | MCP | 권위 |
|---|---|---|---|
| 등록 별칭 탐지 | `POST /api/science/aliases/detect` | `science_aliases_detect` | 정확한 Unicode 구간과 활성화와 무관한 해석 후보만 반환 |
| Claim 후보 제출 | `POST /api/science/claims/submit` | `science_claim_submit` | 모든 클라이언트 입력을 untrusted로 재검증 |
| 사용자 확인 | interpretation confirm endpoint | `science_interpretation_confirm` | 인증된 사용자의 명시적 확인만 허용 |
| 결정론적 검증 | claim/document verify endpoint | `science_verify_claim`, `science_verify_document` | 활성 Release의 Rule만 판정 |
| 근거 확인 | evidence endpoint | `science_evidence_get` | ACL이 허용한 원문·번역·locator·URL. 단독 조회는 운영 적격성을 주장하지 않음 |
| 보고서 | report/export endpoint | `science_report_get`, `science_report_export` | 같은 stored report를 Markdown/PDF로 표현 |

Claim 제출 payload에 `verdict`, `rule`, `evidence`, `citation`, `correction`을 넣어도 서버가 권위로 받아들이지 않는다. 수식 후보의 `equation_id`, digest, 의미식, 변수·단위·조건도 모두 서버 재검증 대상이며 Agent가 제시한 Equation identity 자체를 신뢰하지 않는다. 존재하지 않는 `ontology_ref`, 문서에 없는 별칭, 겹치거나 불완전한 역할·수식 구간, 미확인 조건은 판정 전에 차단한다. 같은 canonical Claim과 Release는 `client_kind`가 user, codex, claude, qwen 중 무엇이든 같은 결과를 내야 한다.

최종 구현 증거 보고서는 현재 Git revision과 tracked pytest suite identity 계약(각 suite의 수량·testcase identity digest, 최소 한 건의 실제 실행)이 묶인 JUnit, verification manifest가 요구하는 모든 named browser check와 각 캡처 hash, Candidate qualification, exact-commit 독립 리뷰의 Critical·Important 0건이 모두 일치할 때만 `FINAL / VERIFIED`로 표기할 수 있다. 이 표기는 구현 증거가 완결됐다는 뜻일 뿐 과학적 진실·안전·공정 승인·Release activation은 뜻하지 않는다. 환경상 실행할 수 없는 계약 테스트가 있으면 정확한 node ID allowlist와 사유를 보고서에 그대로 노출한다. PPT는 exact `FINAL` verification manifest, UI digest, 검증된 PDF render, tracked clean source를 읽지 못하면 생성하지 않는다. build scorecard의 사람 visual QA는 실제 검토 전까지 `PENDING`이다.

stored report의 과학적 의미에는 `report_digest`를 사용하고, Markdown/PDF로 실제 내보낸 bytes에는 별도 `export_digest`를 사용한다. renderer 버전이나 조판 bytes가 달라져도 Knowledge·Equation·Rule·Evidence와 verdict가 같다면 과학적 `report_digest`는 달라지지 않는다. REST와 MCP는 내보낸 bytes의 digest를 각각 다시 확인하며, Web·Markdown·PDF는 같은 stored Equation ID·digest, 변수, 조건, Evidence, locator, verdict와 Rule identity를 사용한다.

# Qwen 실험 어댑터

Qwen은 선택적·실험적 웹 해석 어댑터다. 기본값은 `BOI_SCIENCE_EXPERIMENTAL_LLM_ENABLED=0`이며, 일반 검토와 검증은 Qwen 없이 완료되어야 한다.

연결 불가, timeout, 빈 content, invalid JSON, schema mismatch는 모두 fail-closed다. 이 실패로 Claim, Rule, Evidence, verdict 또는 빨간 표시를 만들지 않는다. 모델의 context 길이와 endpoint는 추적되지 않는 배포 환경에만 두며, 모델 튜닝은 운영 판정의 전제 조건이 아니다.

관련 배포 변수:

```text
BOI_SCIENCE_EXPERIMENTAL_LLM_ENABLED=0
BOI_SCIENCE_ACCESS_MODE=admin_only
BOI_SCIENCE_DICTIONARY_RELEASE_ID=boi:dictionary:current/0.1.0
BOI_SCIENCE_ONTOLOGY_RELEASE_ID=sci:ontology:general-science-draft/0.1.0
SCIENCE_RUNTIME_ROOT=/runtime/science
```

실험 어댑터를 켤 때만 `BOI_SCIENCE_LLM_BASE_URL`, `BOI_SCIENCE_LLM_MODEL`, `BOI_SCIENCE_LLM_API_KEY` 등 `.env` 값을 사용한다. 내부 endpoint와 credential은 코드·문서·fixture·보고서에 기록하지 않는다.

# 역할과 승인

| 역할 | 초기 Pilot 권한 |
|---|---|
| User | 문서 검토, Claim 확인·수정, 허용된 Evidence 열람, 보고서 조회 |
| `science.power_user:<domain>` | 지정 도메인의 별칭·용어·해석·개념 연결 제안 검토. 자신이 만든 제안은 승인 불가 |
| `science.admin` | Source/Evidence, 법칙·수식·Rule과 evaluator binding 검토, Release 검증·활성화·철회 |

용어 수정과 검증 중 수정은 분리한다. `이번 검증에서 수정`은 해당 Claim의 새 interpretation만 만들고, `개선 제안`은 별도 proposal을 만든다. 제안이 Release Candidate에 포함되더라도 현재 검증 결과나 전역 지식을 즉시 바꾸지 않는다.

# 빨간 표시의 필수 조건

다음 조건이 모두 충족돼야 한다.

- exact active Release와 immutable digest가 확인됨
- verdict가 정확히 `VIOLATION`
- 결정 Rule이 active이고 Claim이 Rule 적용 범위 안에 있음
- 수식형 Rule이면 active Release의 exact Equation ID·digest와 지원 evaluator binding이 일치함
- 필수 적용 조건이 충족됨
- 결정 Evidence가 active이고 원문 hash와 locator가 검증됨
- 빨간 text span이 canonical document의 Claim 구간과 일치함

하나라도 부족하면 `INSUFFICIENT_INFORMATION`, `OUTSIDE_VALIDITY_DOMAIN`, `EMPIRICAL_VERIFICATION_REQUIRED` 또는 verification unavailable로 보류한다. Ontology는 용어 해석과 지식 탐색을 도울 뿐 verdict를 만들지 않는다. AI가 작성한 설명도 승인된 Knowledge statement와 결정 Evidence 범위를 넘어서는 권고를 추가하지 않는다.

# 운영 검증과 완료 경계

자동 검증은 disabled-Qwen 및 Qwen 장애 5종, 잘못된 ontology/alias/span, 수동 수정, Wiki local revision의 ACL·source lineage, REST/MCP/client parity, inactive Release, 근거 없는 빨간 표시, 저장소 재시작과 idempotency를 포함한다. 수식 경로는 원문 전사·변수·차원·정의역·원문 대응·evaluator binding, 잘못된 부호·지수·연산자·단위·근사 과장·범위 밖 외삽, 지원하지 않는 의미식과 악성 LaTeX의 fail-closed도 검사한다. Browser evidence에는 disabled-Qwen API boundary, Wiki local revision path, 검토된 수식의 안전한 표시·fallback·모바일 scroll·digest 경계를 포함해 verification manifest에 고정된 모든 named check와 capture hash가 필요하다. Web·REST·MCP·Markdown·PDF의 active stored-report parity는 Claim ID, verdict, Evidence ID, Release ID, report digest뿐 아니라 Equation ID·digest·변수·조건·Rule·locator가 같아야 한다. inactive Candidate의 렌더러 QA를 active stored-report 검증으로 표현하지 않는다.

자동 Candidate qualification `G0..G4`가 통과해도 Release는 `release_candidate`/inactive다. 다음은 자체 증거가 생기기 전까지 `PENDING`이다.

- `G5`: 개발에 쓰지 않은 독립 sealed holdout 평가
- `G6`: 활성 Release의 stored-report Web/REST/MCP/Markdown/PDF parity
- `G7`: Admin의 Source·Evidence·Knowledge·Rule 원문 검토와 Release activation audit
- 운영 데이터에 대한 별도 qualification

문제가 있는 활성 Release는 삭제하지 않고 withdraw한다. 과거 보고서는 당시 Release digest와 함께 immutable하게 보존한다.

# 현재 수식 지원 범위

현재 결정론적 evaluator는 등록된 작은 연산자 집합과 정확히 연결된 Rule만 지원한다. Physics의 work-energy, Chemistry의 molar concentration, Circuits의 KVL 관계가 일반성 검증용 deterministic 예시다. Semiconductor conductivity, Materials diffusion의 Arrhenius 관계, Spin Coating power-law는 검토된 지식과 표시 경로를 시험하지만 현재 `explanation_only`다. 합·적분·미분, 행렬·벡터, 화학 반응 화살표도 renderer와 PDF 조판의 범용성 QA에는 포함하되 판정식으로 사용하지 않는다.

이 범위는 특정 Spin Coating 사례에 맞춘 예외 로직이 아니다. 새 도메인은 권위 있는 Source·Evidence와 정확한 locator를 적재하고, Equation·Rule·evaluator를 qualification한 뒤, 독립 holdout과 Admin activation을 거쳐 같은 계약으로 확장한다.
