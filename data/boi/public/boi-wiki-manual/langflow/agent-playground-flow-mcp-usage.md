---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Playground Flow·MCP 활용 가이드
description: 개인 Flow 개발부터 MCP 연결, Agent Hub 배포와 BoI Action 실행까지 실제 화면으로 따라 하는 가이드
tags: [Manual, AgentPlayground, Langflow, MCP, AgentHub, Action, Ontology]
timestamp: 2026-07-28T18:30:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:agent-playground-flow-mcp-usage
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: boi_api/app/templates/agent_playground.html
  - type: repo
    ref: langflow/flows/boi_universal_simulation_mcp.json
  - type: boi
    ref: boi:public:boi-wiki-manual:operations:agent-hub-integration-boundary
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 전체 흐름

Agent Playground는 개인 개발 공간이다. 내 Langflow에서 Flow를 만들고 충분히
시험한 뒤, 수정하지 않은 Agent Hub UI를 통해 배포한다. Playground가 배포된 exact
Flow를 다시 찾고 검증하면 connector-neutral BoI Action으로 연결할 수 있다.

```text
회사 SSO
→ DEV · Playground Flow
→ Wiki·Ontology 근거로 테스트
→ Langflow MCP tool
→ Agent Hub 배포
→ PRD · Agent Hub exact Flow
→ BoI Action
→ 일반 Wiki 또는 SOP Task 실행
```

![사번 없는 Agent Playground와 개인 Flow 목록](/public/boi-wiki-manual/_media/browser/agent-playground-flow-mcp/01-playground-flow-list.png)

# 1. Langflow 연결 키를 준비한다

`Langflow 설정에서 키 발급`을 열면 같은 회사 SSO 세션으로 Langflow 설정 화면에
진입한다. Langflow 표준 기능으로 개인 API Key를 만들고 Playground에 한 번 입력한다.
입력 후에는 원문 대신 연결 상태와 fingerprint만 보인다.

![원문 키가 노출되지 않는 Langflow API Key 설정](/public/boi-wiki-manual/_media/browser/agent-playground-flow-mcp/02-langflow-api-key-settings.png)

키의 역할을 혼동하지 않는다.

| 구분 | 용도 |
| --- | --- |
| 회사 SSO | 사람이 BoI와 Langflow 화면을 열 때 사용 |
| Langflow API Key | Playground 연결과 Agent Hub 배포 |
| BoI PAT | Langflow 내부에서 Wiki·Ontology를 조회할 때 사용 |
| Action run token | 실제 Action 호출자의 Wiki 권한 |

BoI PAT와 run token은 Playground가 관리하며 사용자가 Agent Hub에 입력하지 않는다.

# 2. DEV Flow를 만들고 원본 Canvas를 확인한다

Flow 목록의 `DEV · Playground`는 개인 프로젝트에서 개발·시험 중인 Flow다. 행을
누르면 Playground에서 선택되고, `원본 열기`는 실제 Langflow Canvas를 새 탭으로
연다. Playground는 분기·병합·루프를 임의로 다시 그리지 않는다.

![Universal Simulation MCP 원본 Canvas](/public/boi-wiki-manual/_media/browser/agent-playground-flow-mcp/03-langflow-universal-simulation-canvas.png)

`BoI Universal Simulation MCP`는 다음 계약을 보여주는 시작 Flow다.

```text
업무 요청
→ Wiki·Ontology 업무 맥락
→ Gemma 시뮬레이션
→ Wiki 자산화 후보
→ 결과 확인
```

SOP Task에서는 Task·Workflow·Stage·Event·Action·책임·선행 결과를 복원한다.
SOP가 없는 질문에는 존재하지 않는 SOP 맥락을 만들지 않는다.

# 3. MCP tool로 사용한다

대표 Flow를 선택하고 `MCP 도구 준비`를 누른 뒤 `실제 MCP 호출`을 실행한다.
`list_tools`에서 `boi_universal_simulate`가 보이고 실제 tool call이 성공해야 한다.

![MCP tool 준비와 실제 호출 결과](/public/boi-wiki-manual/_media/browser/agent-playground-flow-mcp/04-mcp-tool-result.png)

외부 MCP client에는 표시된 streamable HTTP URL과 개인 Langflow API Key를 등록한다.

```json
{
  "transport": "streamable_http",
  "url": "http://<langflow-deploy-host>/api/v1/mcp/project/<project-id>/streamable",
  "headers": {
    "x-api-key": "${LANGFLOW_API_KEY}"
  }
}
```

실제 키를 설정 예시나 Wiki에 붙여 넣지 않는다. 외부 MCP 호출은 조회와
`preview`만 수행한다. `private_draft`는 BoI Action이 호출자별 run token을 전달한
경우에만 허용된다.

# 4. Agent Hub에서 배포한다

Playground의 `Agent Hub 배포` 단계에서 secret-free Flow JSON과 manifest를
준비한다. Agent Hub UI에서 사용자가 직접 다음 값을 입력하거나 선택한다.

1. Langflow deploy endpoint
2. 개인 Langflow API Key
3. `boi-{employee_id}` 프로젝트
4. 배포할 Flow 또는 Component

![수정 없는 Agent Hub의 자산과 배포 화면](/public/boi-wiki-manual/_media/browser/agent-playground-flow-mcp/05-agent-hub-deployment.png)

BoI는 Agent Hub DB나 저장된 Key를 읽지 않으며 배포를 대신 실행하지 않는다.
[Agent Hub 비수정 연동 경계](/docs/boi:public:boi-wiki-manual:operations:agent-hub-integration-boundary)를
함께 확인한다.

# 5. PRD exact Flow를 다시 찾는다

Agent Hub 배포 후 Playground에서 같은 endpoint와 project를 새로고침한다. 배포
전후 Flow 목록을 비교해 exact Flow ID와 checksum이 일치해야
`PRD · Agent Hub`로 표시된다.

![PRD exact Flow 재발견과 검증 상태](/public/boi-wiki-manual/_media/browser/agent-playground-flow-mcp/06-prd-flow-validation.png)

PRD는 배포 출처를 뜻한다. runtime, Task, Ontology 검증이 끝나지 않았거나 checksum
drift가 있으면 Action 연결은 계속 차단된다.

다른 직원이 만든 승인 Component는 `boi.agent-slot.v1` 계약이 맞을 때만 Agent
자리에 자동 연결한다. 실행 경로와 provenance에 Component ID가 남지 않으면
배포되었더라도 검증 완료로 보지 않는다.

# 6. Action으로 연결해 Wiki에서 실행한다

검증된 exact Flow에서 Action 등록 초안을 만들고 기존 validate와 publish-request
절차를 따른다. Action 계약은 API·MCP·Webhook·Manual·Event Broker·BoI Writer와
같은 connector-neutral 구조를 유지하며, 이 Flow의 binding만 Langflow다.

![BoI Action의 Wiki·Ontology 근거와 실행 결과](/public/boi-wiki-manual/_media/browser/agent-playground-flow-mcp/07-action-wiki-result.png)

- `preview`: Wiki를 변경하지 않는다.
- `private_draft`: 실제 Action 호출자의 개인 Wiki에만 저장한다.
- 팀 Action: endpoint 소유자의 Langflow Key로 실행하되 Wiki ACL은 호출자를 따른다.
- Flow checksum이 바뀌면 재검증 전까지 실행을 차단한다.

# 문제가 생겼다면

- 원본 Canvas에서 다시 로그인 화면이 나오면 browser SSO callback과 Caddy routing을 확인한다.
- Playground 주소에 `employee_id`가 있으면 이전 dev 링크다. `/playground`로 다시 접속한다.
- MCP tool이 보이지 않으면 Flow의 MCP 활성화와 project streamable URL을 확인한다.
- Agent Hub 배포 결과가 보이지 않으면 같은 endpoint와 project인지 확인한다.
- Component가 `연결 필요`라면 포트와 `boi.agent-slot.v1` 계약을 확인한다.

[Agent Playground 문제 해결](/docs/boi:public:boi-wiki-manual:langflow:agent-playground-troubleshooting)과
[Caddy SSO 적용 프롬프트](/docs/boi:public:boi-wiki-manual:operations:agent-playground-caddy-sso-routing)를
참고한다.
