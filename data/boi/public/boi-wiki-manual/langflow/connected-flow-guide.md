---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Langflow Connected Flow Guide
description: BoI custom component를 실제 연결된 Langflow workflow로 구성하고 action/runtime과 검증하는 가이드
tags: [Manual, Langflow, BoIComponent, Workflow]
timestamp: 2026-06-18T15:15:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:connected-flow-guide
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
    ref: langflow/custom_components/boi
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Langflow flow는 canvas에 노드가 존재하는 것만으로 완료가 아니다. 입력, BoI context, harness/wiki reader, LLM, output 또는 writer/action invoker가 실제 edge로 연결되어 실행 결과가 action log에 남아야 한다.

# Required Patterns

| Flow type | Required connected path |
|---|---|
| Stage analysis | Chat/Event input -> BoIContextNormalizer -> BoIHarnessLoader/BoIWikiReader -> BoIPromptComposer -> Gemma LLM -> BoIWikiWriter/BoIActionInvoker -> BoIResultComposer -> ChatOutput |
| Writer reference | Input -> ContextNormalizer -> MetadataBuilder -> PolicyGuard -> WikiWriter -> ActionInvoker -> ResultComposer |
| BoI Agent | Chat Input -> native Agent -> BoI Agent Tools -> BoI Agent Result Composer -> Chat Output |
| Agentic simulator | Input -> ContextNormalizer -> BoIUniversalSimulatorAgent -> PolicyGuard -> BoIResultComposer -> ChatOutput |

# BoI Agent vs Pipeline Flow

`BoI Agent Flow`는 Web Pet Agent와 MCP `boi_agent_chat`의 trusted backend다. 사용자와 외부 agent는 Langflow URL을 직접 호출하지 않고 BoI API 또는 `boi-wiki-mcp`를 호출한다. Langflow canvas 안에서는 native Agent component가 Gemma model을 reasoning engine으로 쓰고, `BoI Agent Tools` custom component의 `ontology_search`, `boi_get`, `workflow_status`, `agent_inbox`, `manual_handoff_complete`, `memory_recall` tool을 반복 호출한다. recursion 방지를 위해 `boi_agent_chat` tool은 Agent toolset에 넣지 않는다.

# Pipeline vs Agentic Simulator

기존 connected flow는 BoI Wiki 문서를 한 번 읽고 LLM이 답을 만드는 단일 패스 pipeline이다. 이 구조는 연결 상태 검증에는 충분하지만, Universal Simulator의 두뇌 역할로는 부족하다.

Universal Simulator는 `BoI Universal Simulator Agent`를 중심으로 둔다. Agent는 Action Catalog, Event Type, SOP stage, 같은 trace의 event/action log, generated BoI, prior action result를 seed로 삼아 BoI Wiki tool loop를 여러 번 실행하고, coverage report와 retrieval trace를 만든다. LLM은 Agent 내부 reasoning engine일 뿐이며, 캔버스상 독립 LLM 출력 경로가 있으면 공식 simulator 예제로 보지 않는다. 따라서 공식 simulator 예제는 `BoI Universal Simulator Agent` 노드가 `BoI Result Composer`로 연결되어야 완료로 본다.

Action Gateway는 Universal Simulator flow를 먼저 호출하고, Langflow Agent가 실패하거나 timeout일 때만 `/api/simulations/universal-agent` deterministic fallback을 사용한다. Universal flow 안에 `manual.direct_development.decide_cross_section` 같은 stale hardcoded action key가 남아 있으면 runtime audit 실패로 본다.

# Runtime Evidence

아래 캡처는 인증된 Langflow 세션에서 `BoI Equipment Stage Analysis Flow`가 연결된 상태를 확인한 verified screenshot이다. Langflow flow id는 `scripts/setup_langflow_reference_flows.py --auth-mode api-key`를 다시 실행하면 재생성될 수 있다. 2026-06-20 재검증 기준 최신 stage-analysis flow id는 `36952047-2ec9-47a4-b106-2b54ce823849`이고, 완료 기준은 고정 id가 아니라 같은 flow name/action key가 runtime audit와 Action Gateway log에서 `langflow_invoked`로 확인되는 것이다.

![Langflow Equipment Stage Analysis Flow](/public/boi-wiki-manual/_media/browser/langflow-stage-analysis/20260619-150927-langflow-equipment-stage-analysis-connected-flow-current-1440x1000-01d4ad42f1d6.png)

Reference, Stage Analysis, Universal Simulator canvas의 최신 public gallery는 [Langflow Flow Gallery](/public/boi-wiki-manual/langflow/flow-gallery.md)에서 확인한다.

아래 Workflow Status 캡처는 `scripts/run_equipment_sop_poc.py`로 생성한 trace `trace-5557beb5527048bc86bc9c5e66c4a64f`의 실행 증거다. Event, Action, Langflow action, generated BoI, manual handoff가 같은 trace로 연결되어야 완료로 본다.

![Equipment Workflow Status](/public/boi-wiki-manual/_media/browser/workflow-status/20260619-152032-equipment-anomaly-workflow-status-current-1440x1000-399ae96b3b8d.png)

# Validation

```bash
python scripts/setup_langflow_reference_flows.py --summary
python scripts/audit_langflow_flows.py --runtime --auth-mode api-key --langflow-api-key "$LANGFLOW_API_KEY"
python scripts/run_equipment_sop_poc.py
```

SSO dev overlay에서는 BoI API 접근에 service token 또는 사용자 bearer token이 필요하다.

```bash
SERVICE_TOKEN="$SERVICE_TOKEN" python scripts/run_equipment_sop_poc.py
```

Langflow custom component도 같은 원칙을 따른다. runtime container에는 `BOI_API_SERVICE_TOKEN`을 넘겨 `BoIWikiReader`와 `BoIWikiWriter`가 SSO 모드에서도 BoI API를 호출하게 한다.

# SSO / Permission Setup

개발용 SSO overlay는 `langflow-hynix`의 Keycloak/HCP 변수명을 그대로 쓴다. Langflow 컨테이너가 실제로 읽는 값은 다음이다.

| Variable | Purpose |
| --- | --- |
| `KEYCLOAK_SERVER_URL` | container에서 Keycloak token/JWKS로 접근하는 내부 URL |
| `KEYCLOAK_EXTERNAL_SERVER_URL` | browser redirect에 쓰는 Keycloak URL |
| `KEYCLOAK_HCP_API_URL` | HCP project roles endpoint |
| `KEYCLOAK_ALLOWED_EMPLOYEE` | 개인별 Langflow instance 제한 |
| `KEYCLOAK_SHARED_USERNAME` | SSO 성공 사용자를 매핑할 Langflow shared user |

BoI Wiki는 같은 SSO realm을 쓰고, HCP role을 `boi.viewer`, `boi.editor`, `boi.workflow_runner`, `boi.action_invoker`, `boi.promoter`, `boi.admin`으로 변환해 문서 ACL과 workflow/action 권한을 검증한다.

# Completion Criteria

- required BoI components are connected, not isolated, and the runtime audit passes.
- Universal Simulator contains `BoI Universal Simulator Agent`, and its output is connected to `BoI Result Composer`.
- Universal Simulator has no standalone `Gemma LLM -> Output` path.
- duplicate flow names are archived or ignored by deterministic selection.
- action log contains full Langflow result text.
- action log contains retrieval rounds, used BoI docs, coverage score, and missing context for simulator actions.
- Workflow Status links from Langflow action to raw action detail.
- Smoke result contains BoI Write Result and manual_required.

# Notes

Langflow may show update-available badges for base UI components after an image upgrade. That is not a completion signal by itself. Completion is based on runtime audit, Action Gateway invocation, generated BoI write result, and SOP E2E smoke.

# Citations

- [Langflow Stage Analysis Action](/public/actions/langflow/stage-analysis.md)
- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
