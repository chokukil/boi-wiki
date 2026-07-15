---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Wiki 운영 Runbook
description: 설치 모드, content와 runtime, 연결 상태, Agent v2 readiness, 검색 동기화와 장애 진단 기준
tags: [Manual, Operations, Deployment, Readiness, DataLake, MCP]
timestamp: 2026-07-12T10:45:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:operator-runbook
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:boi-wiki-manual:guide:final-operator-guide
  - type: boi
    ref: boi:public:boi-wiki-manual:operations:integration-status
  - type: boi
    ref: boi:public:boi-wiki-manual:operations:task-ontology-a2ui-acceptance
implementation_refs:
  - type: repo
    ref: README.md
  - type: repo
    ref: scripts/start_dev_api.sh
  - type: repo
    ref: scripts/start_local_full.sh
  - type: repo
    ref: scripts/start_agent_v2_stack.sh
  - type: compose
    ref: docker-compose.yml
review:
  reviewer: platform-lead
  review_status: reviewed
---

# 운영 원칙

BoI Wiki 운영은 content 정본, 새 runtime, 과거 history seed와 재생성 가능한 Agent read model을 분리한다. 한 경로가 비어 있거나 잘못 마운트되어도 조용히 `문서 0건`으로 서비스하지 않고 readiness에서 원인을 표시한다.

# 설치 모드

| Mode | 목적 | 기본 구성 |
|---|---|---|
| Local dev | 개발 PC에서 빠른 확인 | API 8765, local Kafka, Kafka UI, bundled MinIO, MCP v2 |
| local-full | Docker 전체 기능 검증 | API, Agent Postgres/pgvector, worker, Kafka, MinIO, MCP, 선택형 Langflow |
| pilot-external | 사내 상시 서비스 연결 | 외부 Kafka·model·storage와 service account content checkout |
| recovery | 특수 문서 복구 | 명시적으로 선택 integration을 비활성화하고 정본 조회 유지 |

# 기본 시작

로컬 개발:

```bash
./scripts/start_dev_api.sh
```

Docker local-full:

```bash
cp .env.local-full.example .env
./scripts/start_local_full.sh
```

Agent v2 stack을 별도로 확인할 때:

```bash
./scripts/start_agent_v2_stack.sh
```

표시용 주소는 환경마다 다르므로 문서와 Action 예제에서는 `<BOI_BASE_URL>`, `<BOI_MCP_URL>`을 사용한다. 현재 기본 예시는 local dev `http://127.0.0.1:8765`, Docker Web `http://localhost:28000`, MCP `http://localhost:8200/mcp/v2`다.

# Content와 Runtime 경로

| 구분 | 역할 |
|---|---|
| `BOI_CONTENT_ROOT` | OKF Markdown 정본 |
| `BOI_RUNTIME_ROOT` | 새 실행 결과, coordinator와 transient 상태 |
| `BOI_RUNTIME_HISTORY_SEED_ROOT` | 기존 demo·과거 Event/Action 이력의 read-only 조회 |
| `DATA_ROOT` | 호환 경로. 새 설치는 content/runtime 의미를 명확히 분리한다. |

env가 없고 repo의 `data/boi`가 있으면 local dev는 이를 content root로 사용한다. env가 명시된 경우 값을 존중하지만 Markdown 문서 수가 기준보다 적으면 readiness를 실패시킨다.

pilot-external 표준은 host checkout root `/srv/boi-wiki/content`, container mount `/content`, content root `/content/data/boi`다.

# 자료 보관함

모든 표준 설치에서 `BOI_DATALAKE_MODE=bundled`를 기본으로 하고 MinIO를 함께 시작한다. 사내 저장소를 사용할 때만 `external`과 endpoint, credential을 지정한다. `disabled`는 특수 복구 환경에서만 명시한다.

자료 원본은 MinIO, 문서 정본은 Markdown/Git, Agent 검색 상태는 Postgres/pgvector에 둔다. 세 저장소의 역할을 섞지 않는다.

# 연결 상태

Advanced의 `연결 상태`와 `GET /api/integrations/status`가 다음 기능을 확인한다.

- 업무 이벤트 Kafka
- 자료 보관함
- Action Gateway
- MCP v2
- 선택형 Langflow
- Kafka 관리 화면

일반 화면은 `사용 가능`, `연결 확인 필요`만 표시한다. 선택 integration 장애를 BoI Wiki 전체 장애로 취급하지 않는다.

상태 화면은 각 integration을 요청 중에 직접 probe하지 않고 `IntegrationHealthRegistry`의 cached snapshot만 읽는다. 화면이 열린 동안 5초마다 갱신하며 `다시 확인`은 비동기 probe만 시작한다. 상세 의미는 [연결 상태 이해하기](/docs/boi:public:boi-wiki-manual:operations:integration-status)을 따른다.

Kafka UI와 broker 상태는 구분한다. Kafka 관리 화면은 UI health가 정상일 때만 Advanced에 표시하며, UI가 내려가도 broker topic metadata가 정상이면 Event 처리 장애로 판정하지 않는다.

업무 흐름과 관계 그림에 사용하는 Mermaid runtime은 BoI Wiki 정적 자산으로 함께 배포한다. 사내망이나 외부 CDN이 막힌 환경에서도 같은 SVG가 렌더링되어야 하며, 운영 smoke는 외부 Mermaid 요청이 0건인지 함께 확인한다.

runtime은 versioned module chunk로 배포한다. cold cache, 느린 chunk, 최초 load 실패, 문법 오류와 새로고침 복원을 각각 확인하며, 일반 사용자 화면에 raw Mermaid source가 남으면 실패로 판정한다. transient load는 두 번까지 자동 재시도하고 문법 오류는 읽을 수 있는 관계 목록으로 복구한다.

![Data Lake Kafka Action Gateway MCP와 지식 동기화를 확인하는 연결 상태 화면](../_media/browser/current-guide/20260713-integration-status-1440x1000.png)

# Agent v2 Readiness

```bash
export BOI_BASE_URL='<BOI_BASE_URL>'
curl -s "$BOI_BASE_URL/api/v2/system/readiness" | python -m json.tool
```

필수 항목:

- content 문서가 존재한다.
- Agent Postgres와 pgvector가 준비됐다.
- generation과 embedding model을 호출할 수 있다.
- search index source signature가 최신이다.
- Deep Worker heartbeat가 최신이다.
- PAT secret과 MCP v2 10-tool surface가 준비됐다.

모델 장애 중에도 문서, lexical/ontology 검색과 현재 업무는 유지한다. draft와 Deep Work만 unavailable로 표시한다.

# LM Studio 정책

개발 PC에서는 `google/gemma-4-26b-a4b-qat`와 `text-embedding-bge-m3`처럼 사용자가 이미 띄운 generation/embedding model을 동시에 유지한다. 앱은 LM Studio load/unload API를 호출하지 않는다.

`BOI_LMSTUDIO_REQUIRE_PRELOADED_MODELS=true`는 native `GET /api/v1/models`로 수동 상주 상태만 확인한다. 필수 모델이 없으면 자동 load 대신 요청을 차단한다. 이 guard는 개발 PC용이며 사내 관리형 OpenAI-compatible 서버에는 강제하지 않는다.

GPT-5.5는 `BOI_GPT55_TEST_MODE=true`와 별도 test credential을 함께 지정한 비교 검증에서만 사용한다.

# Inbox 보고서 Coordinator

`/api/runtime/config`의 `boi_inbox_reports`에서 queued, running, retrying, ready, last scan과 storage readiness를 확인한다. Private report root가 쓰기 불가하면 보고서 생성은 구조화된 503으로 실패하고 앱 시작 preflight가 문제 경로와 복구 방법을 보여준다.

일반 기본값은 scan 30초, batch 8, 동시 생성 1건이다. active, seed와 과거 이력의 누락 보고서를 결정적인 report ID로 backfill한다.

# 검색 동기화

문서, 보고서와 SOP 저장 성공 후 KnowledgeChangeEvent를 발행한다. 검색 조정기는 변경 source를 batch로 embedding, chunk와 ontology에 반영한다. 저장 성공은 색인 실패로 취소하지 않는다.

`/api/v2/system/readiness`에서 다음을 확인한다.

- `search.index.sync_state`
- `pending_changes`
- `current_source_signature`
- `target_source_signature`
- `last_sync_success_at`

모델이나 schema 변경이 아니면 전체 reindex보다 증분 sync를 우선한다.

# MCP v2

Advanced의 MCP 화면에서 contract `2.0`, `/mcp/v2`, 핵심 도구 10개와 최근 확인을 점검한다. 개인 PAT 발급과 Codex·Claude 설정은 운영 화면이 아니라 BoI Agent의 `외부에서 사용`에서 제공한다.

# API v2

외부 공개 계약은 `/openapi-v2.json`과 `/api/reference`를 사용한다. Knowledge, Work, SOP, Business Event, Action, Agent, Files, System 영역만 포함하며 internal·smoke·service-token API는 제외한다. 기존 `/openapi.json`과 `/docs`는 호환 진단용으로 유지하고 legacy operation은 deprecated로 표시한다.

# Event 이력 진단

일반 `/events`는 같은 trace를 한 업무 발생 건으로 묶는다. raw Event row와 JSON이 필요할 때만 권한 있는 운영자가 Advanced의 `Event 기술 로그` 또는 `/events?view=raw`를 사용한다. 사용자 화면의 업무 상태와 raw dispatch 수가 다르면 occurrence projector와 trace 연결을 먼저 확인한다.

MCP status page는 `<BOI_MCP_STATUS_URL>`, endpoint는 `<BOI_MCP_URL>/mcp/v2` 형태로 문서화한다. 실제 client는 Web에서 발급한 PAT를 Bearer token으로 사용한다. v2는 10개 기본 tool만 노출하며 세부 기능은 `boi_tools_search`로 찾는다.

# 검증 명령

```bash
python scripts/okf_lint.py --root data --strict-media --strict-links
python scripts/check_local_full_readiness.py --base-url "$BOI_BASE_URL"
python scripts/check_agent_v2_search_quality.py --base-url "$BOI_BASE_URL"
python scripts/check_agent_v2_interface_parity.py --base-url "$BOI_BASE_URL"
BOI_BASE_URL="$BOI_BASE_URL" node scripts/check_manual_guides_ui.mjs
```

일반 탐색과 검증 중 LM Studio load/unload request는 0건이어야 한다.

Task·Ontology·동적 화면 acceptance:

```bash
python scripts/check_semantic_kernel_architecture.py
pytest -q tests/test_semantic_kernel_architecture.py
pytest -q tests/test_task_ontology_a2ui.py tests/test_agent_v2.py
python scripts/check_task_ontology_a2ui_acceptance.py --output .tmp/task-ontology-a2ui-acceptance.json
python scripts/evaluate_agent_v2_work_scenarios.py --output .tmp/agent-v2-work-scenarios.json
python scripts/evaluate_agent_v2_work_scenarios.py \
  --fixture tests/fixtures/semantic_kernel_holdout.yaml \
  --output .tmp/semantic-kernel-holdout.json
node scripts/check_task_ontology_a2ui_browser.mjs \
  --base-url="$BOI_BASE_URL" \
  --output=.tmp/task-ontology-a2ui-browser.json \
  --screenshot-dir=.tmp/task-ontology-a2ui-browser-shots
python scripts/check_openkb_release_gate.py \
  --output .tmp/openkb-release-gate.json
```

AST gate는 질문·goal·title·prompt 문자열이나 regex를 이용한 semantic routing, validator의 plan mutation과 capability fallback을 차단한다. `semantic_kernel_holdout.yaml`은 12개 의도군의 서로 다른 표현 60개, 멀티턴 12개와 adversarial 8개를 각각 세 번 실행해 capability·operation·effect·topic 계약을 직접 채점한다. 문장 token이나 한국어 접미사 규칙으로 의미를 다시 추정하지 않는다. 이어지는 명령은 결정적 계약, 실제 API 성능과 model residency, 기존 회귀, 실제 브라우저 journey와 선택 Adapter gate를 검증한다. 실패 사례를 별도 심사 대상으로 표시하더라도 이 플랫폼의 기본 acceptance에서는 GPT-5.5를 호출하지 않는다.

`planner_unavailable`, `planner_invalid`와 `planning_failed`는 정상적인 fail-closed 결과다. 운영자가 임의의 `safe_search`나 대체 capability를 추가해서는 안 된다. WorkRun 장애는 마지막 checkpoint의 raw state, 고정된 catalog·Harness revision, `ProgressDelta.error_disposition`과 idempotency key 순서로 확인한다.

semantic route schema나 Planner가 한 호출에서 반환하는 grounded answer·SOP outline 계약을 바꾸면 `SEMANTIC_ROUTE_CACHE_VERSION`도 함께 올린다. 이전 cache를 그대로 둔 채 warm 결과만 측정하지 않고, cache version을 무효화한 실행에서 grounded Agent p95 10초 기준을 다시 확인한다.

사실성 계약을 바꾸면 source scope와 topic state도 함께 점검한다. 일반 질문은 `canonical|operational`만 사용하고 validation·generated·navigation·deprecated는 제외한다. 응답의 `answerability`, `grounded_claims`, `used_source_refs`를 비교해 모든 supported claim에 ACL-visible source와 supporting chunk가 있는지 확인한다. source가 검색됐다는 사실만으로 grounded 처리해서는 안 된다.

멀티턴 장애는 WorkSession의 `topic_state`와 `topic_corrections`를 먼저 확인한다. 다음 turn에는 직전 supported claim과 실제 used source만 있어야 한다. 후속 resolved goal에서 이전 subject가 빠지면 Planner를 한 번 재판정하고, 다시 빠지면 답변을 중단한다. 명시적 새 주제에서는 이전 subject가 남지 않아야 하며 conflicting 답변은 correction audit과 함께 무효화돼야 한다.

내부에 근거가 없는 질문의 정상 결과는 `answerability.status=insufficient`와 `확인된 근거가 없습니다`다. 이를 모델 장애나 현재 화면 누락으로 바꿔 표시하지 않는다. GPT-5.5와 외부 검색은 기본·pilot acceptance에서 호출하지 않으며 LM Studio의 이미 로드된 모델에 load/unload 요청을 보내지 않는다.

외부 Adapter release gate는 core acceptance와 분리한다. 운영자가 승인한 격리 tool 버전과 실제 export를 사용하고 mock CLI 통과를 release 통과로 계산하지 않는다.

- Graphify: 실제 `graph.json`의 `links`, confidence tag, source location을 확인하고 import manifest의 node·edge 수와 rollback 제거 수가 일치해야 한다.
- OpenKB: 실제 `openkb add`가 하나 이상의 private candidate를 만들고 `index.md`, `log.md`, `AGENTS.md`를 제외해야 한다.
- CLI 종료 코드가 0이어도 validation result가 비어 있으면 job은 `failed/retryable`이어야 한다.
- 2026-07-13 기준 Graphify `0.9.13`은 실제 import·rollback을 통과했다. OpenKB `0.4.4`는 loopback compatibility gateway를 통해 실제 PDF에서 private 후보를 생성하고 `index.md`·`log.md` 제외를 통과했다. gateway는 `json_object` 요청을 이미 로드된 Gemma의 일반 JSON 요청으로만 변환하며 schema 실패 시 한 번만 복구한다.

브라우저 acceptance는 canvas 존재만 세지 않는다. Agent 질문 전송, 진행 상태, 자연어 Graph plan, node 선택, canonical 원문 이동, split·집중 보기, `Esc`, 새로고침 복원과 A2UI 표·Timeline·Mermaid·업무 양식을 실제로 조작한다. 기준 viewport는 `1440×1000`, `1180×850`, `949×1151`, `390×844`다.

업무 관계와 동적 화면 진단:

```bash
curl -sS -X POST "$BOI_BASE_URL/api/v2/knowledge-graph/query" \
  -H "Authorization: Bearer $BOI_PAT" \
  -H "Content-Type: application/json" \
  -d '{"focal_entities":["person:<employee>"],"query_kind":"responsibility","depth":2,"presentation":"table"}'
```

- Graph manifest의 compiler version, source signature와 runtime relation signature가 현재 값과 일치해야 한다.
- Task 배정·업무 기록·CompletionRecord 저장은 background knowledge sync를 깨운다. 관계 조회 요청은 마지막으로 검증된 graph를 즉시 사용하고 요청 안에서 runtime 전체를 다시 컴파일하지 않는다.
- `repeated_performer`는 `work_role_profiles`에서 최근 180일·서로 다른 검증 완료 3건 이상인지 확인한다.
- 일반 화면에서 동적 결과가 보이지 않으면 Advanced `연결 상태`의 `동적 결과 화면 진단`을 펼쳐 catalog, component와 fallback 상태를 확인한다. 별도 사용자 메뉴는 두지 않는다.
- Langflow는 Advanced의 고정 `Langflow` 링크로 새 탭에서 연다. 연결 실패는 링크를 숨기지 않고 `연결 상태`에서 해당 기능의 영향 범위로 진단한다.
- 이동되지 않는 repo/code ref는 업무 근거가 아니라 `implementation_refs`로 분리한다. 관리자만 읽기 전용 기술 근거 화면을 연다.
- 관계 조회·색인·일반 탐색은 LM Studio model load/unload API를 호출하지 않는다.

- [Task·Ontology·동적 화면 검증 기준](/docs/boi:public:boi-wiki-manual:operations:task-ontology-a2ui-acceptance)

# 장애별 확인

| 증상 | 먼저 볼 곳 |
|---|---|
| 문서가 0건 | content root, Markdown count, recovery candidates |
| Inbox·Event·Action 이력이 비어 보임 | active root와 history seed root의 row count |
| 보고서 생성 지연 | Private root writable, coordinator status, retrying count |
| 새 문서가 검색되지 않음 | pending change, source signature, last sync error |
| semantic 검색만 느림 | embedding endpoint와 pgvector index, lexical/ontology 유지 여부 |
| Event Stream이 비어 있음 | Kafka broker, topic, Event Router와 active/seed 구분 |
| Kafka UI만 열리지 않음 | broker와 별개인 optional 관리 UI health |
| Agent draft가 unavailable | model, worker, RBAC와 Harness blocker |
| MCP tool이 너무 많음 | 구형 `/mcp` 대신 `/mcp/v2` 연결 여부 |

# Harness 개선 운영

연결 상태의 관리자용 `업무 실행 품질 개선`은 반복 failure pattern, 검토할 candidate, 활성 Context Playbook과 NegativeResult 수를 보여준다. 일반 사용자의 업무 화면이나 검색 citation에는 이 운영 node를 노출하지 않는다.

```bash
curl -sS "$BOI_BASE_URL/api/v2/harness-failure-patterns" -H "Authorization: Bearer $BOI_PAT"
curl -sS "$BOI_BASE_URL/api/v2/negative-results" -H "Authorization: Bearer $BOI_PAT"
```

Harness 후보는 반드시 `shadow → evaluate → review` 순서로 처리한다. shadow run ID와 fixture revision이 일치하지 않으면 평가가 거부된다. review 승인은 자동 배포가 아니며 생성된 버전의 상태가 `approved_not_deployed`, `production_changed=false`인지 확인한다. 세부 기준은 [업무 실행 품질과 Harness 개선 운영 가이드](/docs/boi:public:boi-wiki-manual:operations:harness-observability-and-improvement)를 따른다.

# 관련 문서

- [BoI Wiki 종합 가이드](/docs/boi:public:boi-wiki-manual:guide:final-operator-guide)
- [BoI Wiki Architecture](/docs/boi:team:platform:boi-wiki-architecture-v0.1)
- [BoI Wiki MCP 등록과 사용](/docs/boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp)
- [자료 보관함과 업무 근거](/docs/boi:public:boi-wiki-manual:data-lake:data-lake-artifact-lifecycle)
- [배포와 검증](/docs/boi:public:boi-wiki-manual:agent:deployment-and-verification)
- [업무 실행 품질과 Harness 개선 운영 가이드](/docs/boi:public:boi-wiki-manual:operations:harness-observability-and-improvement)
