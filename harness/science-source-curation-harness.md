---
title: Science Source Curation Harness
type: boi/harness
status: draft
---

# Science Source Curation Harness

## Purpose

Science Verifier가 인용할 Source와 Evidence span을 재현 가능하게 제안한다. AI는 출처 후보를 찾는 것과 초안을 만드는 데만 쓰며, 과학 판정이나 승인 주체가 아니다.

수식을 포함한 Source/Evidence는 반드시 `science-equation-knowledge-harness.md`의 전사·변수 정의·표기 대응 계약도 적용한다.

## Inputs

- 권위 있는 원본의 `original_url`, DOI, 저자·기관, 판본·개정일
- 실제 요청 주소 `requested_url`과 redirect 후 `resolved_url`
- 합법적으로 열람한 원문 bytes 또는 정확히 제한된 접근 실패 응답
- Source/Evidence ID, 분류·ACL, 예상 claim family
- 수식이면 exact equation locator, 원문 수식과 주변 variable/sign/unit 정의, OCR/visual transcription review
- 제안자 identity와 별도의 `science.admin` reviewer identity

## Observation

HTTP 상태, content type, redirect chain, retrieval 시각, 원문 버전, 접근 제한을 그대로 기록한다. `retrieved_resource_hash`, Source `content_hash`, Evidence `original_text_hash`, `claim_scope_hash`는 서로 다른 hash scope다. 초록만 열람했거나 publisher full text가 막힌 경우에는 그 사실을 숨기지 않고 원문 Evidence로 승격하지 않는다.

## Context

Evidence에는 `exact locator`를 둔다. PDF는 PDF page index와 printed page, section·equation·figure를 함께 기록하고, HTML은 heading·sentence ordinal·prefix·suffix를 기록한다. 원문 `original_text`, Admin 검토 전 한국어 `reviewed_translation`, `original_url`, locator, hash를 한 경로로 연결한다. 번역은 원문을 대체하지 않는다.

수식은 원문 expression hash를 별도로 보존한다. 부호·등호/부등호·지수·첨자·분자/분모·미분 기호·단위·근사 조건·유효 범위와 원문 앞뒤의 기호 정의가 검토되지 않으면 판정 가능한 Equation Evidence가 아니다.

`claim_scope.allowed_claims`는 해당 span이 직접 지지하는 최소 claim family와 `purpose`만 허용한다. 정의 한 문장으로 대조·인과·방향성을 확대하지 않는다. inactive Evidence는 Knowledge의 `excluded_evidence_refs`로만 설명할 수 있고 판정 근거가 될 수 없다.

## Control

- 모든 agent 산출물은 `draft`, `pending_review`, `blocked_pending_authorized_admin_review`다.
- `science.admin`만 법칙·수식·Evidence·Source의 승인 결정을 기록한다.
- 제안자와 reviewer가 같은 self-approval은 금지한다.
- 승인·withdraw·재수집은 exact object digest와 `user_confirmed: true`에 묶는다.
- license, ACL, 접근 권한을 확인하지 못하면 공개 원문 endpoint를 만들지 않는다.
- LLM, RAG, 검색 결과 snippet은 그 자체로 판정 근거가 아니다.

## Action

1. 원본 기관·출판사·표준기관 URL을 우선 확인한다.
2. `requested_url`과 `resolved_url`을 저장하고 resource bytes를 해시한다.
3. 가장 짧은 결정 가능 span과 `exact locator`를 추출한다.
4. `original_text_hash`와 locator context hash를 계산한다.
5. 번역, access limitation, license, ACL, `decision_eligibility`를 기록한다.
6. 허용 claim family, 정확한 `purpose`, required conditions와 금지 범위를 작성한다.
7. Source와 Evidence를 제안 상태로 validation하고 Admin review queue로 보낸다.
8. 별도 Admin이 원본을 직접 열어 확인한 뒤에만 `authorized_review_events`를 기록한다.

## State

`draft → pending_review → approved | rejected | withdrawn` 상태를 append-only review event로 남긴다. approved Source라도 Evidence span마다 별도 검토한다. 활성 Release가 참조한 bytes는 수정하지 않고 새 version을 만든다.

## Verification

- URL을 다시 열어 version·locator·quote가 일치하는지 검사한다.
- 모든 hash를 원래 hash scope로 재계산한다.
- translation이 수식·부정·조건·단위를 바꾸지 않았는지 원문과 대조한다.
- Equation 전사와 OCR review가 `science-equation-knowledge-harness.md`의 original notation/mapping 검사를 통과하는지 확인한다.
- Rule의 각 `EvidenceUse.claim_family`와 `purpose`가 allowed scope와 exact match인지 검사한다.
- 일반 User가 ACL 범위 안에서 원문, 번역, locator, URL, `original_text_hash`를 펼쳐 볼 수 있는지 확인한다.
- AI가 만든 설명이 Source 문장보다 넓은 claim을 생성하면 release-blocking으로 분류한다.

## Failure Artifacts

실패 시 source/evidence ID, 요청·최종 URL, 상태 코드, locator, 기대·실제 hash, claim scope diff, ACL/license 결정, actor, 시각만 남긴다. credential·사내 endpoint·전체 유료 원문은 남기지 않는다.

## Release-Blocking Conditions

- broken URL/locator, hash mismatch, 원문과 번역 불일치
- 초록만 확보했는데 full-text 법칙·수식으로 사용
- `decision_eligibility` inactive/pending인데 active decision path에 포함
- EvidenceUse overclaim 또는 출처 없는 과학적 설명
- Admin 승인 event 부재, self-approval, ACL/license 미확인

| Gate | 이 하네스의 통과 조건 |
|---|---|
| G0 | sci-profile과 ID·hash schema가 유효하다. |
| G1 | Source/Evidence 원문·locator·claim scope가 재현된다. |
| G2 | Knowledge가 허용 Evidence 범위를 넘지 않는다. |
| G3 | Rule EvidenceUse가 exact scope에 묶인다. |
| G4 | 공개 qualification case의 decisive Evidence가 열린다. |
| G5 | 독립 holdout에서도 locator와 scope가 유지된다. |
| G6 | Web/REST/MCP/export가 같은 Evidence identity를 보인다. |
| G7 | 별도 Admin review와 immutable Release만 활성화된다. |
