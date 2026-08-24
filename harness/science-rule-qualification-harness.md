---
title: Science Rule Qualification Harness
type: boi/harness
status: draft
---

# Science Rule Qualification Harness

## Purpose

조건이 명시된 Knowledge를 deterministic Rule로 만들고 실제 과학 주장으로 자격 검증한다. AI는 Rule이나 expected verdict를 실행 시 생성하지 않으며 과학 판정은 closed evaluator만 수행한다. candidate RuleSet은 운영 권한이 아니다.

## Inputs

- approved 대상 Knowledge와 exact EvidenceUse
- closed rule kind, subject/object/relation, expected/contradiction predicate
- required/validity/empirical trigger conditions와 unit dimensions
- Rule마다 열 가지 공개 qualification case
- 제안자와 독립 reviewer, candidate Release identity

## Observation

Rule은 `evaluation_rule_id`, Knowledge/Evidence refs, required conditions, validity domain, equation/unit constraints를 선언한다. claim의 `source_span.exact`는 case label이 아니라 normalized subject·predicate·object·polarity·조건을 실제로 표현하는 실제 과학 주장이어야 한다.

## Context

Primary Verdict는 `VIOLATION`, `CONSISTENT`, `INSUFFICIENT_INFORMATION`, `OUTSIDE_VALIDITY_DOMAIN`, `EMPIRICAL_VERIFICATION_REQUIRED` 다섯 개뿐이다. `CONSISTENT`는 검사 범위 안에서 모순을 찾지 못했다는 뜻이며 참·안전·최적·승인이 아니다.

각 Matrix는 정확히 다음 열 가지 case kind를 가진다: `clear_violation`, `in_scope_consistency`, `missing_required_condition`, `outside_validity_domain`, `empirical_verification_required`, `negation`, `unit_variation`, `decision_changing_ambiguity`, `paraphrase`, `false_red_prevention`.

## Control

- Rule/Matrix/Pack은 agent draft이며 Admin 승인 전 release-blocked다.
- 법칙·수식·Rule·Evidence와 최종 Release 승인은 `science.admin`만 수행한다.
- proposer/reviewer self-approval을 금지한다.
- qualification 실행은 `QualificationRuleSet` candidate만 사용하며 `OperationalVerification`을 발급하지 않는다.
- 승인·qualification·Release mutation에는 exact digest와 `user_confirmed: true`가 필요하다.
- LLM/RAG/ontology는 verdict, evidence path, corrected claim을 만들 수 없다.
- Rule은 RPM 설정값, 변경 백분율, DOE 시작점, recipe recommendation을 반환하지 않는다.

## Action

1. 기존 closed evaluator로 표현 가능한 최소 Rule을 선택한다.
2. required·validity·empirical trigger·dimension 조건을 기계 판독 가능하게 기록한다.
3. EvidenceUse claim family/purpose를 exact match로 연결한다.
4. 자기 Rule을 겨냥하는 열 가지 자연어 claim을 먼저 작성한다.
5. `evaluation_rule_id == matrix.rule_id`를 고정하고 각 case가 자기 Rule의 다른 boundary를 실행하게 한다.
6. ambiguity 한 문장은 두 해석이 서로 다른 verdict가 됨을 증명한다.
7. paraphrase·negation·unit variation이 같은 의미/단위와 다른 극성을 실제 evaluator 입력으로 전달하는지 확인한다.
8. false-red는 unrelated subject로 NOT_APPLICABLE을 만드는 편법이 아니라 같은 claim family의 조건·범위·모델 차이로 red를 막는다.
9. public suite를 통과한 뒤 Rule을 freeze하고 별도 holdout reviewer에게 넘긴다.

## State

공개 case 수정은 Rule 변경과 같이 versioned candidate를 새로 만든다. Rule-freeze 이후 Rule bytes가 바뀌면 sealed holdout 결과를 폐기한다. active Rule은 수정하지 않고 새 Release로 supersede한다.

## Verification

- 각 case의 anchor text와 normalized claim이 의미상 일치하는지 검사한다.
- expected verdict가 evaluator 결과와 일치하고 decisive Evidence path가 exact인지 검사한다.
- empirical case가 다른 공통 Rule을 재사용하지 않고 자기 Rule의 empirical boundary를 실행하는지 확인한다.
- unit variation의 quantity가 target evaluator에 실제 소비되는지 검사한다.
- false-red와 missing/outside가 임의 concept mismatch로 만들어지지 않았는지 확인한다.
- application-independent cases가 다섯 verdict를 모두 보이고 Spin 전용 engine path가 없는지 확인한다.
- candidate를 Engine에 전달하거나 active resolver에 넣으면 반드시 거부되는지 확인한다.

## Failure Artifacts

case ID, 실제 claim text, normalized packet digest, target Rule/version, expected/actual verdict, reason codes, Evidence refs, candidate Release digest를 저장한다. aggregate score는 저장하지 않는다.

## Release-Blocking Conditions

- 합성 case label, anchor/normalized claim 불일치, paraphrase가 실제 같은 의미가 아님
- expected verdict를 얻기 위한 unrelated subject 또는 무시되는 fixture field
- Evidence scope overclaim, Rule-local empirical boundary 부재
- missed required violation, false red, broken ambiguity alternative
- candidate가 운영 capability로 변환됨
- 독립 holdout 부재, Admin 승인 부재, self-approval

| Gate | 이 하네스의 통과 조건 |
|---|---|
| G0 | Rule/Matrix/Pack schema와 digest가 유효하다. |
| G1 | decisive Evidence scope가 정확하다. |
| G2 | Knowledge 조건·한계가 Rule에 보존된다. |
| G3 | deterministic evaluator가 다섯 verdict 경계를 지킨다. |
| G4 | 열 가지 공개 case가 각 Rule을 실질적으로 검증한다. |
| G5 | freeze 후 독립 sealed holdout을 통과한다. |
| G6 | REST/MCP/report가 같은 Verdict Packet을 보인다. |
| G7 | 별도 Admin 승인과 exact Release만 운영 capability를 얻는다. |
