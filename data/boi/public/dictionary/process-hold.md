---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Process Hold
description: 품질/공정 리스크가 확인될 때 lot 또는 공정 진행을 일시 중지하는 고위험 조치
tags: [Dictionary, ProcessControl, Approval]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:process-hold
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Process Hold
definition: 품질 또는 공정 리스크 때문에 진행을 임시 중단하는 고위험 조치. BoI Wiki에서는 승인 전 자동 실행하지 않고 approval_required/manual approval로 기록한다.
aliases: [공정 Hold, 공정 진행 금지, hold, lot hold, 진행 금지]
domain: process-control
examples:
  - 공정 진행 금지는 Action Gateway와 manual approval을 모두 통과해야 한다.
links:
  - /public/actions/api/block-process-progress.md
  - /public/actions/manual/approve-process-hold.md
related_terms: [Approval, Spec / Rule, Manual Handoff]
maps_to_action_key: sop.equipment.block_process_progress
maps_to_sop: boi:public:sop:equipment-abnormal-response
source_refs:
  - {type: internal-doc, ref: "/public/sop/equipment-abnormal-response.md"}
---

# Summary

Process Hold는 공정 진행 금지 또는 lot hold를 뜻한다. BoI Wiki에서 이 term은 고위험 action으로 분류되며, 자동 실행보다 승인 필요 상태를 남기는 것이 기본이다.

# BoI Usage

- [공정 진행 금지 요청](/public/actions/api/block-process-progress.md)
- [공정 진행 금지 승인](/public/actions/manual/approve-process-hold.md)

# Related Dictionary Terms

- [Approval](approval.md)
- [Spec / Rule](spec-rule.md)
- [Manual Handoff](manual-handoff.md)

# Citations

- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
