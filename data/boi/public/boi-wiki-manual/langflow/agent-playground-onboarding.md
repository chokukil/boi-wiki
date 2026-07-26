---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Playground 시작 가이드
description: Langflow 연결 키 발급부터 Agent Hub 배포와 BoI Action 연결까지 처음 한 번 준비하는 방법
tags: [Manual, AgentPlayground, Langflow, AgentHub, Action]
timestamp: 2026-07-26T07:30:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:agent-playground-onboarding
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: boi_api/app/templates/agent_playground.html
  - type: repo
    ref: langflow/compatibility-manifest.json
review:
  reviewer: platform-lead
  review_status: reviewed
---

# 무엇을 준비하는가

Agent Playground는 내 사번에 연결된 Langflow 프로젝트에서 Flow를 만들고 시험하는 개인 개발 공간이다. 충분히 검증한 Flow는 Agent Hub로 배포하고, 배포된 정확한 Flow를 BoI Action으로 연결한다.

Langflow와 Agent Hub는 BoI가 수정하지 않는다. Playground는 각 제품이 제공하는 API Key, Flow JSON, custom component, 공개 API만 사용한다.

# 두 키를 구분한다

| 구분 | 누가 만드는가 | 어디에 쓰는가 |
|---|---|---|
| Langflow 연결 키 | 사용자가 Langflow `설정 → API Keys`에서 발급 | Playground endpoint 연결, Agent Hub endpoint 등록 |
| BoI 지식 연결 | Playground가 자동 발급 | Langflow 안에서 Wiki·Ontology 조회와 개인 초안 저장 |

Langflow 연결 키는 저장 후 다시 보이지 않는다. BoI 지식 연결의 PAT도 화면, Flow JSON, Agent Hub에 노출되지 않는다.

# 처음 시작하기

## 1. 내 개발 공간 확인

`Agent Playground`를 열면 현재 SSO 사용자와 권한을 먼저 확인한다. 주소나 입력값에 포함된 사번은 소유권 기준으로 사용하지 않는다.

## 2. Langflow 연결 키 발급

1. `Langflow 설정에서 키 발급`을 누른다.
2. Langflow의 `API Keys` 화면에서 이름을 `BoI Agent Playground`로 입력한다.
3. 새 키를 발급하고, 표시되는 값을 한 번만 복사한다.
4. Playground로 돌아와 `방금 발급한 API Key`에 붙여 넣는다.
5. `연결 시험`에서 Langflow 1.11과 내 사번 사용자가 확인되는지 본다.
6. `확인하고 저장`을 누른다.

브라우저에서 여는 `/builder` 주소와 Agent Hub가 호출하는 host-root API 주소는 다를 수 있다. Playground에 미리 채워진 주소를 임의로 바꾸기 전에 운영자에게 확인한다.

## 3. BoI 지식 연결 자동 준비

`내 개발 공간 자동 준비`를 누르면 다음 항목이 순서대로 만들어진다.

- `boi-{사번}` 개인 프로젝트
- 만료 없는 개인 BoI PAT
- Langflow `BOI_WIKI_PAT` Credential Variable
- read-only 방식으로 설치된 BoI component bundle 확인
- `BoI Wiki Agent Loop` 기준 Flow
- Wiki를 변경하지 않는 preview smoke

중간에 실패해도 같은 버튼을 다시 누르면 실패한 단계부터 이어진다. 프로젝트, PAT, Flow를 매번 새로 만들지 않는다.

## 4. 첫 Flow 확인

preview가 통과하면 `Playground 시작`을 누른다. 이후 작업은 다음 네 단계로 진행한다.

`Langflow에서 만들기 → Playground 테스트 → Agent Hub 배포 → Action 연결`

# Agent Hub로 배포하기

1. Playground에서 Flow 자산을 내려받는다.
2. Agent Hub에서 Flow JSON 또는 component 자산을 업로드한다.
3. endpoint 별칭과 Langflow host-root URL을 입력한다.
4. 앞에서 발급한 Langflow 연결 키를 Agent Hub에도 한 번 입력한다.
5. 연결 시험 후 `boi-{사번}` 프로젝트를 선택한다.
6. Flow를 배포한다.
7. Playground로 돌아와 같은 endpoint와 project에서 `새 Flow 찾기`를 누른다.
8. 새 exact Flow ID를 선택하고 전체 검증을 실행한다.

BoI와 Agent Hub는 저장된 API Key를 서로 읽지 않는다. 같은 키를 양쪽에 한 번씩 입력하는 것이 정상 절차다.

## 다른 사람이 만든 Agent Hub 자산 사용하기

Agent Hub 자산의 제작자와 Action 사용자는 같을 필요가 없다. 다른 직원이나 팀이 만든 Flow·custom component도 Agent Hub에서 선택해 내 `boi-{사번}` 프로젝트로 배포할 수 있다.

1. Agent Hub에서 사용할 Flow 또는 component를 선택한다.
2. 배포 대상은 내가 Playground에 연결한 Langflow endpoint와 `boi-{사번}` 프로젝트로 지정한다.
3. component를 배포했다면 Langflow에서 그 component를 사용해 Flow를 구성한다.
4. Playground에서 `새 Flow 찾기`를 눌러 배포된 exact Flow를 연결한다.
5. Flow가 `BoIWikiKnowledge → 사용자 Agent·custom component 구성 → BoIWikiSave`의 입출력 계약을 유지하는지 검증한다.
6. build, 실제 실행, SOP Task Context, Wiki·Ontology 근거, 저장 격리 검증을 모두 통과한 Flow만 Action으로 연결한다.

중간의 Agent 영역은 `BoIAgentSlot`이나 예제 모델 하나로 제한하지 않는다. Agent Hub의 여러 custom component를 조합해도 된다. 다만 Wiki facade와 `boi_contract` 입출력, secret scan, 실제 runtime 결과는 유지해야 한다. 완성되지 않은 Flow는 `내 작업 중 Flow`로 남고 Action 연결 버튼이 열리지 않는다.

이미 팀 Langflow endpoint에 배포된 Flow를 그대로 공유 Action으로 사용하는 경우에는 개인 API Key를 전달하지 않는다. 해당 endpoint는 운영자가 팀 소유 연결로 한 번 등록하고 HCP 사용 권한을 부여해야 한다. 런타임은 팀 endpoint의 호출 key를 사용하되 Wiki 조회와 개인 초안은 Action을 실행한 사용자의 단기 run token으로 처리한다.

# Action으로 연결하기

Flow가 `action_ready`가 되면 `Action 연결`을 누른다.

BoI Action은 Langflow 전용 기능이 아니다. 업무 목적, 입력·출력, 근거, 위험도와 승인 정책은
connector-neutral Action 계약으로 저장된다. API, MCP, Webhook, Manual, Event Broker,
BoI Writer, Langflow 중 실행 방식만 connector binding으로 따로 붙는다. Playground에서
만든 초안은 현재 선택한 exact Flow를 실행해야 하므로 그 binding만 Langflow인 것이다.

1. Action 등록 초안을 연다.
2. Action 계약과 `실행 연결: Langflow`를 구분해 확인한다.
3. validate 결과를 확인한다.
4. publish-request를 명시적으로 요청한다.
5. 운영 승인 후 BoI Wiki의 일반 화면이나 SOP Task에서 Action을 사용한다.

Action 실행 시 Langflow 호출 권한은 endpoint 소유자의 연결을 사용하지만 Wiki 조회와 개인 초안 권한은 Action을 누른 사용자의 권한을 따른다.

# Wiki와 Ontology 활용

- 일반 질문은 문서 검색과 연결된 Ontology 관계를 함께 사용한다.
- SOP Task에서 실행하면 Task, SOP, Stage, Event, Action, 선행 결과, 필요 근거와 부족 근거가 함께 전달된다.
- SOP가 없는 업무에는 존재하지 않는 SOP 맥락을 만들지 않는다.
- Ontology provenance가 없으면 해당 관계를 사실 근거로 사용하지 않는다.
- graph 근거가 없으면 문서 근거로 대체하고 이를 결과에 표시한다.

저장 기본값은 `preview`다. `private_draft`를 직접 선택한 경우에만 내 개인 Wiki 초안이 만들어진다.

# 오류 복구

| 표시 | 확인할 내용 |
|---|---|
| API Key 오류 | Langflow에서 키를 다시 발급하고 endpoint의 Key만 교체한다. |
| 사용자 불일치 | 다른 사번이 발급한 키를 사용하지 않았는지 확인한다. |
| 버전 불일치 | Langflow가 지원 범위 `>=1.11.0,<1.12.0`인지 확인한다. |
| bundle 확인 실패 | 운영자에게 read-only custom component mount 상태를 요청한다. |
| preview 실패 | 표시된 단계의 오류를 확인하고 `자동 준비`를 다시 실행한다. |

# 공유하면 안 되는 값

- Langflow API Key 원문
- `BOI_WIKI_PAT`
- `boi_run_*` 실행 token
- 모델 API Key
- API Key가 포함된 네트워크 payload나 화면 캡처

키를 잘못 공유했다면 endpoint 수정에서 새 Langflow 키로 교체하고, `고급 연결 관리`에서 BoI 지식 연결도 회전한다.
