# BoI Wiki

BoI Wiki는 OKF 기반의 업무 BoI 지식/런타임 시스템입니다. 공식 SOP가 있는 정형 업무뿐 아니라 반복 업무와 비정형 개인 업무도 업무 목적, 근거, 다음 행동, 완결 조건 중심으로 정리합니다.

이 저장소는 공유 런타임입니다.

- BoI Wiki Web UI와 BoI API
- Kafka Event Broker와 Event Router
- API, Webhook, MCP, Langflow, Manual, Event Broker, BoI Writer action을 실행하는 Action Gateway
- Event Contract, WorkflowDefinition, Action/Event Skill registry
- agent가 사용할 BoI Wiki MCP 서버
- Langflow reference flow와 BoI custom component 연계
- OKF Markdown 원본 문서, action catalog, event catalog, runtime smoke test

개인 Local Private 작업은 별도 lightweight workspace 저장소를 사용합니다.

```text
/home/chokukil/boi-wiki-local
```

`boi-wiki-local`은 Web 런타임이 아닙니다. 개인 PC에 두는 OKF Markdown workspace와 Codex/Claude/Cursor 하네스 파일 묶음입니다.

## 목적

이 Pilot은 업무 BoI-first runtime을 보여줍니다.

- Kafka가 실제 Event Broker 역할을 합니다.
- Event Router가 Kafka의 업무 이벤트를 소비합니다.
- Action Gateway가 이벤트별 등록 connector action을 실행합니다.
- WorkflowDefinition이 업무 목적, 필요한 업무 BoI, Event, SOP 또는 업무 단계, Action, Manual Handoff, evidence, affordance, RBAC/ACL policy를 함께 묶습니다.
- connector는 BoI Writer, Langflow Webhook, HTTP API, generic Webhook, MCP bridge, Manual, Event Broker 등을 포함합니다.
- BoI Wiki는 SOP, 비정형 업무 BoI, 이벤트 기반 업무 맥락, 분석 결과, Action 초안, 재사용 가능한 조직 지식, validated source edits, Team/Public promotion status를 저장합니다.

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
cp .env.local-full.example .env
./scripts/start_local_full.sh
python scripts/check_local_full_readiness.py --base-url http://localhost:28000
python scripts/check_langflow_universal_simulator.py --langflow-url http://localhost:7860 --boi-api-url http://localhost:28000
SERVICE_TOKEN=dev-service-token-change-me python scripts/run_equipment_sop_poc.py --scenario-profile semiconductor-varied --count 8
python scripts/check_inbox_narrative_quality.py --base-url http://localhost:28000 --summary --require-ready-report
python scripts/check_boi_agent_scenarios.py --base-url http://localhost:28000 --strict --summary
node scripts/check_pet_agent_ui.mjs --scenario-file tests/fixtures/boi_agent_ui_scenarios.yaml --strict
```

기본 Web 포트는 `28000`입니다. 다른 포트를 써야 하면 `.env` 또는 실행 환경에 `BOI_API_PORT=xxxxx`, `BOI_EXTERNAL_URL=http://localhost:xxxxx`를 지정합니다. `scripts/start_local_full.sh`는 `.env.local-full.example`을 기본값으로 읽고, `.env`가 있으면 그 값을 오버레이합니다. 같은 Compose 프로젝트가 이미 떠 있으면 먼저 내리고 다시 올립니다. 28000을 다른 Docker 컨테이너가 점유 중이면 기본적으로 중단하고 알려주며, 로컬 검증용으로 강제 정리가 필요할 때만 `BOI_FORCE_PORT_RECLAIM=1 ./scripts/start_local_full.sh`를 사용합니다.

`local-full`은 repo 전체를 컨테이너의 `/workspace`에 마운트하고 `BOI_CONTENT_ROOT=/workspace/data/boi`, `BOI_CONTENT_SAFE_DIRECTORY=/workspace`를 사용합니다. 이 구조라야 BoI API가 `.git`을 보고 validated edit 후 commit을 만들 수 있습니다.

열어볼 화면:

- BoI Wiki: http://localhost:28000/?employee_id=100001
- BoI Inbox: http://localhost:28000/inbox?employee_id=100001
- SOP: http://localhost:28000/sops?employee_id=100001
- SOP 추가: http://localhost:28000/sops/new?employee_id=100001
- Event Broker: http://localhost:28000/events?employee_id=100001
- Event 카탈로그: http://localhost:28000/event-types?employee_id=100001
- Event 추가: http://localhost:28000/sops/new?employee_id=100001&focus=event
- Action: http://localhost:28000/actions?employee_id=100001
- Action 추가: http://localhost:28000/sops/new?employee_id=100001&focus=action
- Advanced / Agent Builder: http://localhost:28000/agents/builder?employee_id=100001
- Action Gateway: http://localhost:8100/docs
- BoI Wiki MCP 상태: http://localhost:8200/
- BoI Wiki MCP Streamable HTTP: http://localhost:8200/mcp
- Kafka UI: http://localhost:8081
- Langflow: http://localhost:7860

기본 인증 모드는 `BOI_AUTH_MODE=dev`입니다. PoC와 테스트 편의를 위해 `employee_id` selector/query를 허용합니다.

BoI Agent의 Pilot 완료 기준은 단일 질문이 아니라 REST/Web Pet/MCP 시나리오 매트릭스 통과입니다. 상세 기준은 http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:boi-agent-scenario-validation?employee_id=100001 에 정리되어 있습니다.

## Pilot 배포 모델

Pilot 기준은 NAS가 아니라 `local-full` 검증 후 사내 Linux Docker 서버 배포입니다. Kafka와 Langflow가 사내에 이미 있으면 BoI Wiki가 새로 띄우지 않고 env만 바꿔 연결합니다.

| Profile | 포함 서비스 | 용도 |
|---|---|---|
| `local-full` | BoI API, Action Gateway, Event Router, MCP, local Kafka, Kafka UI, local Langflow | 내 Docker에서 전체 기능 재현 |
| `local-full-datalake` | `local-full` + optional PostgreSQL/MinIO Data Lake demo | 사내 legacy DB/Data Lake evidence 활용 예시. Core 완료 기준은 아님 |
| `pilot-external` | BoI API, Action Gateway, Event Router, MCP | 사내 Kafka/Langflow 기존 서비스 연계 |
| `core` | BoI API | 단일 컨테이너 가능 범위 확인용. Workflow runtime 공식 운영용은 아님 |

Data Lake는 선택 기능입니다. BoI Wiki core는 OKF Markdown/JSONL 기반으로 DB 없이 동작해야 하며, PostgreSQL/MinIO가 없다고 `/inbox`, MCP, Agent, OKF lint가 실패하면 안 됩니다. Data Lake를 켠 경우에도 Agent와 UI는 DB에 직접 접속하지 않고 BoI API/MCP의 plan, preview, confirmed execute 경로만 사용합니다.

선택형 Data Lake demo는 별도 overlay로만 켭니다. `~/ontology`의 JSON/CSV fixture는 import/demo source이며 BoI Wiki runtime 필수 경로가 아닙니다.

```bash
BOI_COMPOSE_PROFILE=local-full-datalake \
BOI_ENV_FILE=.env.local-full.example \
BOI_ENV_OVERLAY_FILE=.env:.env.local-full-datalake.example \
./scripts/start_local_full.sh

python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --import-data-context
```

기본 `local-full` 경계 확인은 Data Lake가 꺼져 있어도 통과해야 합니다.

```bash
python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --allow-disabled
```

사내 Pilot 템플릿:

```bash
cp .env.pilot-external.example .env
docker compose --profile pilot-external up -d --build
```

사용자가 보는 URL과 Docker 내부 실행 URL은 분리합니다. `actions.yaml`의 `http://boi-api:8000`, `http://langflow:7860`, `http://boi-wiki-mcp:8200` 같은 값은 컨테이너 내부 호출용입니다. 외부 사용자 링크는 `BOI_EXTERNAL_URL`, `LANGFLOW_EXTERNAL_URL`, `BOI_WIKI_MCP_EXTERNAL_URL`로 표시용 URL만 바꿉니다.

### 사내 Kafka / Langflow 연계

`local-full`에서는 compose 내부 Kafka topic 생성과 Langflow flow setup까지 자동 검증합니다. `pilot-external`에서는 topic이나 flow를 생성하지 않고 접근성만 검증합니다.

```bash
python scripts/check_pilot_external_services.py --kafka --consume --timeout 30
python scripts/check_pilot_external_services.py --langflow --run-langflow-endpoint "$LANGFLOW_BOI_AGENT_ENDPOINT"
```

Kafka/Langflow 설정은 `.env`로만 주입합니다. 코드나 tracked 문서에 사내 host, password, token을 고정하지 않습니다. Langflow Universal Simulator는 실제 의사결정 근거 생성기가 아니라 실행 전 확인, PoC, 외부 시스템이 없는 local demo용 dry-run 경로입니다. Inbox 검증 보고서는 실제 Event/Action/BoI/Data Lake/과거 사례 근거를 우선 사용하고, simulator 결과를 보여줄 때는 `시뮬레이션 결과`로 분리합니다.

### 자동 게시/반영

Public/Team/Private 문서 변경은 Pilot 기준에서 검증 후 즉시 반영됩니다. Web/API/Agent가 ACL/RBAC, OKF/Profile validation, secret scan을 통과한 뒤 파일을 쓰고, cache/index를 무효화하며, `BOI_AUTO_COMMIT=true`이면 commit합니다. `BOI_AUTO_PUSH=true`이면 `BOI_CONTENT_GIT_REMOTE`/`BOI_CONTENT_GIT_BRANCH`로 push까지 수행합니다.

문서 저장소와 런타임 로그는 분리합니다.

```bash
BOI_CONTENT_HOST_PATH=/srv/boi-wiki/content
BOI_CONTENT_MOUNT_PATH=/content
BOI_CONTENT_ROOT=/content/boi
BOI_CONTENT_SAFE_DIRECTORY=/content
BOI_RUNTIME_ROOT=/runtime
```

`pilot-external`에서 `/srv/boi-wiki/content`는 반드시 git checkout이어야 합니다. `/api/runtime/config`의 `readiness.ok`, Git sync status, persisted search index 상태, build revision을 확인합니다.

### Legacy NAS 문서

NAS PoC 운영 문서는 히스토리 보존용입니다. Pilot 완료 기준이나 기본 배포 경로로 사용하지 않습니다.

- NAS Git Auto-Pull 운영 절차: http://localhost:28000/docs/boi:public:boi-wiki-manual:operations:nas-git-auto-pull?employee_id=100001
- NAS SERVICE_TOKEN 운영 절차: http://localhost:28000/docs/boi:public:boi-wiki-manual:operations:nas-service-token-rotation?employee_id=100001

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
- 매뉴얼: http://localhost:28000/docs/boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp?employee_id=100001
- Agent/Search 하네스: http://localhost:28000/docs/boi:public:harness:agent-api-mcp-search-harness?employee_id=100001

`/mcp`를 브라우저 주소창으로 직접 열어 MCP를 검증하지 마세요. 일반 브라우저나 plain `curl`은 MCP Streamable HTTP `Accept` header가 없어서 `406 Not Acceptable`을 받을 수 있습니다. 상태 페이지나 smoke check를 사용합니다.

외부에서 접근 가능한 MCP endpoint는 `.env`에 `MCP_REQUIRE_SERVICE_TOKEN=true`를 설정하는 것이 기본 운영 기준입니다. 이 경우 `/mcp`도 `x-service-token` 또는 `Authorization: Bearer <token>`이 없으면 `401`을 반환합니다. `/api/mcp/call` bridge는 항상 `x-service-token`을 요구합니다.

검색 경로는 의도를 분리합니다.

- `/api/boi?q=...`와 MCP `boi_search`: 접근 가능한 BoI 문서 목록만 반환합니다.
- `/api/search/ontology`와 MCP `ontology_search`: Dictionary, SOP, Event Type, Action, BoI 문서, runtime evidence를 그룹으로 반환합니다.
- `/api/agents/boi-wiki/chat`와 MCP `boi_agent_chat`: 현재 페이지와 ontology search, memory, BoI Inbox context를 함께 써서 답변합니다. 기본값은 `BOI_AGENT_BACKEND=native`이며, `diagram/workflow_explain/gap_check/trace_reasoning`도 boi-api 내부 Native BoI Agent가 처리합니다. LLM Router는 goal/route 후보 생성기이며, Router가 timeout, invalid JSON, low confidence를 반환해도 page context, ontology search, WorkContextPack으로 답할 수 있으면 Native Agent가 계속 답변하고 원인은 `component_errors`/`diagnostics`에 남깁니다. Langflow는 visual workflow/demo/debug backend로 유지하며, legacy `BOI_AGENT_BACKEND=langflow` 모드에서만 필수 backend가 됩니다.
- Native BoI Agent orchestration은 운영 기본값에서 `BOI_AGENT_LANGGRAPH_REQUIRED=1`입니다. LangGraph import나 graph 실행이 실패하면 sequential runtime으로 숨기지 않고 `native_agent_runtime_unavailable` 장애로 표시합니다.
- Native BoI Agent의 최종 답변은 Python typed tool loop가 만든 근거와 artifact를 authoritative contract로 삼고, `BOI_AGENT_COMPOSER_LLM_ENABLED=auto`일 때 OpenAI-compatible Gemma composer가 일반 구성원용 문장으로 다듬습니다. Composer가 invalid JSON, timeout, parser failure를 반환해도 typed answer와 artifact는 유지하고 원인은 `component_errors`에 남깁니다. 답변을 만들 근거 자체가 없거나 Native runtime이 실행되지 못할 때만 Agent 장애로 처리합니다.
- Pilot의 Agent LLM 호출은 짧은 예산과 명시적 큐잉으로 제한합니다. 기본 `BOI_AGENT_LLM_MAX_CONCURRENCY=1`, `BOI_AGENT_LLM_QUEUE_TIMEOUT_SECONDS=120`, `BOI_AGENT_STATUS_TIMEOUT_SECONDS=30`, `BOI_AGENT_COMPOSER_TIMEOUT_SECONDS=30`, `BOI_AGENT_COMPOSER_MAX_ATTEMPTS=2`, `BOI_AGENT_SUGGESTIONS_MAX_ATTEMPTS=2`입니다. 작은 Gemma gateway에서는 Pet UI와 MCP smoke가 동시에 Agent를 호출해도 API 내부에서 순서대로 처리합니다. 큐 대기나 JSON 생성 실패는 `component_errors`/diagnostic event로 기록하며, typed answer를 만들 수 있는 경우 사용자 답변 자체는 유지합니다. composer/suggestions의 두 번째 호출은 규칙 기반 fallback이 아니라 깨진 JSON을 같은 LLM에 재작성시키는 repair 시도입니다.
- non-stream `/api/agents/boi-wiki/chat`는 `BOI_AGENT_CHAT_TIMEOUT_SECONDS` 안에 최종 JSON을 만들지 못하면 `boi_agent_timeout` 503을 반환합니다. MCP 같은 외부 호출자는 이를 정상 답변이 아니라 Agent 장애로 처리해야 하며, 서버는 짧은 대체 답변을 만들지 않습니다.
- `/api/agents/boi-wiki/chat/stream`: Web Pet Agent용 SSE endpoint입니다. 오래 걸리는 질문은 LLM stream planner가 만든 `route + status` 계획을 먼저 받고, `status` 한 줄 진행 상황을 보여주며, `answer_delta`로 답변을 누적한 뒤 `final` JSON으로 links/artifacts를 확정합니다. `final.status_updates`가 canonical 진행 기록이고 `final.status_events`는 같은 배열을 담는 호환 alias입니다. stream planner가 route/status JSON을 만들지 못하면 `diagnostic` event에 `status_generation_failed` 또는 `boi_agent_router_unavailable`을 남기고, Native Agent가 답할 수 있으면 `answer_ready`와 `final`을 계속 보냅니다. canned status 문구를 만들어내지는 않습니다.
- `/api/agents/boi-wiki/suggestions`: 첫 대화 전 page starter 질문과, `answer_context`가 있는 경우 답변 기반 follow-up 질문을 LLM suggestion writer가 만듭니다. `/api/agents/boi-wiki/chat` 최종 응답도 `evidence_ledger`, `affordances`, `artifacts`, `links`, `citations`를 바탕으로 만든 answer-scoped `suggested_questions`를 포함합니다. Writer가 실패하면 답변은 유지하고 `component_errors`에 `boi_agent_suggestions_unavailable`을 남깁니다. 서버는 오래된 템플릿 질문을 정상 추천처럼 섞어 넣지 않습니다.
- Agent/Search/MCP/Inbox/Action 실행은 모두 BoI Profile ACL과 팀 RBAC guardrail을 통과합니다. 권한 관리는 Web 상단 `권한 관리` 메뉴와 `/api/rbac/*` API에서 확인합니다.
- 신규 SOP/Event/Action은 사용자-facing 기준으로 `/sops/new`의 `SOP 추가` 흐름에서 함께 연결합니다. Event 추가와 Action 추가 링크는 각각 `/sops/new?focus=event`, `/sops/new?focus=action`으로 들어가며, 화면은 `Event -> SOP -> Action` 3단 구조에서 필요한 섹션만 선택합니다. 일반 사용자는 먼저 자연어로 설명하고, 시스템이 기존 항목 추천과 탐색기 선택, 실행 전 확인을 제공한 뒤 부족한 항목만 draft로 만듭니다. API/MCP에서는 `sop_registration_plan`, `sop_registration_preview`, `event_publish_plan`, `event_publish_preview`, `event_pattern_preview`, `sop_run_history`를 먼저 사용하고, 충분히 확인된 뒤 `sop_registration_draft_create`, `registration_draft_create`, `sop_draft_create`, `action_draft_create` 또는 `event_type_draft_create`로 draft를 만듭니다. 내부 API/MCP에서는 이 연결 단위를 `WorkflowDefinition`으로 부르지만, Web UI의 일반 진입점은 SOP 추가, BoI Wiki 탐색, Event/Action 카탈로그입니다. Action 섹션은 API, MCP, Webhook, Manual, Event Broker, BoI Writer, Langflow 7종 connector를 선택할 수 있으며, Action draft는 `connector_kind`와 `connector_config`를 함께 전달합니다. 사용자 확인 없이는 draft 생성이나 publish 요청을 실행하지 않습니다.
- 신규 Event Type은 MCP/API 어디서든 즉시 catalog에 넣지 않습니다. `event_type_draft_create`로 초안을 만들고 `event_type_draft_validate` 검증 뒤, 사용자 확인과 `boi.promoter` 권한을 통과할 때만 `event_type_draft_apply`로 반영합니다.

Public dictionary는 BoI Agent가 반도체/품질/설비/패키징 용어를 이해하기 위한 기본 seed vocabulary입니다. 예를 들어 `단면검사`, `Cpk`, `시계열 예측`, `HBM`, `하이브리드 본딩` 같은 현장 표현은 먼저 dictionary로 해석되고, 필요한 경우 SOP/Event/Action 후보로 확장됩니다. Agent나 MCP client를 만들 때는 단순 문서 목록이 필요하면 `boi_search`, 업무 맥락 탐색이나 질문 의도 해석이 필요하면 `ontology_search`를 우선 사용합니다. 개인 dictionary는 본인 private scope에 바로 추가할 수 있지만, team/public dictionary는 shared ontology에 영향을 주므로 `boi.editor` 권한과 팀 멤버십 정책을 통과해야 합니다.

BoI Agent 기술 문서는 Wiki에 정리되어 있습니다.

- Native Agent Architecture: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:native-boi-agent-architecture?employee_id=100001
- Native Agent Tool Loop: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:native-boi-agent-tool-loop?employee_id=100001
- Agent Guardrail and ACL: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:agent-guardrail-and-acl?employee_id=100001
- Pet Agent UX and Artifacts: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:pet-agent-ux-and-artifacts?employee_id=100001
- BoI Profile ACL Policy: http://localhost:28000/docs/boi:public:boi-wiki-manual:security:boi-profile-acl-policy?employee_id=100001
- Team RBAC Management: http://localhost:28000/docs/boi:public:boi-wiki-manual:security:team-rbac-management?employee_id=100001
- Ontology Retrieval and Search: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:ontology-retrieval-and-search?employee_id=100001
- Safety, Approval, and Memory: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:safety-approval-and-memory?employee_id=100001
- Deployment and Verification: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:deployment-and-verification?employee_id=100001

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
  --boi-api-url "$BOI_EXTERNAL_URL" \
  --service-token-env SERVICE_TOKEN \
  --require-bridge \
  --agent-contract \
  --summary
```

REST API와 MCP bridge가 같은 typed artifact를 반환하는지까지 확인하려면 `--agent-artifact-smoke`를 추가합니다. 이 smoke는 설비 SOP 현재 페이지 질문으로 `workflow_summary` artifact를 만들고, REST `/api/agents/boi-wiki/chat`와 MCP `boi_agent_chat` 양쪽에서 같은 `boi-agent.response.v1` 계약, `status_updates`, table artifact row를 검증합니다. Web Pet에서만 표가 보이고 API/MCP에서는 임의 문자열만 내려오는 상태를 배포 성공으로 보지 않기 위한 검사입니다.

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url "$BOI_WIKI_MCP_EXTERNAL_URL" \
  --mcp-url "$BOI_WIKI_MCP_EXTERNAL_URL/mcp" \
  --boi-api-url "$BOI_EXTERNAL_URL" \
  --service-token-env SERVICE_TOKEN \
  --require-bridge \
  --agent-contract \
  --agent-artifact-smoke \
  --summary
```

Pilot host Python처럼 `httpx`나 MCP client library가 없는 환경에서는 AgentResponse 계약만 stdlib 기반으로 확인할 수 있습니다. 이 검증은 BoI API canonical schema, MCP `/health` schema, REST chat 응답, authenticated MCP bridge 응답이 모두 같은 `boi-agent.response.v1` 계약을 쓰는지 확인합니다. `--agent-artifact-smoke`를 함께 쓰면 stdlib 모드에서도 REST/MCP bridge `workflow_summary` artifact를 검증합니다. Pilot app directory에서 실행할 때는 token이 process argument에 남지 않도록 `.env`에서 직접 읽습니다.

```bash
python3 scripts/check_boi_wiki_mcp.py \
  --base-url http://127.0.0.1:8200 \
  --boi-api-url http://127.0.0.1:28000 \
  --service-token-dotenv .env \
  --agent-contract-only \
  --agent-artifact-smoke \
  --require-bridge
```

Codex, Claude Desktop, Cursor 등록 전 상세 체크:

```bash
python scripts/check_boi_wiki_mcp.py \
  --base-url http://localhost:8200 \
  --mcp-url http://localhost:8200/mcp \
  --details \
  --client-checklist
```

위 명령은 `MCP_REQUIRE_SERVICE_TOKEN=false`인 로컬 개발 endpoint 기준입니다. `MCP_REQUIRE_SERVICE_TOKEN=true`인 protected endpoint에서는 token 없이 protocol check가 `auth_required`로 실패하는 것이 정상이며, shared host에서는 `--service-token-env SERVICE_TOKEN` 또는 `--service-token-dotenv .env`와 `--require-bridge`를 함께 사용합니다.

## SSO 개발 모드

SK hynix 스타일 Keycloak/HCP 경로를 로컬에서 확인하려면 SSO dev overlay를 사용합니다.

```bash
docker compose -f docker-compose.yml -f docker-compose.sso-dev.yml up -d --build
```

열어볼 화면:

- BoI Wiki SSO login: http://localhost:28000/auth/login
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
- BoI Wiki 진입점: http://localhost:28000/docs/boi:public:harness:overview?employee_id=100001
- SOP 작성: http://localhost:28000/docs/boi:public:harness:sop-authoring-harness?employee_id=100001
- Action 작성: http://localhost:28000/docs/boi:public:harness:action-authoring-harness?employee_id=100001
- Local Private agent 하네스: http://localhost:28000/docs/boi:public:harness:local-private-agent-harness?employee_id=100001
- Web validated editing: http://localhost:28000/docs/boi:public:harness:web-draft-editing-guide?employee_id=100001
- 활용 사례: http://localhost:28000/docs/boi:public:boi-wiki-manual:use-cases:sop-flow-visualization?employee_id=100001

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

- Local Private 시작하기: http://localhost:28000/docs/boi:public:boi-wiki-manual:local-private:overview?employee_id=100001
- Local Private 하네스: http://localhost:28000/docs/boi:public:harness:local-private-agent-harness?employee_id=100001
- SOP Flow Visualization: http://localhost:28000/docs/boi:public:boi-wiki-manual:use-cases:sop-flow-visualization?employee_id=100001
- Event-to-Action Workflow Planning: http://localhost:28000/docs/boi:public:boi-wiki-manual:use-cases:event-to-action-workflow-planning?employee_id=100001
- API Doc to Action Spec: http://localhost:28000/docs/boi:public:boi-wiki-manual:use-cases:api-doc-to-action-spec?employee_id=100001
- Agent Context Pack: http://localhost:28000/docs/boi:public:boi-wiki-manual:use-cases:agent-context-pack?employee_id=100001
- SOP Image to E2E Workflow: http://localhost:28000/docs/boi:public:boi-wiki-manual:use-cases:sop-image-to-e2e-workflow?employee_id=100001

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
python scripts/check_boi_wiki_mcp.py --base-url http://localhost:8200 --mcp-url http://localhost:8200/mcp --boi-api-url http://localhost:28000 --agent-contract --summary
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

사용자-facing Action 추가는 raw `execution_kind`를 직접 쓰지 않습니다. `/sops/new?focus=action`의 Action 섹션에서 7종 connector 중 하나를 선택하고, API는 method/endpoint, MCP는 server/tool, Webhook은 URL/retry, Manual은 담당자와 완료 기준, Event Broker는 Event Type, BoI Writer는 BoI type/target folder, Langflow는 flow endpoint/ref를 채운 뒤 검증합니다. 일반 화면은 기본 Event Broker topic을 사용하고, topic/schema 같은 raw 계약은 고급 설정에서만 다룹니다.

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
curl -X POST "http://localhost:28000/api/workflows/demo/equipment-anomaly/start?employee_id=100001" \
  -H "Content-Type: application/json" \
  -d '{"equipment_id":"ETCH-VM-01","alarm_code":"RESPONSE_CHAIN_ABNORMAL","title":"Response Chain 이상 Alarm 발생"}'
```

확인:

- Event Broker: http://localhost:28000/events?employee_id=100001
- Event-linked BoI: http://localhost:28000/?employee_id=100001&event_type=equipment.alarm.raised.v1
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
