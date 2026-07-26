# Agent Playground 최종 완료 감사 기준

기준 브랜치: `codex/agent-playground-mainline`

기준 main: `origin/main@53912644c443b0a2af0e5c367901575a111b18ae`

Agent Hub 기준: `7ca556b7885f316eedd757a7190b748bb7e0f7e5`

이 문서는 파일 존재나 수동 체크 표시로 완료를 선언하지 않는다. 최종 인수
패키지의 `regression/mainline-completion-audit.json`이 모든 의미 검증을 통과해
`ok=true`일 때만 사내 적용 준비가 끝난 것으로 본다. 과거 `d85c44a6` 기반
45/45 패키지는 `superseded / not ready`이며 적용 근거로 사용하지 않는다.

## 완성 목표

```text
SSO Principal
→ 개인 Langflow endpoint/project
→ 내 Flow 또는 Agent Hub 승인 공유 자산
→ 수정 없는 Agent Hub UI 배포
→ exact Flow ID·live checksum 재발견
→ runtime·SOP Task·Ontology 검증
→ connector-neutral Action draft·validate·publish-request
→ 일반 Wiki·SOP Task 실행
→ source·Ontology provenance·호출자 개인 초안
```

사용자는 내부 endpoint ID, checksum, PAT, run token을 알지 않아도
`만들기 → 테스트 → Agent Hub → Action 연결`의 현재 단계와 다음 행동 하나만
따라갈 수 있어야 한다.

## 변경 불가 경계

- Agent Hub checkout의 HEAD가 지정 SHA와 같고 시작·종료 시 working tree가
  clean이어야 한다.
- Agent Hub frontend, backend, API route, DB schema와 migration을 수정하지 않는다.
- BoI는 Agent Hub의 승인 catalog `GET`만 사용한다. 배포는 기존 Agent Hub UI에서
  사용자가 직접 수행한다.
- Langflow는 공식 1.11 image, 공개 `/api/v1`, Flow JSON, Credential Variable,
  read-only custom-component bundle만 사용한다.
- BoI가 Agent Hub DB나 Langflow DB를 읽거나 API Key를 동기화하지 않는다.
- 대표 Flow 선정과 대표 모달 노출은 Agent Hub 담당자의 구두 후속 작업이다.

경계는 다음 두 정적 검사와 handoff의 `source-state.json`으로 확인한다.

```bash
python scripts/check_agent_playground_mainline_boundary.py
python scripts/check_agent_playground_langflow_boundary.py
```

## 실제 사용자 여정 증거

최종 handoff의 `browser/`에는 다음 실행 결과와 스크린샷이 모두 있어야 한다.

| 증거 | 의미 assertion |
| --- | --- |
| `fresh-onboarding` | endpoint 0개에서 OIDC 로그인, Langflow 표준 Key, 멱등 bootstrap, 기준 Flow smoke |
| `negative-recovery` | 잘못된 Key, 타 사용자 Key, 지원 밖 버전 차단과 부분 실패 재개·중복 없음 |
| `canonical-exact-e2e` | 내 Flow를 Agent Hub UI로 배포하고 exact ID/checksum을 재발견해 Action으로 실행 |
| `cross-author-adoption` | 다른 직원이 만든 승인 Flow·Component를 내 프로젝트에 배포·조합 |
| `component-composition-drift` | 미연결·비호환 Component 차단, 실행 provenance, checksum drift 차단·복구 |
| `model-agent-exact-e2e` | LM Studio Gemma 실제 추론과 source·Ontology·Task Context 보존 |
| `team-action-sharing` | endpoint owner와 호출자를 분리하고 호출자 개인 초안·`100003` 거부 |
| `action-abstraction` | API, MCP, Webhook, Manual, Event Broker, BoI Writer, Langflow 실제 Gateway 호출 |
| `security-context-hardening` | HCP 즉시 재확인, run-token audience 격리, 1회 소비 |
| `staged-workbench` | desktop·390px에서 단계형 Workbench와 primary action 하나 |
| `wiki-onboarding-docs` | 사용자 문서 6개와 운영 문서 2개의 실제 OIDC HTTP 접근 |

예상하지 못한 HTTP, page, console 오류는 0건이어야 한다. 순정 Agent Hub의
인증 bootstrap 중 발생하는 선택적 component lookup 오류처럼 소스 수정 없이
피할 수 없는 항목은 별도 `ignored_*` 근거와 범위를 명시하고 사용자 여정 실패로
이어지지 않았음을 증명해야 한다.

## 지식·권한·Action 의미 검증

- `BoIWikiKnowledge`는 사용자에게 `boi_search`를 노출하지 않고
  Task/Wiki Context → typed Ontology → 연결 문서 → 문서 fallback 순으로 동작한다.
- SOP Task는 실제 Task anchor에서 Workflow, Stage, Event, Action, 책임,
  선행 결과, 필요·부족 근거를 복원한다. 일반 질문에 허위 SOP를 만들지 않는다.
- Ontology edge는 provenance를 가지며 graph 부재는
  `grounded_document_fallback`으로 표시한다.
- 호환 Component는 `boi.agent-slot.v1`일 때만 공개 Flow PATCH API로 연결한다.
  실행 경로와 runtime provenance에 component asset ID가 없으면 Action을 차단한다.
- Action은 `action_contract`와 교체 가능한 `connector_binding`으로 나뉜다.
  Playground Flow만 Langflow binding을 사용한다.
- Action 등록·operator 적용·실행 직전에 live checksum을 다시 비교하고 drift면
  `409`로 차단한다.
- endpoint owner의 Langflow Key는 서버 호출에만 쓰고 Wiki ACL과 private draft
  owner는 실제 Action 호출자로 결정한다.
- PAT·run token은 HCP 권한을 즉시 다시 확인한다. run token은 caller, Action,
  deployment, endpoint/project, exact Flow, trace, execution, scope와 TTL에 묶는다.

## Wiki 산출물

사용자 가이드:

- `Agent Playground 시작 가이드`
- `Langflow 처음 연결하기`
- `내 Flow를 Agent Hub에 배포하기`
- `Agent Hub 공유 자산 활용하기`
- `Action으로 연결하고 Wiki에서 실행하기`
- `Agent Playground 문제 해결`

운영 가이드:

- `Agent Playground 운영 가이드`
- `Agent Hub 연동 경계와 운영 책임`

Playground 도움말과 오류 상태는 관련 문서로 직접 연결해야 한다. 운영 문서는
Agent Hub·Langflow 비수정 원칙, URL 계약, SSO/HCP, 공식 image와 read-only
bundle, migration·rollback, Action 승인과 drift 검증을 포함한다.

## 로컬 검증 주소

- Playground: `http://localhost:28005/playground`
- Agent Hub: `http://localhost:18080/AgentHub.html`
- Keycloak: `http://localhost:18082`
- Langflow: `http://localhost:7867`

브라우저 redirect와 HTML에는 `host.docker.internal`을 노출하지 않는다. 검증
compose의 loopback sidecar는 외부 제품 소스를 고치지 않고도 위 localhost 계약을
각 컨테이너 namespace에서 유지하기 위한 검증 wrapper다.

## 최종 판정

최종 커밋으로 서비스를 다시 빌드한 뒤에 생성한 증거만
`artifacts/agent-playground-handoff/<run_id>/`에 넣는다. 패키지에는 Flow JSON,
read-only bundle, compatibility manifest, Wiki 문서, 브라우저 증거, 전체 pytest,
Langflow 1.10 import·DB migration·Credential 복호화·rollback, secret scan,
`SHA256SUMS`, `source-state.json`, `CHERRY_PICK_ORDER.md`가 포함되어야 한다.

```bash
python scripts/audit_agent_playground_mainline_completion.py \
  --handoff-root artifacts/agent-playground-handoff/<run_id> \
  --live \
  --verify-checksums
```

이 명령의 `ok=true`와 Agent Hub clean 상태가 최종 완료 판정이다.
