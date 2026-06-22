---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Spec / Rule
description: 공정/품질 판정 기준과 자동화 rule 변경 대상
tags: [Dictionary, Quality, Approval]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:spec-rule
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Spec / Rule
definition: 공정, 품질, 검사, 자동화 판단 기준. 변경은 영향 범위와 승인 절차가 필요한 고위험 업무다.
aliases: [Spec, Rule, 스펙, 룰, 판정 기준, 관리 기준, spec change, rule change]
domain: process-quality
examples:
  - Spec/Rule 변경은 dry-run 또는 approval_required로 남기고 사람 승인 후 처리한다.
links:
  - /public/actions/api/change-spec-rule.md
  - /public/actions/manual/approve-spec-rule-change.md
related_terms: [SPC, Process Hold, Approval]
maps_to_action_key: sop.equipment.change_spec_rule
maps_to_sop: boi:public:sop:equipment-abnormal-response
source_refs:
  - {type: internal-doc, ref: "/public/sop/equipment-abnormal-response.md"}
---

# Summary

Spec / Rule은 공정과 품질 판단 기준이다. BoI Wiki에서는 변경 후보를 만들 수는 있지만, 실제 변경은 승인과 변경관리 절차를 요구한다.

# BoI Usage

- [Spec / Rule 변경 요청](/public/actions/api/change-spec-rule.md)
- [Spec / Rule 변경 승인](/public/actions/manual/approve-spec-rule-change.md)

# Related Dictionary Terms

- [SPC](spc.md)
- [Process Hold](process-hold.md)
- [Approval](approval.md)

# Citations

- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
