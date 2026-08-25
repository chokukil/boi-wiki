---
okf_version: "0.1"
boi_profile_version: "0.1"
sci_profile_version: "0.1"
type: boi/harness
title: Science Verification Harness
description: 문서 해석부터 판정·근거·채널 parity까지 검증하는 운영 기준
tags: [BoIWiki, ScienceVerifier, Harness]
timestamp: 2026-08-25T16:00:00+09:00
boi_id: boi:public:harness:science-verification-harness
visibility: public
classification: internal
owner: science-admin
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: draft
source_refs:
  - type: repo
    ref: harness/science-verification-harness.md
  - type: repo
    ref: data/okf/profiles/sci-profile.yaml
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
---
# Science Verification Harness

## Purpose

문서 중심 Science Verifier가 해석 오류를 판정으로 승격하지 않고, 결정론적 판정·과학적 설명·원문 근거를 동일한 보고서로 제공하는지 검증한다. BoI는 새 과학 Agent가 아니라 사용자 Agent가 호출하는 Scientific Integrity Layer다.

## Inputs

- ACL 확인된 document bytes와 Unicode code point selection anchor
- 결정론적으로 탐지된 등록 alias와 pinned Dictionary/Ontology Release
- User·Codex·Claude·선택적 Qwen이 REST/MCP로 제출한 untrusted Claim 후보
- 명시적으로 확인된 Claim Packet
- exact Foundation/Domain/Application Release selection
- stored Verification Report와 Web/REST/MCP/Markdown/PDF 표현

## Observation

문서에서 정확한 source span, interpretation candidates, outcome-changing ambiguity, Rule reason codes, Knowledge/Evidence/Source identities를 관찰한다. Wiki local revision에는 canonical source ref/digest와 ACL 재검사 결과, server-derived submitted lineage를 함께 관찰한다. 모델 ID와 prompt version은 provenance일 뿐 과학 권위가 아니다. endpoint·credential·transport cause는 저장하거나 표시하지 않는다.

## Context

AI 해석은 proposal이다. `POST /api/science/aliases/detect`는 등록 alias의 exact Unicode code point 구간만 반환하며 Claim이나 verdict를 만들지 않는다. `POST /api/science/claims/submit`과 MCP `science_claim_submit`은 User·Codex·Claude·Qwen 후보를 같은 closed schema로 받아 서버가 subject/object/relation binding, 조건 schema, alias, complete non-overlapping relation span을 다시 검증한다. Qwen은 optional/experimental adapter이며 연결 실패·timeout·빈 응답·invalid JSON·schema mismatch가 Science Verifier 판정 실패나 빨간 표시로 이어지지 않는다. 결과가 달라질 모호성이 있으면 보라색 점선으로 멈춘다. 명시적 user confirmation 뒤 exact Claim만 판정한다. deterministic Rule이 in-scope contradiction을 확정한 span만 빨간색 밑줄과 음영을 받는다.

`VIOLATION`, `CONSISTENT`, `INSUFFICIENT_INFORMATION`, `OUTSIDE_VALIDITY_DOMAIN`, `EMPIRICAL_VERIFICATION_REQUIRED` 외 verdict를 만들지 않는다. CONSISTENT는 검사 범위 내 모순 미발견이며 참·안전·승인·공정 qualification을 뜻하지 않는다.

## Control

- 일반 User는 문서 검증과 허용된 원문 Evidence 열람만 한다.
- domain Power User는 alias·용어·해석·concept link 제안을 승인할 수 있으나 법칙·수식·Rule·Evidence·Release는 승인할 수 없다.
- `science.admin`만 component review와 Release activation/withdrawal을 한다.
- proposer/reviewer self-approval을 금지한다.
- interpretation 확인, proposal, approval, activation, withdrawal에는 `user_confirmed: true`와 actor-bound idempotency key가 필요하다.
- AI·MCP·UI·export는 verdict/evidence/citation을 변경할 수 없다.

## Action

1. 서버가 canonical document와 ACL을 다시 확인하고 anchor를 resolve한다. Wiki local revision은 submit·confirm·`verify_claim`·`verify_document`마다 exact source ACL과 canonical ref/digest를 재검사한다. 원본 `boi:*`는 덮어쓰지 않고 server-derived `boi:submitted:*` lineage로만 전환한다.
2. 등록 alias를 결정론적으로 탐지하고 exact `binding_id`, `concept_id`, `surface_term`, start/end, binding digest를 반환한다. 이 단계는 verdict를 만들지 않는다.
3. User·Codex·Claude·Qwen 후보를 closed schema로 검사하고 ontology refs, subject/relation/object 역할, 조건, alias, non-overlapping complete span을 pinned binding과 대조한다. client가 보낸 verdict·Evidence·Rule 필드는 거부한다.
4. 결과에 영향 없는 용어 차이는 기록만 하고, 결과가 달라질 모호성만 사용자에게 확인한다. 수동 교정은 기존 record를 고치지 않고 `supersedes_claim_id`를 가진 새 제출로 저장한다.
5. user confirmation event로 새 immutable interpretation version을 만든다.
6. exact active Release와 `OperationalVerification`으로 Claim을 판정한다.
7. Rule이 허용한 Knowledge statement와 decisive Evidence만으로 충분한 과학적 설명을 구성한다.
8. 교정 카드 바로 아래에 결정 근거 1~2개를 항상 보이고, 펼쳐보기에서 `original_text`, `reviewed_translation`, `locator`, `original_url`, ontology_refs를 제공한다.
9. 같은 stored report에서 Markdown/PDF를 만들고 동일 digest를 반환한다.

## State

Interpretation, external Claim submission, correction resubmission, confirmation event, Verdict Packet, Report, export는 append-only immutable record다. Wiki revision의 canonical source lineage도 이 record에 저장되고 재시작 뒤 보존된다. 동일 actor·request digest·idempotency key의 재시도는 같은 bytes를 반환한다. 새 Release가 활성화되거나 이전 Release가 withdraw되어도 과거 `report_digest`와 component digests는 변하지 않는다. raw pasted document는 최초 owner만 접근하는 semantics를 유지한다.

## Verification

- stale/duplicate/missing Unicode code point anchor를 fail closed하는지 확인한다.
- Wiki local revision의 source ACL이 submit, confirm, `verify_claim`, `verify_document`에서 다시 확인되는지, canonical lineage가 재시작 후에도 남는지 확인한다.
- lineage field가 모두 제거되었거나 ref/digest가 위조·malformed된 Wiki revision이 confirmation·verification으로 진행되지 않고 fail closed하는지 확인한다.
- ontology mismatch, partial relation span, LLM `changes_outcome=false`가 user confirmation을 우회하지 못하는지 확인한다.
- 존재하지 않는 ontology_ref, 문서에 없는 alias, 겹치거나 불완전한 role span이 confirmation과 verdict로 진행되지 않는지 확인한다.
- unconfirmed agent condition/process_stage/material_state가 verdict나 report applicability fact가 되지 않는지 확인한다.
- User·Codex·Claude·Qwen과 MCP가 같은 canonical Claim을 제출하면 client label과 무관하게 같은 Claim ID와 결정론적 verdict가 나오는지 확인한다.
- caller-authored verdict·Evidence·Rule이 REST/MCP closed schema에서 거부되는지 확인한다.
- inactive Release가 verdict에 사용되지 않고, 근거 없는 빨간 표시가 생성되지 않는지 확인한다.
- red annotation은 `VIOLATION`에만, purple ambiguity는 outcome-changing proposal에만 나타나는지 확인한다.
- 각 explanation sentence가 Knowledge digest, Evidence digest, Source digest, `original_text_hash`에 묶이는지 확인한다.
- 일반 User가 허용된 원문·번역·locator·URL을 볼 수 있고 source ACL denial은 우회되지 않는지 확인한다.
- Web, REST, MCP, Markdown, PDF가 claim ID, verdict, Evidence ID, Release ID, `report_digest`에서 완전히 같은지 확인한다.
- 과학적 설명이 충분하되 Rule/Evidence 범위를 넘는 권고나 종합 점수를 만들지 않는지 확인한다.
- restart, retry, concurrent same-key request에서도 같은 report bytes와 audit count를 유지하는지 확인한다.
- 구현 증거가 tracked pytest suite identity(수량·testcase identity digest, 실제 실행 1건 이상), 정확히 21 named browser checks와 capture hashes, Candidate qualification, exact-commit independent review를 함께 묶는지 확인한다. 이는 implementation evidence의 `FINAL / VERIFIED` 조건일 뿐 activation 증명이 아니다.

## Failure Artifacts

sanitized model ID, prompt version, document/Claim/Release/report digest, anchor context, expected/actual verdict, component digest, channel diff, ACL decision, reason code만 기록한다. endpoint, API key, user secret, chain-of-thought는 기록하지 않는다.

## Release-Blocking Conditions

- 미확인 또는 ontology 불일치 Claim이 verdict로 진입
- missed violation, false-red, wrong interpretation, broken Evidence, ungrounded explanation
- 일반 User가 원문 근거를 확인할 수 없음 또는 ACL 우회
- Web/REST/MCP/Markdown/PDF parity 불일치
- idempotency/restart 후 report bytes 변경
- Admin review 부재, self-approval, inactive component 사용

## Candidate와 activation gate 분리

`release_candidate`는 inactive다. G0–G4 자동 Candidate qualification은 통과할 수 있지만, G5 독립 sealed holdout, G6 active stored-report Web/REST/MCP/Markdown/PDF parity, G7 사람 Science Admin의 원문 review·activation audit는 자체 증거가 생길 때까지 `PENDING`이다. Qwen live availability, tuning, context size 또는 성공 응답은 이 gate 어느 것도 통과시키거나 실패시키지 않는다.

| Gate | 이 하네스의 통과 조건 |
|---|---|
| G0 | packet/profile/anchor schema와 identity가 유효하다. |
| G1 | 원문 Evidence와 ACL 경로가 검증된다. |
| G2 | 해석된 Knowledge와 ontology refs가 추적된다. |
| G3 | exact Release의 deterministic verdict만 사용한다. |
| G4 | 공개 cases에서 missed violation/false-red가 없다. |
| G5 | 독립 holdout에서 해석·범위·판정 실패가 없다. |
| G6 | 활성 Release의 stored report가 Web/REST/MCP/Markdown/PDF/export/restart/security parity를 통과한다. |
| G7 | 별도 사람 Science Admin review와 activation audit 후 immutable Release만 활성화된다. |
