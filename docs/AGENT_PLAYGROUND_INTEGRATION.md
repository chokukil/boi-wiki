# Agent Playground · Agent Hub · BoI Wiki 연계

`/agents/builder`는 `/playground`로 이동한다. Agent Playground는 SSO 사용자가 개인
Langflow 공간을 준비하고 Flow를 시험한 뒤, Agent Hub 배포 결과의 exact Flow를 BoI
Action으로 연결하는 개발·검증 workbench다. Agent Hub는 배포 Control Plane이며 Action
실행 경로에는 들어가지 않는다.

## mainline 기준과 책임

이 구현은 `origin/main@53912644c443b0a2af0e5c367901575a111b18ae`에서 독립적으로
구성했다. main의 `AuthIdentity(employee_id, display_name, email, roles, teams,
auth_source)`를 그대로 사용하며 semantic Agent v2에 의존하지 않는다.

| 구간 | 책임 | 자격증명 |
| --- | --- | --- |
| Agent Playground | endpoint, onboarding, Flow 검증, deployment·Action 연결 | 현재 `AuthIdentity` |
| Langflow 1.11 | 사번별 project와 Flow 실행 | 사용자별 Langflow API Key |
| Agent Hub | 승인 자산과 endpoint/project를 이용한 배포 | 사용자별 Langflow API Key |
| BoI Wiki 직접 연결 | Wiki·Ontology 조회와 개인 초안 | `BOI_WIKI_PAT` |
| BoI Action | connector-neutral 실행과 caller ACL | 1회성 `boi_run_*` token |

Langflow 연결 키와 BoI PAT는 다른 키다. 사용자는 Langflow 표준 설정 화면에서 API Key를
발급해 Playground와 Agent Hub에 각각 한 번 입력한다. BoI PAT는 Playground가 Langflow
Credential API에 `BOI_WIKI_PAT`로 등록하며 Agent Hub에는 주지 않는다.

## 변경하지 않는 외부 제품

Langflow와 Agent Hub 소스는 수정하지 않는다.

- Langflow:
  `langflowai/langflow:1.11.0@sha256:f7de8256fdbba725d7765bcff9d984ad272e0f726daabf2d7e3c3b0fa8dc31bf`
- 공개 `/health`, `/api/v1/version`, `/api/v1/users/whoami`, project/Flow/variable,
  `/api/v1/run/{flow_id}`만 사용
- BoI component는 `LANGFLOW_COMPONENTS_PATH`의 read-only mount로 제공
- Agent Hub: PR #25 SHA `7ca556b7885f316eedd757a7190b748bb7e0f7e5`, git diff 없음

버전 변경 시 BoI adapter와 bundle을 회귀 검증한다. Langflow package monkey patch,
core component override, 내부 DB 접근으로 호환시키지 않는다.

## URL 계약

브라우저 표시 주소와 Agent Hub 배포 API 주소는 분리한다.

| 용도 | 설정 | 예시 |
| --- | --- | --- |
| BoI | `BOI_EXTERNAL_URL` | `http://wiki.skhynix.com` |
| Langflow 브라우저 | `LANGFLOW_EXTERNAL_URL` | `http://wiki.skhynix.com/builder` |
| Agent Hub endpoint | `LANGFLOW_DEPLOY_URL` | host root에서 `/api/v1`이 열리는 주소 |

PR #25는 endpoint path를 제거하므로 `/builder` 표시 주소를 그대로 등록하지 않는다.
Caddy·DNS는 사내 배포에서 이 계약을 만족해야 하지만 이 브랜치가 구성하지 않는다.

로컬 격리 검증 주소는 다음과 같다.

| 서비스 | 주소 |
| --- | --- |
| BoI SSO | `http://localhost:28005` |
| Action Gateway | `http://localhost:18105` |
| Wiki MCP | `http://localhost:18205/mcp/v2` |
| Langflow 1.11 | `http://localhost:7867` |
| Agent Hub | `http://localhost:18080/AgentHub.html` |
| Agent Hub API | `http://localhost:18001` |
| Keycloak / Mock HCP | `http://localhost:18082` / `http://localhost:18083` |
| LM Studio | `http://localhost:1236` |

기존 main `:28000`과 Langflow `:7860`은 변경하지 않는다.

## 온보딩

`100001/100002/100003` dev fixture는 SSO와 같은 사번·역할 계약을 모사한다. SSO 모드의
소유자는 query/form/header가 아니라 `empno` claim과 HCP 역할로 만든 `AuthIdentity`다.
HCP 실패는 fail-closed하며 다른 사번 전달은 403이다.

신규 `100002`의 실제 흐름:

1. OIDC authorization-code + PKCE S256으로 `/playground`에 로그인한다.
2. `Langflow 설정 열기`에서 표준 API Key를 발급한다.
3. Playground에 endpoint와 key를 한 번 입력한다.
4. 연결 시험이 1.11 지원 범위와 현재 사번 소유자를 확인한다.
5. bootstrap이 `boi-100002`, 무기한 PAT, `BOI_WIKI_PAT`, 기준 Flow를 멱등 준비한다.
6. preview smoke가 성공하면 네 단계 workbench를 연다.

```text
Langflow에서 만들기 → Playground 테스트 → Agent Hub 배포 → Action 연결
```

invalid key, 타 사용자 key, 지원하지 않는 버전은 각각 차단한다. 중간 실패 후 다시
bootstrap해도 project, Credential, 기준 Flow, PAT를 중복 생성하지 않는다. endpoint별
onboarding 상태는 독립적이다.

사용자 가이드는 실제 Wiki에 포함한다.

- `/docs/boi:public:boi-wiki-manual:langflow:agent-playground-onboarding`
- `/docs/boi:public:boi-wiki-manual:operations:agent-playground-operator-runbook`

## Credential과 MCP

endpoint API Key는 AES-GCM으로 암호화한다. 응답에는 `has_api_key`와 fingerprint만
표시한다. PAT와 run token은
`BOI_RUNTIME_ROOT/agent-playground/credentials.sqlite3`에 저장한다.

- PAT: 원문 미저장, 만료 없음 기본, scope·역할 snapshot, 폐기·회전
- run token: caller·Action·deployment·endpoint·project·Flow·trace·execution ID·
  capability·scope·TTL 귀속, 정상 실행 동안 여러 Wiki 호출 허용 후 종료 시 소비

독립 `/api/v2/tokens`는 POST/GET/DELETE를 제공한다. `/mcp/v2` facade는 다음 네 도구만
노출한다.

- `boi_search` (호환용 내부 이름, Task Context·Ontology-first hybrid retrieval)
- `boi_get`
- `boi_plan(capability_id=knowledge.draft)`
- `boi_confirm`

MCP는 bearer와 exact audience를 내부 BoI API로 전달하며 `employee_id`를 받지 않는다.
내부 Wiki adapter는 main의 실제 `work_context_pack`, `ontology_search_payload`, typed
workflow·responsibility·lineage·impact 관계와 `write_boi`를 사용한다. 공개 UX에는
`boi_search`를 별도 단순 검색 기능으로 노출하지 않는다. graph가 없을 때만 ACL 내 문서를
fallback으로 사용한다. preview는 변경하지 않고 `private_draft`만 caller 개인 Wiki에 저장한다.

## 기준 Flow와 실제 모델

기준 Flow:

```text
Chat Input
→ BoIWikiKnowledge
→ agent_slot
→ BoIWikiSave
→ Chat Output
```

- `BoI Wiki Agent Loop`, endpoint `boi-wiki-agent-loop`, version `1.1.0`
- 기본 저장 mode `preview`
- generator 출력이 source of truth이며 JSON drift와 checksum을 검사

실제 model 예제는 `BoI Wiki Agent Loop – Model Agent Example`이다. OpenAI-compatible
LM Studio `:1236`의 `google/gemma-4-26b-a4b-qat`를 사용했다. 모델 주소·이름·credential은
Langflow 표준 variable/credential로 주입하며 Flow JSON과 bundle에는 비밀값을 넣지 않는다.
실제 response ID와 latency가 있는 추론만 runtime validation으로 인정한다.

## 다른 작성자의 Agent Hub 자산 채택

자산 제작자와 Playground 사용자가 같을 필요는 없다.

1. Agent Hub의 승인 Flow 또는 `.py` component를 선택한다.
2. 사용자의 endpoint/API Key와 `boi-{employee_id}` project로 배포한다.
3. Playground가 같은 endpoint/project의 public API에서 exact Flow ID를 다시 찾는다.
4. component가 미연결 노드인지 확인한다. `boi.agent-slot.v1`에 정확히 맞을 때만 공개
   Flow PATCH API로 `agent_slot`을 교체하고, 이전 graph snapshot을 보관한다.
5. source author, live checksum, component 실행 provenance, runtime, Wiki/Ontology 근거를 검증한다.
6. `action_ready`인 exact Flow만 Action draft로 연결한다.

component 배포, graph 연결, runtime 실행은 서로 다른 상태다. 미연결 component나 실행
provenance가 없는 component는 `action_ready`가 될 수 없다.

## connector-neutral Action

Action은 업무 계약과 실행 연결을 분리한다.

- `action_contract`: 업무 목적, 입력·출력, 근거, 위험·승인 정책
- `connector_binding`: API, MCP, Webhook, Manual, Event Broker, BoI Writer, Langflow

Playground가 만든 draft만 선택한 exact Flow에 대한 Langflow binding을 사용한다.
새 draft는 `execution_mode=gateway`, `boi.action-contract.v1`,
`boi.connector-binding.v1`, endpoint/deployment/project/Flow/version/checksum을
저장한다. 레거시 flat `execution_kind`는 읽기 호환만 유지한다.

Action Gateway는 endpoint owner의 암호화된 Langflow API Key로 `/api/v1/run/{flow_id}`를
호출한다. Wiki 조회·저장은 caller에 묶인 짧은 run token으로 수행하므로 공유 Action에서도
배포자 권한으로 상승하지 않는다. Action은 기본 private이며, team scope는 등록자와 호출자의
HCP team membership을 매 실행마다 확인한다. 팀 endpoint는 이번 범위에 없다.

## 현재 감사 상태

`d85c44a6`에서 만든 기존 완료 감사와 handoff는 `superseded / not ready`다. HCP 즉시
축소, run-token audience 오용, 실제 Task 복원, typed Ontology, component 실행 경로,
live checksum drift, 다른 팀 호출자의 개인 초안 소유권을 포함한 새 Playwright E2E가
모두 통과한 뒤에만 새 완료 증거를 기록한다.

## 회귀와 handoff

```bash
python scripts/check_agent_playground_mainline_boundary.py
python scripts/check_agent_playground_langflow_boundary.py
python -m pytest -q
```

최종 handoff는
`artifacts/agent-playground-handoff/<run_id>-mainline-final-audit/`에 생성한다.
`regression/mainline-completion-audit.json`, source state, secret scan, `SHA256SUMS`,
single-commit `CHERRY_PICK_ORDER.md`가 함께 있어야 한다. 적용 대상은 이 mainline
커밋뿐이며 이전 Playground 브랜치나 `9fee2118`은 비교 자료로만 남긴다.
