---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Wafer
description: 반도체 소자가 형성되는 얇고 평탄한 기판
tags: [Dictionary, Semiconductor, Wafer]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:wafer
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Wafer
definition: 반도체 공정에서 여러 die 또는 cell이 만들어지는 얇은 기판. BoI event payload에서는 wafer_id나 wafer map evidence로 등장한다.
aliases: [웨이퍼, WF, wafer_id, wafer map, wafer-map]
domain: semiconductor-manufacturing
examples:
  - wafer_id 기준으로 Map View Image와 Trend evidence를 연결한다.
links:
  - /public/sop/equipment-abnormal-response.md
  - /public/sop/direct-development-reporting.md
related_terms: [Lot, Map View, Die]
source_refs:
  - {type: external-glossary, ref: "Intel Common Chip Terms", url: "https://newsroom.intel.com/de/tech101/explaining-common-chip-terms"}
  - {type: external-glossary, ref: "NIST Semiconductor Glossary", url: "https://www.nist.gov/semiconductors/semiconductor-glossary"}
---

# Summary

Wafer는 반도체 공정의 기본 단위 기판이다. BoI Wiki에서는 `wafer_id`, Map View, Lot/Wafer 이력, wafer-level evidence를 연결하는 핵심 term으로 사용한다.

# BoI Usage

- [설비 이상 대응 SOP](/public/sop/equipment-abnormal-response.md)의 detect/analyze stage에서 Lot/Wafer 이력 조회와 연결된다.
- [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)의 Map View 확인 stage와 연결된다.

# Related Dictionary Terms

- [Lot](lot.md)
- [Map View](map-view.md)
- [Die](die.md)

# Citations

- [Intel Common Chip Terms](https://newsroom.intel.com/de/tech101/explaining-common-chip-terms)
- [NIST Semiconductor Glossary](https://www.nist.gov/semiconductors/semiconductor-glossary)
