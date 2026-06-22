---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: FDC
description: 설비 fault를 감지하고 분류하는 공정 모니터링 체계
tags: [Dictionary, Semiconductor, FDC, Equipment]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:fdc
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: FDC
definition: Fault Detection and Classification. 설비/공정 sensor나 trend에서 이상을 감지하고 분류하는 활동 또는 시스템 범주.
aliases: [Fault Detection and Classification, Fault Detection, fault 감지, 이상 감지, 설비 이상 감지]
domain: equipment-monitoring
examples:
  - FDC alarm은 설비 이상 대응 SOP의 detect stage 진입 event로 볼 수 있다.
links:
  - /public/event-types/equipment.alarm.raised.v1.md
  - /public/event-types/trend.anomaly.detected.v1.md
related_terms: [SPC, Response Trend, Alarm]
maps_to_event_type: trend.anomaly.detected.v1
maps_to_sop: boi:public:sop:equipment-abnormal-response
source_refs:
  - {type: external-paper, ref: "Skyworks IEEE article on FDC", url: "https://www.skyworksinc.com/-/media/SkyWorks/Documents/Articles/IEEE_Chang_202304_Advanced_Process_Monitoring.pdf"}
---

# Summary

FDC는 설비 fault를 감지하고 분류하는 모니터링 개념이다. BoI Wiki에서는 Alarm, Trend 이상, 설비 상태 signal을 SOP의 `detect` stage로 연결하기 위한 dictionary term이다.

# BoI Usage

- [Trend 이상 감지](/public/event-types/trend.anomaly.detected.v1.md)
- [설비 Alarm 발생](/public/event-types/equipment.alarm.raised.v1.md)

# Related Dictionary Terms

- [SPC](spc.md)
- [Response Trend](response-trend.md)
- [Alarm](alarm.md)

# Citations

- [Skyworks IEEE article on FDC](https://www.skyworksinc.com/-/media/SkyWorks/Documents/Articles/IEEE_Chang_202304_Advanced_Process_Monitoring.pdf)
