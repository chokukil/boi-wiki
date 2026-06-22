---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Lot
description: 함께 투입·처리·추적되는 wafer 묶음 또는 생산 단위
tags: [Dictionary, Semiconductor, Lot]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:lot
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Lot
definition: 생산과 품질 추적을 위해 함께 관리되는 wafer 묶음. BoI event payload에서는 lot_id로 전달되며 Trend, Raw Data, 품질 이력 조회의 key가 된다.
aliases: [LOT, lot_id, Lot ID, 생산 lot, 로트]
domain: semiconductor-manufacturing
examples:
  - lot_id로 품질 시스템 Source Data와 설비 이력을 조회한다.
links:
  - /public/actions/api/request-raw-data.md
  - /public/actions/api/request-trend-history.md
related_terms: [Wafer, Quality System, Response Trend]
maps_to_action_key: sop.equipment.request_raw_data
source_refs:
  - {type: internal-doc, ref: "/public/sop/equipment-abnormal-response.md"}
---

# Summary

Lot은 wafer 묶음 또는 생산 추적 단위다. BoI Wiki에서는 event payload의 `lot_id`를 통해 Raw Data, Trend History, Source Data, 설비 이력을 묶는다.

# BoI Usage

- [Raw / Source Data 확인 요청](/public/actions/api/request-raw-data.md)
- [Trend / 이력 확인 요청](/public/actions/api/request-trend-history.md)

# Related Dictionary Terms

- [Wafer](wafer.md)
- [Quality System](quality-system.md)
- [Response Trend](response-trend.md)

# Citations

- [설비 이상 감지·원인 분석·이상 조치 SOP](/public/sop/equipment-abnormal-response.md)
