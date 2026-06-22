---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Etch
description: 막이나 패턴을 선택적으로 제거하는 반도체 식각 공정
tags: [Dictionary, Semiconductor, Etch, Equipment]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:etch
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Etch
definition: 반도체 제조에서 필요한 형상을 만들기 위해 material을 선택적으로 제거하는 공정. PoC 설비 예시는 ETCH-VM 계열 장비로 표현된다.
aliases: [식각, Etching, ETCH, ETCH-VM, VM 장비]
domain: semiconductor-process
examples:
  - ETCH-VM-01에서 Response Chain 이상 alarm이 발생했다.
links:
  - /public/sop/equipment-abnormal-response.md
related_terms: [FDC, Response Trend, Equipment Alarm]
maps_to_event_type: equipment.alarm.raised.v1
maps_to_sop: boi:public:sop:equipment-abnormal-response
source_refs:
  - {type: external-glossary, ref: "Applied Materials Technical Glossary", url: "https://www.appliedmaterials.com/us/en/glossary.html"}
---

# Summary

Etch는 반도체 pattern 형성을 위해 material을 제거하는 공정이다. BoI Wiki PoC에서는 ETCH-VM 설비 alarm과 관련 SOP를 찾기 위한 alias로 사용한다.

# BoI Usage

- [equipment.alarm.raised.v1](/public/event-types/equipment.alarm.raised.v1.md)
- [설비 이상 대응 SOP](/public/sop/equipment-abnormal-response.md)

# Related Dictionary Terms

- [FDC](fdc.md)
- [Response Trend](response-trend.md)
- [Alarm](alarm.md) - `Equipment Alarm`와 연결되는 public dictionary term

# Citations

- [Applied Materials Technical Glossary](https://www.appliedmaterials.com/us/en/glossary.html)
