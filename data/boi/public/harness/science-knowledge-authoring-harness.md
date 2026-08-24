---
okf_version: "0.1"
boi_profile_version: "0.1"
sci_profile_version: "0.1"
type: boi/harness
title: Science Knowledge Authoring Harness
description: Evidence 범위를 보존한 atomic Science Knowledge 작성 기준
tags: [BoIWiki, ScienceVerifier, Harness]
timestamp: 2026-08-25T16:00:00+09:00
boi_id: boi:public:harness:science-knowledge-authoring-harness
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
    ref: harness/science-knowledge-authoring-harness.md
  - type: repo
    ref: data/okf/profiles/sci-profile.yaml
review:
  review_status: pending_review
  required_role: Admin
  authorized_review_events: []
---
# Science Knowledge Authoring Harness

## Purpose

Dictionary와 원본 Evidence 사이에 검토 가능한 과학 지식 단위를 제안한다. Knowledge는 답변 prose가 아니라 조건·한계가 붙은 atomic statement이며, AI가 판정을 만드는 우회 통로가 아니다.

## Inputs

- Dictionary concept와 interpretation-only Ontology binding
- approved 가능한 Source/Evidence span과 exact claim scope
- 지식 수준(invariant, law, mechanism, model, qualified_rule, observation)
- domain, definitions, assumptions, applicability, limitations, invalid_outside
- 제안자 identity와 별도의 `science.admin` reviewer

## Observation

용어가 가리키는 개념·stage·state·quantity kind를 먼저 분리한다. Dictionary는 용어 입구, Ontology(온톨로지)는 해석과 탐색 후보, Evidence는 원문 근거다. Ontology에는 결과 방향이나 verdict를 넣지 않는다. 결과 방향은 조건이 완결된 Rule에서만 결정한다.

## Context

Knowledge 하나는 하나의 `atomic statement`만 가진다. `definitions`, `assumptions`, `applicability`, `limitations`, `invalid_outside`를 독립 필드로 둔다. 각 `EvidenceUse`는 Evidence의 `claim_family`와 `purpose`를 그대로 보존하고, 사용하지 못한 초록·범위 밖 자료는 `excluded_evidence_refs`와 exclusion reason으로 명시한다.

수학적 귀결, 물리 법칙, derived model, empirical correlation, vendor rule, internal qualified rule을 섞지 않는다. maturity에는 review state와 provenance만 두며 수치 confidence score를 만들지 않는다.

## Control

- agent 산출물은 제안이며 `draft/pending_review/release-blocked`다.
- `science.admin`이 지식 statement·수식·EvidenceUse를 승인한다.
- Power User는 지정 domain의 alias·용어·해석·concept link 제안만 Release Candidate에 포함할 수 있다.
- proposer/reviewer self-approval을 금지한다.
- 변경·승인·withdraw에는 exact digest와 `user_confirmed: true`가 필요하다.
- AI 요약은 Evidence에 없는 claim, 인과, 방향, 보편성을 추가할 수 없다.

## Action

1. 문장을 독립적으로 반증 가능한 최소 atomic statement로 쪼갠다.
2. Dictionary/Ontology concept를 연결하되 must-not-collapse 차이를 유지한다.
3. 지식 수준과 epistemic status를 선택한다.
4. definitions·assumptions·applicability·limitations·invalid_outside를 작성한다.
5. EvidenceUse마다 allowed claim family와 exact purpose를 복사한다.
6. inactive 또는 범위 부족 Evidence를 excluded list로 분리한다.
7. related Knowledge는 governed_by/explained_by/formalized_by/validated_by 의미만 쓴다.
8. 검증 후 별도 Admin review queue로 보내고 승인 전에는 전역 지식을 바꾸지 않는다.

## State

Knowledge draft는 제안자에게 수정 가능하지만 approved/active object는 immutable하다. 수정은 새 version으로 만들고 supersedes 관계와 이전 digest를 보존한다. alias feedback은 proposal로 축적하며 기존 Ontology를 즉시 바꾸지 않는다.

## Verification

- statement가 하나의 주장인지, 부정·조건·단위·stage·state가 명시됐는지 확인한다.
- 모든 EvidenceUse가 live Evidence의 claim scope와 exact match인지 검사한다.
- definitions-only Evidence로 contrast/causal/directional verdict를 만들지 않았는지 검사한다.
- assumptions 또는 invalid_outside를 지우면 더 넓은 주장이 되는지 adversarial review한다.
- Ontology 직렬화에 expected predicate, outcome direction, verdict가 없는지 확인한다.
- 지식 설명이 원문, 번역, locator, Source URL까지 추적되는지 확인한다.

## Failure Artifacts

Knowledge ID/version, atomicity failure, EvidenceUse scope diff, 누락된 condition, excluded Evidence, ontology-collapse 후보, actor와 object digest를 남긴다. LLM chain-of-thought나 비밀 설정은 저장하지 않는다.

## Release-Blocking Conditions

- 복수 과학 주장을 한 statement에 결합
- Evidence claim scope보다 넓은 statement 또는 설명
- assumption/applicability/invalid_outside 누락
- Ontology가 결과 방향이나 판정 규칙을 포함
- inactive Evidence를 결정 근거로 사용
- Admin 승인 부재 또는 self-approval

| Gate | 이 하네스의 통과 조건 |
|---|---|
| G0 | sci-profile과 Knowledge schema/ID가 유효하다. |
| G1 | Source/Evidence scope가 검토 가능하다. |
| G2 | atomic Knowledge와 조건·한계가 완결된다. |
| G3 | Rule이 Knowledge를 조건 그대로 사용한다. |
| G4 | qualification 설명이 Knowledge/Evidence로 추적된다. |
| G5 | holdout이 누락 조건과 과범위를 검출한다. |
| G6 | UI/API/MCP/export의 statement와 digest가 같다. |
| G7 | 별도 Admin 승인 version만 활성 Release에 들어간다. |
