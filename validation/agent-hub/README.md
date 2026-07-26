# Immutable Agent Hub PR #25 validation

이 스택은 Agent Hub PR #25를 수정하지 않고 mainline Agent Playground, 공식
Langflow 1.11, Keycloak, Mock HCP와 실제로 연결한다. Agent Hub는 Flow·component
배포 Control Plane이며 BoI Action runtime에는 들어가지 않는다.

## 고정 기준

- Agent Hub checkout: `/home/chokukil/agent-hub-pr25-validation`
- commit: `7ca556b7885f316eedd757a7190b748bb7e0f7e5`
- Agent Hub 코드·DB·API 변경: 금지
- Agent Hub UI/API: `http://localhost:18080/AgentHub.html`, `http://localhost:18001`
- Keycloak / Mock HCP: `http://localhost:18082`, `http://localhost:18083`
- BoI SSO: `http://localhost:28005`
- Action Gateway / Wiki MCP: `http://localhost:18105`, `http://localhost:18205`
- Langflow 1.11: `http://localhost:7867`
- Agent Hub 등록 URL: `http://host.docker.internal:7867`
- LM Studio: `http://host.docker.internal:1236`

```bash
export AGENT_HUB_SOURCE_DIR=/home/chokukil/agent-hub-pr25-validation
docker compose -f validation/agent-hub/docker-compose.yml up -d --build
docker compose -f validation/agent-hub/docker-compose.yml exec backend \
  alembic upgrade head
```

검증 전후에 다음을 확인한다.

```bash
test "$(git -C "$AGENT_HUB_SOURCE_DIR" rev-parse HEAD)" = \
  7ca556b7885f316eedd757a7190b748bb7e0f7e5
git -C "$AGENT_HUB_SOURCE_DIR" diff --quiet
```

Keycloak 사용자는 고정 `sub`를 사용한다. 임시 비밀번호와 raw API Key는 실행 중에만
주입하고 저장소·스크린샷·handoff에 넣지 않는다.

## 실제 브라우저 runner

신규 사용자 온보딩:

```bash
BOI_URL='http://localhost:28005' \
LANGFLOW_URL='http://localhost:7867' \
BOI_SSO_PASSWORD='<temporary-keycloak-password>' \
LANGFLOW_PASSWORD='<langflow-user-password>' \
node validation/agent-playground/onboarding_e2e.mjs
```

Agent Hub → exact Flow → Action 전체 체인:

```bash
AGENT_HUB_PASSWORD='<temporary-keycloak-password>' \
LANGFLOW_API_KEY='<raw-user-api-key>' \
LANGFLOW_PASSWORD='<langflow-user-password>' \
AGENT_PLAYGROUND_URL='http://localhost:28005/playground' \
BOI_BASE_URL='http://localhost:28005' \
node validation/agent-hub/playwright_e2e.mjs
```

runner는 실제 화면에서 다음을 수행한다.

1. Agent Hub `100002` Keycloak 로그인
2. Flow JSON 업로드
3. 잘못된 API Key 연결 실패와 정상 key 복구
4. Langflow 1.11과 `boi-100002` 확인
5. Flow 실제 배포와 반환 exact Flow ID 확인
6. Langflow Canvas에서 Flow 존재 확인
7. BoI OIDC authorization-code + PKCE S256 로그인
8. `empno` 해석과 사번 spoof 403 확인
9. Playground live API 재발견
10. 구조·build·runtime·SOP·Ontology 검증
11. Action draft validate와 명시적 publish-request
12. exact reference validation-only operator fixture
13. 일반 질문, SOP Task, preview, private draft 실행
14. `100003` 실행 403과 logout 401
15. desktop/390px mobile overflow 및 unexpected error 0건 확인

API Key 입력 화면이나 secret-bearing payload는 캡처하지 않는다. 결과에는 Flow ID,
checksum, Action key, trace, source/Ontology 개수, draft reference 같은 비밀이 아닌
증거만 남긴다.

Codex Desktop 인앱 브라우저 bridge가 WSL workspace URI를 local file URI로 처리하지
못하는 환경에서는 standalone Playwright를 사용한다. 이 경우에도 실제 HTTP, Keycloak,
Agent Hub UI와 Langflow UI를 사용하며 `file://` 화면은 증거로 인정하지 않는다.

## 타 작성자 자산

Agent Hub 자산 제작자와 Playground 사용자는 같을 필요가 없다. 권한 있는 사용자는 다른
사람이 만든 승인 Flow 또는 custom component를 자기 endpoint/project로 배포하고 exact
Flow를 재발견할 수 있다.

최종 cross-author runner는 다음을 확인했다.

- 작성자 `100001`, 승인 reviewer `2074795`, 채택자 `100002`
- 승인 Flow JSON과 개별 `.py` component
- 채택 exact Flow `afb92757-dac4-4427-aa15-1adb21a09780`
- source author와 checksum 유지
- `action_ready` 후 exact Action draft 생성
- raw Langflow key 재노출 없음

## 2026-07-26 mainline 최종 결과

### canonical

- Agent Hub asset: `d345c5e7-c2b0-4116-aa00-d5e9bad143e5`
- Flow: `73ad7fff-c624-47af-9b57-56d3ab895336`
- checksum:
  `680fe5f4942ec8f8b8641d8d5b0a02cc81202352581961f132388326f8893f8d`
- registration draft: `action-registration-20260726175415-c3aed475`
- publish-request와 exact operator fixture 완료
- 일반/SOP/private draft Action 실행 완료

### LM Studio model Agent

- Agent Hub asset: `8ada6718-f852-4f15-9312-5f186d32d293`
- Flow: `ec3bc2d9-3c27-424c-812c-98c1f25ae54e`
- checksum:
  `00e54b53b8104b86e1afcc002c9c557e052e41afe477b92be131898eefcfc982`
- model: `google/gemma-4-26b-a4b-qat`
- 실제 response ID·latency가 있는 `real_inference=true`
- 독립 Action draft·publish-request·일반/SOP/private draft 완료

두 Flow의 일반 실행은 source 6개, Ontology 관계 40개를 반환한다. private draft owner는
caller `100002`이고 `100003` Action 실행은 403이다. 예상하지 못한 HTTP/page/console
오류는 0건이다.

incompatible Flow `ec848330-97fa-4637-9f16-c631ebacc956`는 `BoIWikiSave` 누락으로
`blocked`되고 Action draft가 409로 거부된다. 한 Flow의 성공이 다른 Flow 상태를
대신하지 않는다.

## 회귀·인수

- 1.10 Flow export → clean 1.11 upload 201 → `/api/v1/run` 200
- DB clone migration에서 user Flow·Credential 복호화 유지
- 1.10 image·DB·secret rollback
- 순정 공식 package와 read-only bundle runtime의 Langflow package hash 동일
- 전체 main 테스트 `613 passed`
- connector-neutral Gateway 회귀 `19 passed`

최종 자료는
`artifacts/agent-playground-handoff/<run_id>-mainline-final-audit/`에 모은다.
`regression/mainline-completion-audit.json`이 source boundary, browser, Langflow,
Action, live stack을 요구사항별로 판정한다. 과거 integration branch나 임시 `/tmp`
경로는 적용·인수 기준이 아니다.
