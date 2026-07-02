---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Operations Center
description: 사번 기준으로 여러 SOP workstream, 검증 보고서, 판단 근거, 승인/반려/보류 업무를 한 화면에 모으는 운영 상황실 기준
tags: [Manual, OperationsCenter, SOP, Inbox, WorkContext]
timestamp: 2026-07-01T18:30:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:boi-operations-center
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
    ref: boi:public:boi-wiki-manual:agent:inbox-work-context-and-history
  - type: boi
    ref: boi:public:boi-wiki-manual:mcp:register-and-use-boi-wiki-mcp
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

BoI Operations Center는 BoI Agent 채팅창이 아니라 사번 기준 업무 상황실이다. 한 사람이 여러 SOP에 동시에 엮이는 것을 기본 전제로 두고, 여러 SOP가 현재 사용자에게 보내는 검증 보고서 BoI, 부족 근거, 승인 요청, 처리 지연을 한 화면에 모아 보여준다.

# Screen Model

기본 화면은 React Flow 기반 `Map`이다. SVG fallback은 두지 않는다. 중앙에는 현재 사용자 사번을 두고, 주변에는 담당, 승인, 참조로 연결된 SOP workstream, Agent, Evidence, Report, Decision node를 배치한다. 각 SOP 노드의 크기는 열린 업무 수, 색상은 가장 높은 위험 상태를 의미한다. `Queue`는 지금 먼저 봐야 할 업무를 우선순위로 정렬하고, `Table`은 같은 데이터를 운영자가 빠르게 필터링할 수 있게 보여준다.

SOP 노드를 선택하면 SOP Lens로 전환한다. 이 화면은 문서용 Mermaid가 아니라 런타임 graph payload를 사용한다. 현재 단계, 완료된 단계, 근거 부족 단계, 승인 대기 단계가 분리되어 보이고, stage를 선택하면 오른쪽 판단 패널의 업무 맥락이 해당 단계 기준으로 바뀐다.

# Runtime Contract

Operations Center는 Event/Action JSONL을 매번 전체 스캔하지 않는다. BoI API는 runtime manifest와 index를 바탕으로 다음 구조를 materialize한다.

- `EmployeeWorkItem`: 사번, SOP, run, stage, priority, report state, decision state
- `SopRunState`: SOP 실행 인스턴스, 현재 단계, stage 상태, evidence state, business context
- `EvidencePacket`: 판단 근거의 종류, 확보 상태, BoI 문서 링크, Data Lake artifact 링크, 부족 사유

`/api/ops/overview`는 첫 렌더에 필요한 manifest만 반환한다. 상세한 판단 보고서는 BoI Inbox report BoI와 `/api/sop-runs/{run_id}/context`에서 조회한다.

# Agent Runtime And Sandbox

Operations Center의 첫 렌더, Inbox 목록, SOP/Event/Action catalog는 LLM이나 sandbox를 기다리지 않는다. 이 경로는 runtime manifest/index만 사용한다.

고급 실행 경로는 `gpt-5.5`와 OpenAI Agents SDK를 사용한다.

- Agent Builder draft test
- Evidence Sandbox 실행 결과 요약
- Data Lake/MCP multi-tool 탐색
- Inbox 검증 보고서 BoI 생성
- 복잡한 SOP/Event/Action 연결 제안

BoI API는 Agents SDK를 optional runtime adapter로 사용한다. SDK가 없거나 OpenAI 상태가 degraded여도 core UI는 200을 반환하고, `/api/runtime/config`와 `/api/runtime/openai-health`에 degraded 상태만 남긴다.

Evidence Sandbox는 업무 판단 근거를 만들 수 있는 계산 workspace다. 단, 근거로 채택하려면 다음 조건을 만족해야 한다.

- source refs
- 실행 code/script
- runtime execution record
- output artifact: JSON/CSV 같은 계산 결과와 함께 chart/table/report HTML 또는 Markdown을 포함할 수 있어야 함
- validation result
- ACL/RBAC 통과
- 사용자 확인

local-full 기본 sandbox backend는 Agents SDK의 `unix_local` client다. 운영용 강한 격리가 필요하면 같은 API contract를 유지한 채 Docker, OpenAI Sandbox Agent, Vercel Sandbox 같은 provider backend로 교체한다. Sandbox artifact는 BoI 본문에 raw data를 넣지 않고 artifact URL과 report attachment로 연결한다.

# SOP Scope

Operations Center와 BoI Agent는 같은 SOP resolver를 사용한다.

| Scope | 의미 |
|---|---|
| `catalog_all` | 전체 SOP 카탈로그 목록 |
| `catalog_search` | 사용자가 준 조건과 일치하는 SOP 목록 |
| `current_page_related` | 현재 보고서, SOP, Event, Action에 직접 연결된 SOP |

사용자가 “SOP 리스트 전부 보여줘”라고 하면 현재 문서와 연결된 1건이 아니라 `catalog_all`을 반환한다. 반대로 “이 보고서 관련 SOP”는 현재 보고서와 직접 연결된 SOP만 반환한다. 이 구분은 Agent 답변, MCP `sop_catalog_search`, `/api/sops`, `/ops` workstream 선택 모두에서 유지한다.

# API And MCP

Operations Center API는 다음 경로를 기준으로 한다.

- `GET /api/ops/overview`
- `GET /api/ops/canvas`
- `GET /api/ops/nodes/{node_id}`
- `GET /api/ops/edges/{edge_id}`
- `GET /api/ops/recent-events`
- `GET /api/ops/stream`
- `GET /api/sop-runs`
- `GET /api/sop-runs/{run_id}`
- `GET /api/sop-runs/{run_id}/graph`
- `GET /api/sop-runs/{run_id}/context`

Agent/Sandbox API는 다음 경로를 기준으로 한다.

- `POST /api/agents/drafts`
- `POST /api/agents/drafts/{draft_id}/test`
- `POST /api/agents/drafts/{draft_id}/publish`
- `POST /api/agents/sandbox/jobs`
- `GET /api/agents/sandbox/jobs/{job_id}`
- `GET /api/agents/sandbox/jobs/{job_id}/events`
- `GET /api/agents/sandbox/jobs/{job_id}/artifacts/{artifact_path}`
- `POST /api/agents/sandbox/jobs/{job_id}/adopt-evidence`
- `POST /api/inbox/reports/{report_id}/attach-evidence`

MCP client는 같은 기능을 `boi_ops_overview`, `boi_ops_canvas`, `boi_ops_recent_events`, `sop_catalog_search`, `sop_run_get`, `sop_run_graph`, `sop_run_context`, `agent_draft_create`, `agent_draft_test`, `agent_sandbox_job_create`, `agent_sandbox_job_get`, `agent_sandbox_adopt_evidence`로 사용한다. 판단 결과 기록은 기존 BoI Inbox decision API를 재사용하고, 승인/반려/보류/추가 근거 요청은 사유와 사용자 확인 없이는 기록하지 않는다.

# Verification Harness

Operations Center와 Agent Builder는 API contract만으로 완료 판단하지 않는다. local-full 검증은 최소한 다음 흐름을 포함한다.

- `python scripts/check_agent_sandbox.py --base-url http://localhost:28000 --employee-id 100001 --strict-openai --summary`
- `python scripts/check_agent_builder_mcp_bridge.py --mcp-base-url http://localhost:8200 --employee-id 100001 --summary`
- `node scripts/check_agent_builder_ui.mjs --url http://localhost:28000/agents/builder?employee_id=100001 --strict`
- `python scripts/check_boi_operations_center.py --base-url http://localhost:28000 --employee-id 100001 --summary`
- `node scripts/check_boi_inbox_ui.mjs --url http://localhost:28000/ops?employee_id=100001 --strict`

`check_agent_builder_ui.mjs`는 실제 브라우저에서 Agent Builder를 열고 `초안 만들기`, `바로 테스트`, `Sandbox 테스트`를 클릭한다. 통과 조건은 `gpt-5.5` Agents SDK 테스트 결과, Sandbox artifact, console health, publish/test button state가 모두 확인되는 것이다. 이 검증은 Builder API가 살아 있어도 사용자 화면에서 버튼 흐름이 끊기는 경우를 잡기 위한 필수 UI smoke다.

`check_agent_sandbox.py`는 단일 smoke가 아니라 압력 raw data, LOT yield, 부족 raw gate 같은 복수 시나리오를 실행한다. 각 시나리오는 code/script, JSON/CSV 결과, 보고서 Markdown, 필요한 경우 HTML chart/table artifact를 생성하고, `gpt-5.5` summary가 ready 상태인지 확인한 뒤 `verified_evidence`로 채택한다. 이 검증이 통과해야 Sandbox가 단순 mock이 아니라 실제 업무 판단에 채택 가능한 계산 근거를 만들 수 있다고 본다.

# Citations

- [Inbox Work Context and Historical Patterns](/public/boi-wiki-manual/agent/inbox-work-context-and-history.md)
- [Register and Use BoI Wiki MCP](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
