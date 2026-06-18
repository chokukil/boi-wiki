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
- Automated Action draft package
- Manual Action docs
- Catalog patch drafts
- Citations and OKF links

# Stage Contract

모든 stage는 `id`, `name`, `purpose`, `entry_event`, `next_stage`, `emits_event`, `source_systems`, `automated_actions`, `manual_actions`, `outputs`, `failure_modes`, `acceptance_criteria`를 가져야 한다.

# Example

- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
- [Action Authoring Harness](/public/harness/action-authoring-harness.md)

# Citations

- [Harness Overview](/public/harness/overview.md)
