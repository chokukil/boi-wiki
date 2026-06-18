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

# Runtime Evidence

![Langflow Equipment Stage Analysis Flow](/public/boi-wiki-manual/_media/screenshots/langflow-equipment-stage-flow-20260618.png)

![Equipment Workflow Status](/public/boi-wiki-manual/_media/screenshots/workflow-status-equipment-anomaly-20260618.png)

# Validation

```bash
python scripts/setup_langflow_reference_flows.py --summary
python scripts/audit_langflow_flows.py --runtime
python scripts/run_equipment_sop_poc.py
```

SSO dev overlay에서는 BoI API 접근에 service token 또는 사용자 bearer token이 필요하다.

```bash
SERVICE_TOKEN=dev-service-token-change-me python scripts/run_equipment_sop_poc.py
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

- required BoI components are connected, not isolated.
- duplicate flow names are archived or ignored by deterministic selection.
- action log contains full Langflow result text.
- Workflow Status links from Langflow action to raw action detail.
- Smoke result contains BoI Write Result and manual_required.

# Notes

Langflow may show update-available badges for base UI components after an image upgrade. That is not a completion signal by itself. Completion is based on runtime audit, Action Gateway invocation, generated BoI write result, and SOP E2E smoke.

# Citations

- [Langflow Stage Analysis Action](/public/actions/langflow/stage-analysis.md)
- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
