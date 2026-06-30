---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Action Authoring Harness
description: API, Webhook, MCP, Langflow, Manual, Event Broker, BoI Writer action을 같은 방식으로 정의하는 기준
tags: [Harness, ActionGateway, API, Webhook, MCP, Langflow, Manual]
timestamp: 2026-06-18T00:48:00+09:00
boi_id: boi:public:harness:action-authoring-harness
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
    ref: harness/action-authoring-harness.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Action Authoring Harness는 실행 가능한 action spec과 `data/action_catalog/actions.yaml` patch draft를 일관되게 만들기 위한 기준이다. Pilot 기준에서는 action spec에서 멈추지 않고 업무 목적, 필요한 업무 BoI, 기존 WorkflowDefinition 재사용 여부, Event Contract, Action/Event Skill 연결까지 함께 만든다. Langflow는 connector 중 하나이며 기본값이 아니다.

# Common Fields

`action_key`, `connector_kind`, `type`, `execution_mode`, `doc_ref`, `event_types`, `risk_level`, `approval_required`, `auto_dispatch`, `dry_run_default`, `owner`는 모든 action에 필요하다.

# Connector Requirements

Web UI에서는 `/sops/new?focus=action`의 Action 섹션에서 시작한다. 사용자는 먼저 자연어로 수행할 일을 설명하고, 기존 Action을 재사용할지 새 Action 초안을 만들지 선택한다. raw `execution_kind`를 자유 입력하지 않고, 7종 connector 중 하나를 고른 뒤 connector별 필수 설정을 `connector_config`로 남긴다. MCP에서는 `sop_registration_plan`으로 Event/SOP/Action 후보를 함께 확인하고, 필요하면 `action_draft_create(..., connector_kind=..., connector_config=..., user_confirmed=true)`가 같은 계약을 사용한다.

- API/Webhook: method, url, auth, headers, request_schema, response_schema, examples, curl, health_check
- MCP: mcp_server, tool_name, transport, input_schema, output_schema, example_tool_call
- Langflow: flow_name, endpoint_name, run_url, required_components, input_value_template, result_boi_policy
- Manual: assignee_role, checklist, completion_contract, approval_policy
- Event Broker: emits_event_type, event_body_template, trace_policy
- BoI Writer: materialization_policy, metadata_policy, enrichment_policy

# Safety Defaults

신규 action은 `enabled=false`, `auto_dispatch=false`, `dry_run_default=true`로 시작한다. 고위험 action은 `requires_manual_action` 없이는 활성화할 수 없다.

# Authoring Flow

1. 업무 목적과 이 action이 채워야 할 업무 BoI를 먼저 적는다.
2. Web UI에서는 `/sops/new?focus=action`의 `SOP 추가` 흐름으로 기존 SOP/Event/Action 후보를 먼저 확인한다. MCP/API에서는 [BoI Wiki MCP](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md) `workflow_definitions_search`와 `workflow_definition_deduplicate`를 내부 중복 확인 도구로 사용한다.
3. 사용자가 자연어로 “이런 Action이 필요하다”고 말하면 `sop_registration_plan(focus=action)`으로 기존 Event, SOP, Action 후보와 connector 추천을 함께 만든다.
4. `sop_registration_preview`로 Action 요청 권한, 승인 필요 여부, 연결 시스템 확인 상태를 보여준다.
5. 필요하면 `actions_search`로 기존 action을 찾고, 없을 때만 `/sops/new?focus=action` 또는 MCP `sop_registration_draft_create`/`action_draft_create`로 신규 action draft를 만든다.
6. 실제 업무에 가장 좁고 적합한 7종 connector 중 하나를 고른다: API, MCP, Webhook, Manual, Event Broker, BoI Writer, Langflow.
7. connector별 최소 설정을 채운다. 예: API는 `method`, `endpoint`; MCP는 `server`, `tool`; Manual은 `assignee_policy`, `completion_criteria`; Event Broker는 일반 화면에서는 기본 topic을 쓰고, 고급 설정에서만 topic을 직접 다룬다.
8. 사용자 화면에는 SOP/Event/Action 연결로 보여주고, 내부적으로는 WorkflowDefinition, Action Skill 또는 Event Skill 연결을 함께 만든다.
9. public action-spec BoI 문서와 catalog patch draft를 만든다.
10. connector별 테스트와 Event Broker publish smoke evidence를 남긴다.
11. 공개 문서와 log에 secret을 남기지 않는다.

# 내부 실행 정의

Action 등록은 단독 완료가 아니다. 사용자 화면에서는 관련 SOP, Event, Action 연결을 확인하고, API/MCP 내부에서는 다음 중 하나를 반드시 남긴다.

- 기존 Workflow 정의 재사용 근거
- 기존 Workflow 정의 확장 patch
- 신규 Workflow 정의 draft

BoI Agent는 업무 BoI, 내부 WorkflowDefinition, Event/Action Skill registry를 기준으로 답변, 추천 질문, 실행 카드, 후속 행동을 판단한다. 일반 사용자에게는 `업무 흐름 정의` 직접 링크를 보여주지 않고 `관련 SOP 보기`, `Event 보기`, `Action 보기`, `BoI Wiki에서 보기`로 연결한다.

# Example

- [Public Action Library](/public/actions/overview.md)
- [Multi-action Connector Guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)
- [Event-Native Workflow Guide](/public/boi-wiki-manual/workflows/event-native-workflow-guide.md)
- [Action/Event Skill Registry Guide](/public/boi-wiki-manual/workflows/action-event-skill-registry-guide.md)

# Citations

- [Harness Overview](/public/harness/overview.md)
