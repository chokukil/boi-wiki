---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: SOP Authoring Harness
description: 이미지, 문서, OCR 텍스트에서 BoI Wiki 표준 SOP package를 만드는 기준
tags: [Harness, SOP, EventBroker, BoIWiki, ActionGateway]
timestamp: 2026-06-18T00:47:00+09:00
boi_id: boi:public:harness:sop-authoring-harness
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

SOP Authoring Harness는 사용자가 업무 문서나 화면 캡처를 주고 SOP 생성을 요청할 때, 모든 agent가 같은 구조의 BoI Wiki SOP package를 만들도록 하는 기준이다.

# Required Package

- SOP Markdown document
- Event Type docs
- Automated Action draft package across API, Webhook, MCP, Langflow, Event Broker, and BoI Writer connectors
- Manual Action docs
- Catalog patch drafts
- Citations and OKF links
- `_media` assets, media manifest, and media reference docs when source images or screenshots are supplied

# Stage Contract

모든 stage는 `id`, `name`, `purpose`, `entry_event`, `next_stage`, `emits_event`, `source_systems`, `automated_actions`, `manual_actions`, `outputs`, `failure_modes`, `acceptance_criteria`를 가져야 한다.

# Agent Flow

1. [BoI Wiki MCP](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)로 기존 SOP, event type, action spec, manual을 검색한다.
2. source image 또는 문서에서 stage, trigger, evidence, automated action, manual handoff를 추출한다.
3. 기존 action spec을 우선 재사용하고, 없을 때만 새 action package draft를 만든다.
4. Langflow는 LLM/agent reasoning이 필요한 stage에만 사용한다.
5. Web/MCP 저장은 draft-only로 남기고, 검증 후 agent가 commit한다.

# Example

- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
- [Action Authoring Harness](/public/harness/action-authoring-harness.md)
- [OKF Media and Browser Screenshot Guide](/public/boi-wiki-manual/media/okf-media-and-screenshots.md)

# Citations

- [Harness Overview](/public/harness/overview.md)
