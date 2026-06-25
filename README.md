# BoI Wiki

BoI Wiki는 OKF 기반의 AI Native Workflow 지식/런타임 시스템입니다.

이 저장소는 공유 런타임입니다.

- BoI Wiki Web UI와 BoI API
- Kafka Event Broker와 Event Router
- API, Webhook, MCP, Langflow, Manual, Event Broker, BoI Writer action을 실행하는 Action Gateway
- agent가 사용할 BoI Wiki MCP 서버
- Langflow reference flow와 BoI custom component 연계
- OKF Markdown 원본 문서, action catalog, event catalog, runtime smoke test

개인 Local Private 작업은 별도 lightweight workspace 저장소를 사용합니다.

```text
/home/chokukil/boi-wiki-local
```

`boi-wiki-local`은 Web 런타임이 아닙니다. 개인 PC에 두는 OKF Markdown workspace와 Codex/Claude/Cursor 하네스 파일 묶음입니다.

## 목적

이 PoC는 AI Native Workflow backbone을 보여줍니다.

- Kafka가 실제 Event Broker 역할을 합니다.
- Event Router가 Kafka의 업무 이벤트를 소비합니다.
- Action Gateway가 이벤트별 등록 connector action을 실행합니다.
- connector는 BoI Writer, Langflow Webhook, HTTP API, generic Webhook, MCP bridge, Manual, Event Broker 등을 포함합니다.
- BoI Wiki는 SOP, 이벤트 기반 업무 맥락, 분석 결과, action 초안, 재사용 가능한 조직 지식, validated source edits, Team/Public promotion status를 저장합니다.

현재 설계에서 BoI Writer는 보조 경로가 아닙니다. Langflow, API, Webhook, MCP와 같은 1급 connector입니다.

```text
Business Event
  -> Kafka Event Broker
  -> Event Router
  -> Action Gateway
       -> BoI Writer Connector
       -> Langflow Webhook Connector
       -> HTTP API Connector
       -> Generic Webhook Connector
       -> MCP bridge Connector
       -> Future Connector
  -> BoI Wiki / API Results / Next Events
```

## 빠른 시작

```bash
cp .env.example .env
docker compose up -d --build
```

열어볼 화면:

- BoI Wiki: http://localhost:8000/?employee_id=100001
- Event Types: http://localhost:8000/event-types?employee_id=100001
- Event Stream: http://localhost:8000/events?employee_id=100001
- SOP: http://localhost:8000/sops?employee_id=100001
- Action Gateway: http://localhost:8100/docs
- BoI Wiki MCP 상태: http://localhost:8200/
- BoI Wiki MCP Streamable HTTP: http://localhost:8200/mcp
- Kafka UI: http://localhost:8081
- Langflow: http://localhost:7860

기본 인증 모드는 `BOI_AUTH_MODE=dev`입니다. PoC와 테스트 편의를 위해 `employee_id` selector/query를 허용합니다.

## NAS / 외부 URL 배포

외부 도메인으로 배포할 때는 사용자가 보는 URL과 Docker 내부 실행 URL을 분리합니다. `actions.yaml`의 `http://boi-api:8000`, `http://langflow:7860`, `http://boi-wiki-mcp:8200` 같은 값은 컨테이너 내부 호출용이므로 바꾸지 않습니다.

NAS에서 BoI Wiki를 외부로 연 최소 설정:

```bash
BOI_EXTERNAL_URL=http://wiki.example.internal:28000
LANGFLOW_EXTERNAL_URL=
KAFKA_UI_EXTERNAL_URL=
BOI_WIKI_MCP_EXTERNAL_URL=
ACTION_GATEWAY_EXTERNAL_URL=
```

Langflow, Kafka UI, MCP Status, Action Gateway의 `*_EXTERNAL_URL`이 비어 있으면 BoI Wiki는 현재 접속 도메인을 기준으로 포트를 추론해 상단 메뉴를 유지합니다. `BOI_EXTERNAL_URL=http://wiki.example.internal:28000` 기준 기본 fallback은 Langflow `27860`, Kafka UI `28081`, Action Gateway `28100`, MCP Status `28200`입니다. reverse proxy나 포트 포워딩이 다른 구조라면 해당 `*_EXTERNAL_URL`을 명시합니다.

### NAS Git 자동 반영

NAS에 Git worktree가 구성되어 있으면 DSM Scheduled Task로 `main` 변경을 1분 주기로 가져오게 할 수 있습니다. 기본 운영 방식은 `git pull --ff-only origin main`이고, 문서/catalog 변경은 재기동 없이 반영하며 코드/compose 변경이 있을 때만 NAS compose를 재실행합니다. 자동 pull 로그는 10 MiB 기준으로 최대 5개까지 rotation합니다.

코드나 정적 asset 변경으로 `boi-api`를 다시 빌드할 때는 `.env`의 `BOI_BUILD_REVISION`도 현재 Git short SHA로 갱신해야 합니다. Synology Compose v1은 `--env-file .env` 값을 우선 사용하므로 shell에서만 export하면 이전 revision이 계속 표시될 수 있습니다. `scripts/nas_auto_pull_deploy.sh`는 이 값을 자동 갱신하고 `/api/runtime/config`의 `build.revision`이 Git HEAD와 일치하는지 검증합니다.

- NAS Git Auto-Pull 운영 절차: http://localhost:8000/docs/boi:public:boi-wiki-manual:operations:nas-git-auto-pull?employee_id=100001

### NAS SERVICE_TOKEN

NAS PoC는 단일 `SERVICE_TOKEN`을 강한 랜덤값으로 유지하고, 변경 시 짧은 maintenance restart로 처리합니다. 무중단 dual-token rotation은 정식 운영 전환 시 별도 검토합니다.

토큰 변경 시 `boi-api`, `action-gateway`, `event-router`, `boi-wiki-mcp`, `langflow`를 같은 compose 사이클에서 재생성해야 합니다. 운영 절차는 BoI Wiki 문서에 남겨둡니다.

- NAS SERVICE_TOKEN 운영 절차: http://localhost:8000/docs/boi:public:boi-wiki-manual:operations:nas-service-token-rotation?employee_id=100001

## 저장소 분리

| 저장소 | 역할 | 대상 |
|---|---|---|
| `/home/chokukil/boi-wiki` | 공유 런타임, source of truth, Web/MCP/API 서비스, 테스트 | 개발자, 운영자, shared Wiki agent |
| `/home/chokukil/boi-wiki-local` | Local Private OKF workspace와 agent 하네스 | Codex, Claude, Cursor를 쓰는 일반 사용자 |

Web Private과 Local Private은 다릅니다.

- Web Private은 이 런타임의 `DATA_ROOT` 아래에 저장되며, 인증된 사번 사용자에게만 Web BoI Wiki에서 보입니다.
- Local Private은 사용자 PC의 `boi-wiki-local`에 저장되며, 이 Web BoI Wiki가 scan하지 않습니다.
- Local Private 공유는 사용자 preview 승인 후 원격 동기 검증을 통과하면 Team/Public에 즉시 게시됩니다. 품질/정책 관리는 HOTL로 사후 개입합니다.

## BoI Wiki MCP

BoI Wiki MCP는 Codex, Claude Desktop, Cursor, Langflow, custom agent가 REST 경로를 외우지 않고 BoI Wiki를 사용할 수 있게 하는 agent-facing 인터페이스입니다.

- 사람이 보는 상태 페이지: http://localhost:8200/
- MCP Streamable HTTP endpoint: http://localhost:8200/mcp
- Action Gateway bridge 호환 endpoint: http://localhost:8200/api/mcp/call
- 매뉴얼: http://localhost:8000/docs/boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp?employee_id=100001
- Agent/Search 하네스: http://localhost:8000/docs/boi:public:harness:agent-api-mcp-search-harness?employee_id=100001

`/mcp`를 브라우저 주소창으로 직접 열어 MCP를 검증하지 마세요. 일반 브라우저나 plain `curl`은 MCP Streamable HTTP `Accept` header가 없어서 `406 Not Acceptable`을 받을 수 있습니다. 상태 페이지나 smoke check를 사용합니다.

외부에서 접근 가능한 MCP endpoint는 `.env`에 `MCP_REQUIRE_SERVICE_TOKEN=true`를 설정하는 것이 기본 운영 기준입니다. 이 경우 `/mcp`도 `x-service-token` 또는 `Authorization: Bearer <token>`이 없으면 `401`을 반환합니다. `/api/mcp/call` bridge는 항상 `x-service-token`을 요구합니다.

검색 경로는 의도를 분리합니다.

- `/api/boi?q=...`와 MCP `boi_search`: 접근 가능한 BoI 문서 목록만 반환합니다.
- `/api/search/ontology`와 MCP `ontology_search`: Dictionary, SOP, Event Type, Action, BoI 문서, runtime evidence를 그룹으로 반환합니다.
- `/api/agents/boi-wiki/chat`와 MCP `boi_agent_chat`: 현재 페이지와 ontology search, memory, inbox를 함께 써서 답변합니다. 기본값은 `BOI_AGENT_BACKEND=native`이며, `diagram/workflow_explain/gap_check/trace_reasoning`도 boi-api 내부 Native BoI Agent가 처리합니다. 자동 라우팅은 LLM Router가 필수이고, Router가 route/intent JSON을 만들지 못하면 규칙 기반 대체 응답 없이 `boi_agent_router_unavailable` 장애로 표시합니다. Router, stream status, composer, suggestions의 `*_REQUIRED` env 이름은 compose 호환용으로 남아 있지만 운영 런타임 정책은 항상 필수입니다. Langflow는 visual workflow/demo/debug backend로 유지하며, legacy `BOI_AGENT_BACKEND=langflow` 모드에서만 필수 backend가 됩니다.
- Native BoI Agent orchestration은 운영 기본값에서 `BOI_AGENT_LANGGRAPH_REQUIRED=1`입니다. LangGraph import나 graph 실행이 실패하면 sequential runtime으로 숨기지 않고 `native_agent_runtime_unavailable` 장애로 표시합니다.
- Native BoI Agent의 최종 답변은 Python typed tool loop가 만든 근거와 artifact를 기준으로 하고, `BOI_AGENT_COMPOSER_LLM_ENABLED=auto`일 때 OpenAI-compatible Gemma composer가 일반 구성원용 문장으로 다듬습니다. `BOI_AGENT_COMPOSER_REQUIRED` 값을 낮춰도 운영 런타임은 composer 필수 정책을 유지하며, composer가 최종 답변을 만들지 못하면 deterministic 문장으로 숨기지 않고 `native_agent_runtime_unavailable` 장애로 표시합니다.
- NAS PoC의 Agent LLM 호출은 짧은 예산으로 제한합니다. 기본 `BOI_AGENT_STATUS_TIMEOUT_SECONDS=12`, `BOI_AGENT_COMPOSER_TIMEOUT_SECONDS=12`, `BOI_AGENT_COMPOSER_MAX_ATTEMPTS=2`이며, 작은 status/answer-plan JSON을 만들지 못하면 긴 대기나 규칙 기반 대체 답변 대신 Agent 장애로 노출합니다. 두 번째 composer 호출은 규칙 기반 fallback이 아니라 깨진 JSON을 같은 LLM에 재작성시키는 repair 시도입니다.
- non-stream `/api/agents/boi-wiki/chat`는 `BOI_AGENT_CHAT_TIMEOUT_SECONDS` 안에 최종 JSON을 만들지 못하면 `boi_agent_timeout` 503을 반환합니다. MCP 같은 외부 호출자는 이를 정상 답변이 아니라 Agent 장애로 처리해야 하며, 서버는 짧은 대체 답변을 만들지 않습니다.
- `/api/agents/boi-wiki/chat/stream`: Web Pet Agent용 SSE endpoint입니다. 오래 걸리는 질문은 LLM stream planner가 만든 `route + status` 계획을 먼저 받고, `status` 한 줄 진행 상황을 보여주며, `answer_delta`로 답변을 누적한 뒤 `final` JSON으로 links/artifacts를 확정합니다. stream planner가 route/status JSON을 만들지 못하면 SSE를 시작하지 않고 HTTP `503`의 `status_generation_failed` 또는 `boi_agent_router_unavailable` 장애로 반환합니다. `BOI_AGENT_STATUS_REQUIRED`는 호환용 설정명으로 남아 있지만 런타임 정책은 항상 필수이며, 값을 낮춰도 canned status fallback은 생기지 않습니다.
- `/api/agents/boi-wiki/suggestions`: 현재 페이지 추천 질문은 LLM suggestion writer가 만듭니다. `BOI_AGENT_SUGGESTIONS_REQUIRED` 값을 낮춰도 운영 런타임은 suggestion writer 필수 정책을 유지하며, writer가 실패하면 템플릿 질문으로 대체하지 않고 `boi_agent_suggestions_unavailable` 장애로 표시합니다.
- Agent/Search/MCP/Inbox/Action 실행은 모두 BoI Profile ACL과 팀 RBAC guardrail을 통과합니다. 권한 관리는 Web 상단 `권한 관리` 메뉴와 `/api/rbac/*` API에서 확인합니다.
- 신규 Event Type은 MCP/API 어디서든 즉시 catalog에 넣지 않습니다. `event_type_draft_create`로 초안을 만들고 `event_type_draft_validate` 검증 뒤, 사용자 확인과 `boi.promoter` 권한을 통과할 때만 `event_type_draft_apply`로 반영합니다.

Public dictionary는 BoI Agent가 반도체/품질/설비/패키징 용어를 이해하기 위한 기본 seed vocabulary입니다. 예를 들어 `단면검사`, `Cpk`, `시계열 예측`, `HBM`, `하이브리드 본딩` 같은 현장 표현은 먼저 dictionary로 해석되고, 필요한 경우 SOP/Event/Action 후보로 확장됩니다. Agent나 MCP client를 만들 때는 단순 문서 목록이 필요하면 `boi_search`, 업무 맥락 탐색이나 질문 의도 해석이 필요하면 `ontology_search`를 우선 사용합니다.

BoI Agent 기술 문서는 Wiki에 정리되어 있습니다.

- Native Agent Architecture: http://localhost:8000/docs/boi:public:boi-wiki-manual:agent:native-boi-agent-architecture?employee_id=100001
- Native Agent Tool Loop: http://localhost:8000/docs/boi:public:boi-wiki-manual:agent:native-boi-agent-tool-loop?employee_id=100001
- Agent Guardrail and ACL: http://localhost:8000/docs/boi:public:boi-wiki-manual:agent:agent-guardrail-and-acl?employee_id=100001
- Pet Agent UX and Artifacts: http://localhost:8000/docs/boi:public:boi-wiki-manual:agent:pet-agent-ux-and-artifacts?employee_id=100001
- BoI Profile ACL Policy: http://localhost:8000/docs/boi:public:boi-wiki-manual:security:boi-profile-acl-policy?employee_id=100001
- Team RBAC Management: http://localhost:8000/docs/boi:public:boi-wiki-manual:security:team-rbac-management?employee_id=100001
- Ontology Retrieval and Search: http://localhost:8000/docs/boi:public:boi-wiki-manual:agent:ontology-retrieval-and-search?employee_id=100001
- Safety, Approval, and Memory: http://localhost:8000/docs/boi:public:boi-wiki-manual:agent:safety-approval-and-memory?employee_id=100001
- Deployment and Verification: http://localhost:8000/docs/boi:public:boi-wiki-manual:agent:deployment-and-verification?employee_id=100001

Langflow는 optional visual/debug backend입니다. 외부 agent와 사용자는 BoI API 또는 BoI Wiki MCP를 공식 인터페이스로 사용합니다.

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url http://localhost:8200 \
  --mcp-url http://localhost:8200/mcp \
  --summary
```

protected MCP와 bridge를 함께 확인할 때:

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url "$BOI_WIKI_MCP_EXTERNAL_URL" \
  --mcp-url "$BOI_WIKI_MCP_EXTERNAL_URL/mcp" \
  --service-token "$SERVICE_TOKEN" \
  --require-bridge \
  --summary
```

Codex, Claude Desktop, Cursor 등록 전 상세 체크:

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url http://localhost:8200 \
  --mcp-url http://localhost:8200/mcp \
  --details \
  --client-checklist
```

위 명령은 `MCP_REQUIRE_SERVICE_TOKEN=false`인 로컬 개발 endpoint 기준입니다. `MCP_REQUIRE_SERVICE_TOKEN=true`인 protected endpoint에서는 token 없이 protocol check가 `auth_required`로 실패하는 것이 정상이며, `--service-token "$SERVICE_TOKEN"`과 `--require-bridge`를 함께 사용합니다.

## SSO 개발 모드

SK hynix 스타일 Keycloak/HCP 경로를 로컬에서 확인하려면 SSO dev overlay를 사용합니다.

```bash
docker compose -f docker-compose.yml -f docker-compose.sso-dev.yml up -d --build
```

열어볼 화면:

- BoI Wiki SSO login: http://localhost:8000/auth/login
- Keycloak dev realm: http://localhost:8088
- Langflow Hynix SSO UI: http://localhost:7860

dev realm은 `100001`, `100002`, `100003` 사용자를 만들고 password는 `password`입니다. `100001`은 `aix-tf`, `platform` 팀과 admin 역할을 모두 갖습니다. `100002`는 `aix-tf`, `100003`은 `platform`만 갖습니다.

`BOI_AUTH_MODE=keycloak`에서는 query 사번 spoofing이 거부됩니다. 내부 Event Router, Action Gateway, MCP bridge 호출은 `x-service-token`과 대상 `employee_id`를 함께 사용해야 합니다.

SSO dev overlay는 `langflow-hynix` Keycloak/HCP 모델에 맞춰져 있습니다.

- Langflow는 `KEYCLOAK_HCP_API_URL`, `KEYCLOAK_ALLOWED_EMPLOYEE`, `KEYCLOAK_EMPLOYEE_CLAIM`, `KEYCLOAK_SHARED_USERNAME`을 읽습니다.
- BoI Wiki는 Wiki 전용 `BOI_*` 이름을 유지하면서 동일한 `KEYCLOAK_*` alias를 받습니다.
- Mock HCP는 BoI Wiki용 `GET /api/permissions?employee_id=...`와 Langflow-Hynix용 `GET /v1/projects/{project}/roles`를 제공합니다.
- workflow start, action invoke, source/body apply, promotion은 `boi.workflow_runner`, `boi.action_invoker`, `boi.editor`, `boi.promoter` 역할로 통제됩니다.

## BoI 하네스

하네스 문서는 Codex, Claude, Langflow, custom agent가 curated BoI Wiki 지식을 만들거나 수정할 때 따라야 하는 기준입니다.

- repo 원본: `harness/README.md`
- BoI Wiki 진입점: http://localhost:8000/docs/boi:public:harness:overview?employee_id=100001
- SOP 작성: http://localhost:8000/docs/boi:public:harness:sop-authoring-harness?employee_id=100001
- Action 작성: http://localhost:8000/docs/boi:public:harness:action-authoring-harness?employee_id=100001
- Local Private agent 하네스: http://localhost:8000/docs/boi:public:harness:local-private-agent-harness?employee_id=100001
- Web validated editing: http://localhost:8000/docs/boi:public:harness:web-draft-editing-guide?employee_id=100001
- 활용 사례: http://localhost:8000/docs/boi:public:boi-wiki-manual:use-cases:sop-flow-visualization?employee_id=100001

Web/MCP source/body edit는 사용자 승인 후 즉시 preview, lint, validation, apply, 자동 commit을 수행합니다. 검증이나 commit이 실패하면 원본 Markdown/YAML은 유지되고 validation feedback과 수정 제안만 반환됩니다. Team/Public promotion은 별도 publish 경로이며, 사용자 승인과 원격 자동 검증 통과 후 즉시 게시됩니다.

## BoI Wiki Local

일반 사용자가 Python, Docker, Git, MCP를 몰라도 개인 Local Private workspace를 쓰고 싶을 때 BoI Wiki Local을 사용합니다.

이 환경에 생성된 local repository 경로:

```text
/home/chokukil/boi-wiki-local
```

사용자 환경에서는 `boi-wiki-local` repo URL을 agent에게 주고 이렇게 말하면 됩니다.

```text
이 repo 설치해줘.
이 폴더를 BoI Wiki Local로 써줘.
이 회의 내용을 BoI로 정리해줘.
```

Local Private 문서는 사용자 local workspace에만 남고 이 Web BoI Wiki의 `DATA_ROOT`에 scan되지 않습니다. 원격 공유는 사용자 명시 확인이 있어야 하며, agent가 sanitized promotion candidate를 만든 뒤 원격 동기 검증/게시를 요청합니다. 일반 사용자는 Git commit을 직접 신경 쓰지 않습니다.

`boi-wiki-local`은 skills-first local workspace입니다. MCP를 몰라도 회의록 BoI, SOP 초안, Action 초안, Mermaid 도식, context pack, workflow simulation을 만들 수 있습니다. MCP가 연결되면 shared SOP/Event/Action/Workflow Status 검색에 활용하고, 원격 쓰기나 실행은 사용자 승인 후에만 수행합니다. 공식 MCP는 shared `boi-wiki-mcp` 하나이며 local MCP 서버는 사용자 기본 경로에 포함하지 않습니다.

매뉴얼:

- Local Private 시작하기: http://localhost:8000/docs/boi:public:boi-wiki-manual:local-private:overview?employee_id=100001
- Local Private 하네스: http://localhost:8000/docs/boi:public:harness:local-private-agent-harness?employee_id=100001
- SOP Flow Visualization: http://localhost:8000/docs/boi:public:boi-wiki-manual:use-cases:sop-flow-visualization?employee_id=100001
- Event-to-Action Workflow Planning: http://localhost:8000/docs/boi:public:boi-wiki-manual:use-cases:event-to-action-workflow-planning?employee_id=100001
- API Doc to Action Spec: http://localhost:8000/docs/boi:public:boi-wiki-manual:use-cases:api-doc-to-action-spec?employee_id=100001
- Agent Context Pack: http://localhost:8000/docs/boi:public:boi-wiki-manual:use-cases:agent-context-pack?employee_id=100001
- SOP Image to E2E Workflow: http://localhost:8000/docs/boi:public:boi-wiki-manual:use-cases:sop-image-to-e2e-workflow?employee_id=100001

대표 요청:

```text
설비 이상 대응 SOP를 Mermaid 프로세스 플로우로 그려줘.
이 이벤트가 발생하면 어떤 SOP와 Action이 이어지는지 알려줘.
기존 API 문서를 BoI Action Spec 초안으로 만들어줘.
원격 BoI Wiki를 검색해서 이번 업무용 context pack을 만들어줘.
MCP 설정은 모르겠으니 local만 써줘.
```

## 검증

shared repo 검증:

```bash
python scripts/okf_lint.py --root data --include-logs --strict-media --strict-links
pytest tests -q -s
python scripts/check_boi_wiki_mcp.py --base-url http://localhost:8200 --mcp-url http://localhost:8200/mcp --summary
```

일반 Local 사용자는 위 명령을 직접 실행하지 않아도 됩니다. `boi-wiki-local`에서는 agent 하네스가 Level 0 self-check를 수행하고, 가능하면 `check.sh` 또는 `check.ps1`을 실행합니다.

## 핵심 개념

### Event Broker

Kafka는 다음과 같은 업무 이벤트를 전달합니다.

- `meeting.closed.v1`
- `action.created.v1`
- `report.requested.v1`
- `promotion.requested.v1`
- `equipment.alarm.raised.v1`
- `trend.anomaly.detected.v1`
- `root_cause.analysis.requested.v1`
- `maintenance.guide.requested.v1`
- `corrective_action.requested.v1`

### Event Router

Event Router는 프로토콜 중립입니다. Langflow를 1차 경로로, BoI API를 2차 경로로 판단하지 않습니다. Event Type을 읽고 Action Gateway를 통해 등록된 connector action을 실행합니다.

### Action Gateway

Action Gateway는 connector abstraction layer입니다. connector action은 다음 파일에 정의됩니다.

```text
data/action_catalog/actions.yaml
```

지원 connector action type:

| Type | 의미 |
|---|---|
| `boi_materialize` | 업무 이벤트에서 BoI 문서 생성 |
| `langflow_webhook` | Langflow Webhook Flow 호출 |
| `http` / `api` | REST 스타일 내부 API 호출 |
| `webhook` / `internal_webhook` | generic webhook 호출 |
| `mcp_tool` | BoI Wiki MCP bridge 또는 MCP-compatible endpoint 호출 |
| `boi_event` | 다음 업무 이벤트를 Kafka에 발행 |
| `mock_api` | PoC에서 보이는 시스템/API 호출 결과 |

### BoI Wiki

BoI Wiki는 사람과 agent가 함께 쓰는 지식 표면입니다.

- Public SOP와 공통 문서
- 사번/팀 ACL 기반 Team BoI
- 현재 사번 사용자의 Web-created Private BoI
- Event Type Catalog
- Event Stream
- Event-linked BoI 문서

local agent가 만든 Local-only Private BoI는 Web BoI Wiki에 의도적으로 보이지 않습니다.

## Demo: 설비 이상 SOP Workflow

SOP workflow 시작:

```bash
curl -X POST "http://localhost:8000/api/workflows/demo/equipment-anomaly/start?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{"equipment_id":"ETCH-VM-01","alarm_code":"RESPONSE_CHAIN_ABNORMAL","title":"Response Chain 이상 Alarm 발생"}'
```

확인:

- Event Stream: http://localhost:8000/events?employee_id=100001
- Event-linked BoI: http://localhost:8000/?employee_id=100001&event_type=equipment.alarm.raised.v1
- Action logs: http://localhost:8100/api/actions/logs

## Connector 설정 예시

```yaml
- action_key: boi.materialize_event
  type: boi_materialize
  enabled: true
  event_types: ["*"]
  risk_level: low
  approval_required: false
  dry_run_default: false

- action_key: langflow.meeting_writer.sample
  type: langflow_webhook
  enabled: false
  event_types: [meeting.closed.v1]
  flow_id: ${payload.langflow_flow_id}
  risk_level: low
  approval_required: false

- action_key: mcp.boi_search.sample
  type: mcp_tool
  enabled: false
  event_types: [report.requested.v1]
  tool_name: boi.search
  arguments:
    query: ${payload.query}
    employee_id: ${employee_id}
```

## Intranet 전환 메모

PoC 요소는 다음 기업 내부 서비스로 교체합니다.

| PoC | Intranet Target |
|---|---|
| hardcoded employee/team map | SSO/IAM/HR 조직 데이터 |
| file-based BoI Wiki | 내부 문서/Wiki/Git/SharePoint 저장소 |
| mock API | 품질 시스템, 비전 검사 시스템, 설비, 승인, 알림 API |
| development key | Secret Manager |
| `BOI_AUTH_MODE=dev` | Keycloak SSO + HCP permission API |
| MCP bridge/server | 내부 MCP bridge/server와 승인된 MCP endpoint |
| high-risk action 사전 확인 | 사람 승인과 change-management workflow |

## 보안 기본값

- Webhook/API 호출에는 service token 또는 API key가 필요합니다.
- SSO 모드에서는 사용자 identity가 Keycloak/HCP에서 옵니다. query `employee_id`는 개발 모드 전용입니다.
- Action Gateway는 allowlisted host만 호출합니다.
- high-risk action은 approval-required입니다.
- Private BoI는 사번 단위로 scope가 제한됩니다.
- Team/Public promotion은 copy-not-move입니다.
- Team/Public promotion은 사용자 승인과 자동 검증 후 `review_status: user_confirmed`, `hotl.status: watching`으로 게시됩니다.
