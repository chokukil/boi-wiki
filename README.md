# BoI Wiki

BoI Wiki는 OKF 기반의 업무 BoI 지식/런타임 시스템입니다. 공식 SOP가 있는 정형 업무뿐 아니라 반복 업무와 비정형 개인 업무도 업무 목적, 근거, 다음 행동, 완결 조건 중심으로 정리합니다.

이 저장소는 공유 런타임입니다.

- BoI Wiki Web UI와 BoI API
- Kafka Event Broker와 Event Router
- API, Webhook, MCP, Langflow, Manual, Event Broker, BoI Writer action을 실행하는 Action Gateway
- Event Contract, WorkflowDefinition, Action/Event Skill registry
- agent가 사용할 BoI Wiki MCP 서버
- Harness acceptance, Source Wiki, Local Second Brain, promotion preview API/MCP
- Langflow reference flow와 BoI custom component 연계
- OKF Markdown 원본 문서, action catalog, event catalog, runtime smoke test

개인 Local Private 작업은 별도 lightweight workspace 저장소를 사용합니다.

```text
/home/chokukil/boi-wiki-local
```

`boi-wiki-local`은 Web 런타임이 아닙니다. 개인 PC에 두는 OKF Markdown workspace와 Codex/Claude/Cursor 하네스 파일 묶음입니다.

최종 운영 허브는 [BoI Wiki 종합 가이드](data/boi/public/boi-wiki-manual/guide/final-operator-guide.md)입니다.

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
./scripts/start_agent_v2_stack.sh
python scripts/check_local_full_readiness.py --base-url http://localhost:28000
python scripts/check_langflow_universal_simulator.py --langflow-url http://localhost:7860 --boi-api-url http://localhost:28000
SERVICE_TOKEN=dev-service-token-change-me python scripts/run_equipment_sop_poc.py --scenario-profile semiconductor-varied --count 8
python scripts/check_inbox_narrative_quality.py --base-url http://localhost:28000 --summary --require-ready-report
curl -s http://localhost:28000/api/v2/harness/acceptance
```

기본 Web 포트는 `28000`입니다. 다른 포트를 써야 하면 `.env` 또는 실행 환경에 `BOI_API_PORT=xxxxx`, `BOI_EXTERNAL_URL=http://localhost:xxxxx`를 지정합니다. `scripts/start_local_full.sh`는 `.env.local-full.example`을 기본값으로 읽고, `.env`가 있으면 그 값을 오버레이합니다. 같은 Compose 프로젝트가 이미 떠 있으면 먼저 내리고 다시 올립니다. 28000을 다른 Docker 컨테이너가 점유 중이면 기본적으로 중단하고 알려주며, 로컬 검증용으로 강제 정리가 필요할 때만 `BOI_FORCE_PORT_RECLAIM=1 ./scripts/start_local_full.sh`를 사용합니다.

`local-full`은 repo 전체를 컨테이너의 `/workspace`에 마운트하고 `BOI_CONTENT_ROOT=/workspace/data/boi`, `BOI_CONTENT_SAFE_DIRECTORY=/workspace`, `BOI_RUNTIME_HISTORY_SEED_ROOT=/workspace/data`를 사용합니다. 이 구조라야 BoI API가 `.git`을 보고 validated edit 후 commit을 만들 수 있고, 기존 demo Event/Action/Inbox 이력은 read-only seed로 조회됩니다.

로컬 시작 스크립트는 `boi-api`를 현재 host UID/GID로 실행해 bind mount의 Private BoI가 `root:root`로 생성되지 않게 합니다. 시작 전에 `data/boi/private`의 기존 파일과 폴더가 현재 사용자에게 쓰기 가능한지도 검사합니다. 과거 Docker 실행이 만든 root 소유 파일이 있으면 안내된 `sudo chown -R <uid>:<gid> data/boi/private`를 명시적으로 한 번 실행한 뒤 다시 시작합니다. 애플리케이션은 소유권을 자동 변경하지 않습니다.

로컬 API를 기본 포트 `8765`에서 빠르게 확인할 때는 `scripts/start_dev_api.sh`를 사용합니다. 이 스크립트는 Docker용 `.env` 경로를 로컬 경로로 오인하지 않고 repo의 `data/boi`를 content root로 사용하며 runtime 파일은 `.tmp/boi-runtime`에 분리합니다. 기존 `data/events`, `data/actions`, `data/boi/private/*/inbox-reports`는 `BOI_RUNTIME_HISTORY_SEED_ROOT=$PWD/data`로 읽기 전용 병합 조회합니다. Local Kafka와 topic 초기화, Kafka 관리 UI, bundled MinIO 자료 보관함, Codex/Claude용 MCP v2도 기본으로 함께 시작합니다. 컨테이너 주소는 호스트용 `localhost` 주소로 바꿔 API에 전달합니다. 이미 운영 중인 broker나 저장소를 쓸 때만 `KAFKA_BOOTSTRAP`, `BOI_DATALAKE_MODE=external`, endpoint와 credential을 명시합니다. API만 확인하는 특수한 실행에서는 `BOI_DEV_START_MCP=0`으로 외부 Agent 연결을 끌 수 있습니다.

대용량 과거 Action 이력은 화면 요청에서 `.jsonl.idx` 요약 인덱스를 우선 사용합니다. 인덱스가 없는 seed Action 파일은 전체 합계가 기본 64MB 이하일 때만 병합하고, 16MB를 넘는 indexed 원본은 raw 화면에서도 요약만 표시합니다. 이 제한은 각각 `BOI_RUNTIME_HISTORY_SEED_ACTION_FULL_SCAN_MAX_BYTES`, `BOI_RUNTIME_HISTORY_SEED_ACTION_RAW_READ_MAX_BYTES`로 조정할 수 있습니다.

열어볼 화면:

- BoI Wiki: http://localhost:28000/?employee_id=100001
- BoI Inbox: http://localhost:28000/inbox?employee_id=100001
- BoI Operations Center: http://localhost:28000/ops?employee_id=100001
- SOP: http://localhost:28000/sops?employee_id=100001
- SOP 추가: http://localhost:28000/sops/new?employee_id=100001
- Event Broker: http://localhost:28000/events?employee_id=100001
- Event 카탈로그: http://localhost:28000/event-types?employee_id=100001
- Event 추가: http://localhost:28000/sops/new?employee_id=100001&focus=event
- Action: http://localhost:28000/actions?employee_id=100001
- Action 추가: http://localhost:28000/sops/new?employee_id=100001&focus=action
- 자료 보관함: http://localhost:28000/data-library?employee_id=100001
- BoI Agent: http://localhost:28000/agent
- 나만의 BoI Agent 만들기: http://localhost:28000/helpers/new
- 외부 Agent 연결: http://localhost:28000/agent/access
- 연결 상태: http://localhost:28000/integrations?employee_id=100001
- Action Gateway: http://localhost:8100/docs
- BoI Wiki MCP 상태: http://localhost:8200/
- BoI Wiki MCP v2 Streamable HTTP: http://localhost:8200/mcp/v2
- Kafka UI: http://localhost:8081
- Langflow: http://localhost:7860

기본 인증 모드는 `BOI_AUTH_MODE=dev`입니다. PoC와 테스트 편의를 위해 `employee_id` selector/query를 허용합니다.

BoI Agent의 Pilot 완료 기준은 단일 질문이 아니라 REST/Web Pet/MCP 시나리오 매트릭스 통과입니다. 상세 기준은 http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:boi-agent-scenario-validation?employee_id=100001 에 정리되어 있습니다.

## Pilot 배포 모델

Pilot 기준은 NAS가 아니라 `local-full` 검증 후 사내 Linux Docker 서버 배포입니다. Kafka와 Langflow가 사내에 이미 있으면 BoI Wiki가 새로 띄우지 않고 env만 바꿔 연결합니다.

| Profile | 포함 서비스 | 용도 |
|---|---|---|
| `local-full` | BoI API, Action Gateway, Event Router, MCP, local Kafka, Kafka UI, local Langflow, bundled MinIO | 내 Docker에서 전체 기능 재현 |
| `local-full-datalake` | 이전 설치와의 호환 profile | `local-full`에 기본 포함된 자료 보관함을 명시적으로 선택하던 과거 실행 방식 |
| `local-full-legacy-db-demo` | `local-full-datalake` + optional PostgreSQL Legacy DB Demo | 사내 legacy DB나 Data Lake SQL API를 흉내내는 structured query adapter 예시. Core 완료 기준은 아님 |
| `pilot-external` | BoI API, Action Gateway, Event Router, MCP | 사내 Kafka/Langflow 기존 서비스 연계 |
| `core` | BoI API | 단일 컨테이너 가능 범위 확인용. Workflow runtime 공식 운영용은 아님 |

자료 보관함은 모든 표준 설치에서 `BOI_DATALAKE_MODE=bundled`로 시작하며 MinIO를 함께 띄웁니다. 사내 공용 저장소를 사용할 때만 `external`로 바꾸고 endpoint와 credential을 지정합니다. BoI Wiki의 정본은 계속 OKF Markdown/Git이고, MinIO에는 긴 원본을 보존합니다. Agent와 UI는 저장소에 직접 접속하지 않고 BoI API/MCP가 제공하는 ACL URL, summary, profile, sample, checksum만 사용합니다. PostgreSQL은 검색 read model 또는 별도 Legacy DB Demo이며 자료 원본 정본이 아닙니다.

```bash
BOI_COMPOSE_PROFILE=local-full-datalake \
BOI_ENV_FILE=.env.local-full.example \
BOI_ENV_OVERLAY_FILE=.env:.env.local-full-datalake.example \
./scripts/start_local_full.sh

python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --import-data-context --artifact-smoke
```

PostgreSQL structured query 예시는 Legacy DB Demo profile에서만 켭니다.

```bash
BOI_COMPOSE_PROFILE=local-full-legacy-db-demo \
BOI_ENV_FILE=.env.local-full.example \
BOI_ENV_OVERLAY_FILE=.env:.env.local-full-datalake.example:.env.local-full-legacy-db-demo.example \
./scripts/start_local_full.sh

python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --legacy-db-demo-smoke
```

특수한 문서 전용 복구 환경에서만 `BOI_DATALAKE_MODE=disabled`를 명시할 수 있습니다. 이 경우 자료 업로드는 사용할 수 없지만 기존 OKF 문서와 정본 검색은 계속 읽을 수 있어야 합니다.

```bash
python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --allow-disabled
```

사내 Pilot 템플릿:

```bash
cp .env.pilot-external.example .env
BOI_ENV_FILE=.env BOI_COMPOSE_PROFILE=pilot-external ./scripts/start_local_full.sh
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
BOI_CONTENT_ROOT=/content/data/boi
BOI_CONTENT_SAFE_DIRECTORY=/content
BOI_API_RUN_AS=1000:1000  # /srv/boi-wiki/content 소유 서비스 계정의 실제 UID:GID로 변경
BOI_RUNTIME_ROOT=/runtime
BOI_RUNTIME_HISTORY_SEED_ROOT=/content/data
```

`pilot-external`에서 `/srv/boi-wiki/content`는 반드시 이 repo의 git checkout root여야 합니다. 문서 정본은 host의 `/srv/boi-wiki/content/data/boi`, 컨테이너의 `/content/data/boi`입니다. `BOI_API_RUN_AS`는 checkout을 소유한 서비스 계정의 숫자 UID:GID와 같아야 합니다. 새 실행 로그는 `/runtime` 아래에 쓰고, repo에 포함된 기존 demo/history 로그는 `/content/data`를 seed로 읽습니다. `/api/runtime/config`의 `content.markdown_documents`, `content.expected_guide_exists`, `boi_inbox_reports.generation_ready`, `runtime_history`, `readiness.ok`, Git sync status, persisted search index 상태, build revision을 확인합니다.

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

BoI Agent v2는 Web Pet, REST, MCP, Codex/Claude Agent Kit이 같은 Context, Harness, WorkRun과 권한 정책을 사용합니다. Pet이 기본 사용자 경험이며 `/agent`는 별도 제품이 아니라 같은 Pet surface를 넓게 여는 주소입니다. 2026-07-11에 브라우저 연속성, Task 학습 순환, 검색 품질과 REST/MCP/Agent Kit parity acceptance를 통과해 모든 설치 예시의 `BOI_AGENT_V2_DEFAULT`를 `true`로 전환했습니다. 동결된 v1 Pet은 2026-07-25까지 `BOI_AGENT_V2_DEFAULT=false`로만 rollback할 수 있으며 새 기능을 추가하지 않습니다. 기존 Builder URL은 v2로 이동하고 MCP는 v2의 10개 도구만 노출합니다.

- Web BoI Agent: http://localhost:28000/agent
- 나만의 BoI Agent 만들기: http://localhost:28000/helpers/new
- PAT 발급 및 Agent Kit 안내: http://localhost:28000/agent/access
- Agent v2 readiness: http://localhost:28000/api/v2/system/readiness
- MCP 상태 페이지: http://localhost:8200/
- MCP v2 endpoint: http://localhost:8200/mcp/v2

검색은 Dictionary/온톨로지 확장, 실제 embedding, 그래프·권위·최신성·Task 맥락 rerank 순으로 수행합니다. 문서는 heading과 원문 line 범위를 가진 800~1,200자 chunk와 120자 overlap으로 색인하며, 답변 citation은 실제로 회수된 chunk만 가리킵니다. Markdown/JSONL/catalog가 정본이고 Postgres/pgvector와 ontology node/edge table은 언제든 재생성 가능한 read model입니다. embedding 장애 시 lexical/ontology 검색과 현재 업무는 유지되지만 semantic 검색이 성공한 것처럼 표시되지는 않습니다. `history_seed`는 유사 사례에서만 사용하며 현재 Inbox나 내 할 일에는 포함하지 않습니다.

지식 Source는 OKF Markdown, Git 변경 이력, 자료 보관함을 기본 adapter로 사용합니다. Graphify·codegraph는 운영 필수 의존성이 아니며 동일 corpus 비교 검증 뒤 source별로만 활성화합니다. 모든 관계에는 선언·추출·추론 여부, 근거, extractor version과 source revision을 남깁니다. 야간 Knowledge Health는 오래된 판단, 모순, 중복, 끊어진 링크와 연결 공백을 diff 후보로 만들지만 Team/Public 정본을 자동으로 다시 쓰지 않습니다.

Inbox 검토 보고서는 페이지 방문이나 수동 버튼에 의존하지 않습니다. `InboxReportCoordinator`가 새 업무와 기존 Active/Seed 이력을 낮은 동시성으로 순차 보완하고, Private BoI 저장이 끝나면 검색 동기화기가 변경된 문서와 chunk·ontology를 자동 반영합니다. 정본과 검색 read model 사이에 차이가 생겨도 일반 화면에는 기술적인 index 경고를 노출하지 않으며, lexical/ontology 검색을 유지한 채 백그라운드에서 복구합니다. 운영 상태는 `/api/runtime/config`와 `/api/v2/system/readiness`에서 확인합니다.

사용자는 capability를 고르지 않고 Pet 입력창에 자연어로 요청합니다. LangGraph Quick Agent가 매 turn의 대화, 현재 페이지, Source Set과 활성 artifact를 바탕으로 검색·현재 업무·Task 수행·유사 사례·private 초안·DeepAgents 경로를 자동 결정합니다. 자유 질문이 모호하면 읽기 전용 `knowledge.search`로 안전하게 라우팅하며, draft는 높은 확신의 작성 요청에서만 생성합니다. 명시 capability는 결정적인 외부 자동화에서만 사용합니다. 기본 capability는 다음 10개입니다.

`knowledge.search`, `work.inbox`, `task.work`, `cases.similar`, `business_event.plan`, `sop.plan`, `action.plan`, `skill.plan`, `knowledge.draft`, `deep.research`

초안은 모두 private/provisional artifact와 Evidence Ledger를 남깁니다. DeepAgents worker는 읽기 전용 BoI 검색만 사용하고 Postgres queue/checkpoint, retry, cancel, timeout, no-progress 제한을 적용합니다. 결과는 항상 draft이며 실제 게시·Action 실행·외부 부작용은 기존 preview/confirmation과 RBAC를 다시 통과해야 합니다. Task mode는 서버가 결정하며 Manual은 검색·제안, Copilot은 private draft, Autopilot은 allowlist 저위험 작업까지만 허용합니다.

Web 대화와 초안은 `WorkSession`으로 함께 저장됩니다. 기본 private session은 30일 보관되며 고정한 session과 정식 초안은 사용자가 삭제할 때까지 유지됩니다. 각 session은 자동 선택·고정·제외·직접 연결 source를 가진 `Source Set`과 GoalPlan을 보존합니다. Pet은 compact/expanded/fullpage에서 같은 renderer와 store를 사용하고, citation 원문·관련 질문·private 노트·artifact·scroll 위치를 이어갑니다. Agent의 인라인 Task 편집과 `/sops/new` 전체 편집은 동일한 SOP artifact revision을 사용합니다. 서로 다른 Task 수정은 병합되고 같은 필드의 동시 수정만 비교 가능한 409 충돌로 반환됩니다. 업무 도우미 Builder는 구조화된 지침, source scope, Skill, connector, surface를 저장하고 오른쪽 preview에서 실제 Agent 응답을 시험합니다. 기존 v1 agent draft는 `legacy_draft_id`로 최초 한 번만 read-only import됩니다.

모든 turn은 `WorkIntent → WorkContextPack → WorkRun → Harness → LoopDelta` 계약을 사용합니다. `WorkIntent.operation_plan`은 한 요청의 확인·생성·검증·실행·자산화 순서를 보존하고, `ContextManifest`는 현재 화면 anchor, 선택·제외 source와 이유, revision, provenance, 원본 격리 정책을 기록합니다. 현재 화면은 검색 범위 제한이 아니라 업무 해석 anchor이며 검색은 접근 가능한 Wiki 전체를 계속 사용합니다.

`WorkRun`은 최대 5회 iteration, no-progress 1회, tool loop 5회의 제한을 가집니다. 매 진행에는 새 근거, Action 결과, 사람 입력, artifact, 상태 변화, blocker 또는 지식 후보 중 하나가 필요합니다. 완료는 모델 문장이 아니라 Task의 완료된 모습, 확인할 자료, Evidence Ledger와 Manual/Copilot/Autopilot 정책으로 판정합니다. `GET /api/v2/work-runs/{id}`는 해당 실행의 검증된 Evidence Ledger를 함께 반환합니다.

자연어의 업무 의미와 수행 경로는 LLM structured planner가 판단하며 문구 목록이나 정규식으로 capability를 고르지 않습니다. 그 판단 이후의 실행 한도와 권한은 `LoopPolicy`와 Harness가 결정적으로 강제합니다. 루프는 `turn`, `goal`, `time`, `proactive`를 구분하고 각각 사용자/API/Event/Schedule/Interval trigger, Task stop, routine stop을 별도로 기록합니다. 시간·이벤트 기반 업무는 `/api/v2/work-routines`에서 만들고 trigger/cancel할 수 있으며 worker가 due routine을 같은 `WorkRun`으로 실행합니다. 같은 source fingerprint는 실행 전에 억제하고 같은 결과가 반복되면 다음 확인 간격을 최대 8배까지 늘립니다.

초안과 Deep Work 결과는 작성 대화를 받지 않는 fresh-context 독립 검토를 한 번 더 거칩니다. 이 검토는 보완점을 찾는 품질 신호일 뿐 Autopilot 완료, 코드 Harness, RBAC, 사람 확인을 대신하지 않습니다. 일반 turn과 Deep Work는 각각 token budget을 가지며 model/embedding/tool 사용량은 run과 연결된 usage ledger에 남습니다. 일반 turn은 32K 누적 예산을 유지하고, Deep Work는 pilot mode에서 최대 5회 도구 호출, 40K 입력 context와 160K 실행 누적 예산을 사용합니다. `BOI_DEEPAGENTS_MAX_INPUT_TOKENS`는 모델의 실제 context에서 출력 여유를 뺀 값으로 배포별 조정할 수 있습니다. 이 구분은 Anthropic의 [Getting started with loops](https://claude.com/blog/getting-started-with-loops)의 turn/goal/time/proactive loop, verifiable exit criteria, independent review, pilot-first 및 usage visibility 원칙을 BoI Task 계약에 맞게 적용한 것입니다.

일반 로컬·사외 실행은 LM Studio/OpenAI-compatible generation과 로컬 embedding을 기본으로 사용합니다. `OPENAI_API_KEY`가 있어도 GPT-5.5로 자동 승격하지 않으며, Pet·Quick Agent·DeepAgents는 같은 로컬 model route를 사용합니다. GPT-5.5는 비용·품질 비교용 일회성 검증에서만 `BOI_GPT55_TEST_MODE=true`와 별도 test credential을 명시해 허용하고, 상시 서비스 환경에는 이 값을 켜지 않습니다. LM Studio 모델이 지원하면 `BOI_V2_REASONING_EFFORT=none`으로 structured output에 불필요한 숨은 reasoning을 없애며, 지원하지 않는 gateway는 이 값을 비워 provider 기본값을 사용합니다. 개발 PC에서 `BOI_LMSTUDIO_REQUIRE_PRELOADED_MODELS=true`를 켜면 앱은 native `GET /api/v1/models`로 생성 모델과 embedding 모델의 TTL 없는 수동 상주 상태만 확인하고 load/unload API는 호출하지 않습니다. 필수 모델이 수동 상주 중이면 LM Studio의 JIT 설정은 다른 client를 위해 켜 두어도 BoI 요청을 허용하며, 필수 모델이 없거나 TTL 인스턴스만 있으면 자동 재로딩 대신 요청을 차단합니다. 이 가드는 현재 PC처럼 모델 교대 로딩을 피해야 하는 개발 환경에서만 선택적으로 켜고, 사내 관리형 OpenAI-compatible 서버에서는 끕니다. embedding 차원이 바뀌면 재생성 가능한 pgvector 검색 테이블만 비우고 다시 색인하며 Markdown/JSONL 정본과 업무 실행 기록은 건드리지 않습니다.

완료된 업무에서 재사용 가치가 확인되면 private `KnowledgeCandidate`를 만들 수 있습니다. 후보는 출처, 중복 판단과 대상 자산을 가지며 다음 검색에서 provisional 지식으로 재사용됩니다. 같은 Manual Task가 검증된 완료 기록으로 3회 반복되면 Skill/Action 후보를, 같은 Task blocker가 2회 반복되면 SOP/Harness 개선 후보를 만들되 대화 횟수만으로는 후보를 만들지 않습니다. 대화·로그 원문이나 출처 없는 요약은 Learning Harness가 차단합니다. Team/Public 반영은 candidate promotion 요청 이후에도 기존 preview, RBAC, Harness와 별도 확인을 다시 거칩니다.

MCP v2는 progressive discovery를 위해 10개 도구만 공개합니다.

`boi_bootstrap`, `boi_agent`, `boi_search`, `boi_get`, `boi_my_work`, `boi_context`, `boi_plan`, `boi_confirm`, `boi_job_status`, `boi_tools_search`

외부 client는 Web SSO로 로그인한 뒤 `/agent/access`에서 PAT를 발급합니다. PAT는 한 번만 표시되고 hash만 저장되며 기본 30일, 최대 90일입니다. query의 `employee_id`는 신뢰하지 않으며 PAT identity, 현재 RBAC, 발급 당시 권한, Task mode의 교집합만 허용합니다. MCP `boi_agent`도 기본적으로 `capability_id`를 보내지 않으며, 후속 요청에는 응답의 `work_session_id`를 보내 Web Pet과 같은 source, citation, GoalPlan과 artifact를 이어갑니다. Codex/Claude/Python/TypeScript 설정은 `agent_kit/`과 `scripts/install_boi_agent_kit.sh`를 사용합니다. PAT를 설정 파일이나 저장소에 기록하지 마세요.

주요 REST 계약은 `/api/v2/bootstrap`, `/api/v2/agent/turns`, `/api/v2/work-sessions`, `/api/v2/work-sessions/{id}/sources`, `/api/v2/work-runs`, `/api/v2/work-routines`, `/api/v2/citations/{id}`, `/api/v2/goal-plans/{id}`, `/api/v2/notes/from-turn`, `/api/v2/artifacts/{id}/sop`, `/api/v2/helper-drafts`, `/api/v2/search`, `/api/v2/capabilities`, `/api/v2/deep-jobs`, `/api/v2/evaluations/{id}`, `/api/v2/usage/{id}`, `/api/v2/system/readiness`입니다. 기본 응답은 8KB 이하이며 전체 context/tool trace는 진단 권한 없이 반환하지 않습니다.

Public dictionary는 BoI Agent가 반도체/품질/설비/패키징 용어를 이해하기 위한 기본 seed vocabulary입니다. 예를 들어 `단면검사`, `Cpk`, `시계열 예측`, `HBM`, `하이브리드 본딩` 같은 현장 표현은 먼저 dictionary로 해석되고, 필요한 경우 SOP/Event/Action 후보로 확장됩니다. Agent나 MCP client를 만들 때는 단순 문서 목록이 필요하면 `boi_search`, 업무 맥락 탐색이나 질문 의도 해석이 필요하면 `ontology_search`를 우선 사용합니다. 개인 dictionary는 본인 private scope에 바로 추가할 수 있지만, team/public dictionary는 shared ontology에 영향을 주므로 `boi.editor` 권한과 팀 멤버십 정책을 통과해야 합니다.

아래 Wiki 문서는 동결된 v1 운영 계약의 감사·마이그레이션 참고 자료입니다. v2의 실행 계약은 `boi_api/app/v2`, `data/agent_catalog/capabilities-v2.yaml`, `agent_kit/`을 기준으로 합니다.

- Native Agent Architecture: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:native-boi-agent-architecture?employee_id=100001
- Native Agent Tool Loop: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:native-boi-agent-tool-loop?employee_id=100001
- Agent Guardrail and ACL: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:agent-guardrail-and-acl?employee_id=100001
- Pet Agent UX and Artifacts: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:pet-agent-ux-and-artifacts?employee_id=100001
- BoI Profile ACL Policy: http://localhost:28000/docs/boi:public:boi-wiki-manual:security:boi-profile-acl-policy?employee_id=100001
- Team RBAC Management: http://localhost:28000/docs/boi:public:boi-wiki-manual:security:team-rbac-management?employee_id=100001
- Ontology Retrieval and Search: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:ontology-retrieval-and-search?employee_id=100001
- Safety, Approval, and Memory: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:safety-approval-and-memory?employee_id=100001
- Deployment and Verification: http://localhost:28000/docs/boi:public:boi-wiki-manual:agent:deployment-and-verification?employee_id=100001

Langflow는 선택 가능한 외부 flow/Action connector입니다. Agent v2의 routing, 검색, 권한, 실행 runtime으로 사용하지 않습니다.

v2 배포 검증은 runtime readiness와 의미 기반 acceptance를 함께 봅니다.

```bash
python scripts/check_local_full_readiness.py --base-url http://localhost:28000
python scripts/check_agent_v2_search_quality.py --base-url http://localhost:28000
curl -s http://localhost:28000/api/v2/harness/acceptance | python -m json.tool
curl -s http://localhost:8200/status.json | python -m json.tool
```

검색 품질 검사는 curated 업무 질의에서 Recall@8 0.85 이상, reviewed 정본 Top-3 적중률 0.90 이상을 요구합니다. `full_accepted=true`가 되려면 Postgres/pgvector, 실제 generation/embedding model, 최신 search index, DeepAgents worker heartbeat, PAT secret, MCP v2 10-tool surface가 모두 준비되어야 합니다. 모델 장애 중에도 `core_accepted`와 검색·문서·현재 업무는 유지됩니다. MCP protocol 요청에는 `/agent/access`에서 발급한 `Authorization: Bearer boi_pat_...`가 필요합니다.

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

GPT-5.5 비교 검증은 일반 smoke와 CI에 포함하지 않습니다. 별도 검증 서버에
`BOI_GPT55_TEST_MODE=true`, `BOI_AGENT_USE_OPENAI_RUNTIME=true`, `BOI_GPT55_TEST_BASE_URL`,
`BOI_GPT55_TEST_MODEL`, `BOI_GPT55_TEST_API_KEY`를 별도로 명시한 뒤에만 다음처럼 실행합니다.

```bash
python scripts/check_agent_builder_mcp_bridge.py --gpt55-test --mcp-base-url http://localhost:8200 --employee-id 100001 --summary
python scripts/check_agent_sandbox.py --gpt55-test --base-url http://localhost:28000 --summary
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
- MCP/API의 `user_confirmed=true`는 사용자가 실행 의도를 확인했다는 guard입니다. high-risk Action Gateway 호출의 `approved_by`는 승인자 기록이며, `user_confirmed`가 `approved_by`를 대체하지 않습니다.
- Private BoI는 사번 단위로 scope가 제한됩니다.
- Team/Public promotion은 copy-not-move입니다.
- Team/Public promotion은 사용자 승인과 자동 검증 후 `review_status: user_confirmed`, `hotl.status: watching`으로 게시됩니다.
