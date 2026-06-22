---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Root Cause Analysis
description: 이상 현상의 직접/근본 원인 후보를 evidence 기반으로 좁혀가는 분석 활동
tags:
- Dictionary
- Semiconductor
- workflow
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:root-cause-analysis
visibility: public
classification: internal
owner: aix-tf
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
review:
  reviewer: dictionary-curator
  review_status: reviewed
term: Root Cause Analysis
definition: 이상 현상의 직접/근본 원인 후보를 evidence 기반으로 좁혀가는 분석 활동
aliases:
- RCA
- 원인 분석
- 근본원인분석
- 원인 후보
domain: workflow
examples:
- Root Cause Analysis stage는 raw data, trend, guide, manual review를 묶어 판단한다.
links:
- /public/event-types/root_cause.analysis.requested.v1.md
- /public/actions/manual/review-root-cause.md
related_terms:
- FDC
- Response Trend
- Maintenance Guide
- Manual Handoff
source_refs:
- type: external-reference
  ref: NIST Control Charts
  url: https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm
- type: external-reference
  ref: KLA Defect Inspection and Review
  url: https://www.kla.com/products/chip-manufacturing/defect-inspection-review
maps_to_event_type: root_cause.analysis.requested.v1
maps_to_sop: boi:public:sop:equipment-abnormal-response
---

# Summary

이상 현상의 직접/근본 원인 후보를 evidence 기반으로 좁혀가는 분석 활동

# BoI Usage

- [root_cause.analysis.requested.v1](/public/event-types/root_cause.analysis.requested.v1.md)
- [review-root-cause](/public/actions/manual/review-root-cause.md)

# Agent Notes

- Agent는 `Root Cause Analysis` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [NIST Control Charts](https://www.itl.nist.gov/div898/handbook/pmc/section3/pmc31.htm)
- [KLA Defect Inspection and Review](https://www.kla.com/products/chip-manufacturing/defect-inspection-review)
