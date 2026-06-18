---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: SOP Workflow 작성과 Runtime 연결
description: 사용자 SOP 이미지/문서에서 BoI Wiki SOP, event type, action catalog, Langflow/MCP/API/manual 연결을 만드는 절차
tags: [Manual, SOP, Workflow, EventBroker, ActionGateway]
timestamp: 2026-06-18T15:20:00+09:00
boi_id: boi:public:boi-wiki-manual:sop-workflows:create-and-connect-sop
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
    ref: harness/sop-authoring-harness.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

사용자가 SOP 문서나 이미지를 주면 agent는 관련 BoI Wiki 문서를 먼저 검색하고, 업무 단계와 event/action/manual handoff를 추출해 OKF SOP package를 만든다.

# Package Output

- SOP BoI 문서 with `workflow.workflow_key` and `workflow.stages`
- Event Type docs
- API/Webhook/MCP/Langflow/Manual/Event Broker action spec docs
- `data/event_catalog/event_types.yaml` and `data/action_catalog/actions.yaml` draft patches
- OKF links, citations, media references

# Workflow Rule

각 stage는 `id`, `name`, `purpose`, `entry_event`, `event_types`, `next_stage`, `emits_event`, `source_systems`, `automated_actions`, `manual_actions`, `outputs`, `failure_modes`, `acceptance_criteria`를 가져야 한다.

# Validation

1. `python scripts/okf_lint.py --root data --include-logs --strict-media`
2. `pytest tests -q -s`
3. `python scripts/check_boi_wiki_mcp.py`
4. `python scripts/run_equipment_sop_poc.py`

# Citations

- [SOP Authoring Harness](/public/harness/sop-authoring-harness.md)
- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
