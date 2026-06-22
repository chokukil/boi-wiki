---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/dictionary-term
title: Fab
description: 반도체 wafer가 공정 장비와 cleanroom을 거쳐 chip으로 제조되는 제조 시설
tags: [Dictionary, Semiconductor, Manufacturing]
timestamp: "2026-06-22 09:00:00+09:00"
boi_id: boi:public:dictionary:fab
visibility: public
classification: internal
owner: aix-tf
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
review: {reviewer: dictionary-curator, review_status: reviewed}
term: Fab
definition: 반도체 wafer 제조가 이루어지는 fabrication facility. BoI Wiki에서는 생산 FAB, 연구소 FAB, 양산 FAB처럼 site/context 구분에도 사용한다.
aliases: [fabrication facility, 반도체 제조시설, 제조 FAB, 양산 FAB, 연구소 FAB]
domain: semiconductor-manufacturing
examples:
  - 연구소 FAB과 양산 FAB의 비교 Trend를 확인한다.
links:
  - /public/sop/direct-development-reporting.md
related_terms: [Wafer, Lot, Process Hold]
maps_to_sop: boi:public:sop:direct-development-reporting
source_refs:
  - {type: external-glossary, ref: "NIST Semiconductor Glossary", url: "https://www.nist.gov/semiconductors/semiconductor-glossary"}
  - {type: external-glossary, ref: "Lam Research Technical Glossary", url: "https://www.lamresearch.com/technical-glossary/"}
---

# Summary

Fab은 반도체 wafer 제조 시설을 뜻한다. BoI Wiki의 direct-development workflow에서는 연구소 FAB과 양산 FAB의 조건 또는 trend를 비교하는 문맥에서 자주 등장한다.

# BoI Usage

- [직개발 결과 확인 및 Reporting SOP](/public/sop/direct-development-reporting.md)의 연구소-양산 FAB 비교 stage에서 사용한다.
- "FAB 비교", "양산 FAB", "연구소 FAB" 검색은 이 term을 통해 관련 SOP/Event/Action으로 확장된다.

# Citations

- [NIST Semiconductor Glossary](https://www.nist.gov/semiconductors/semiconductor-glossary)
- [Lam Research Technical Glossary](https://www.lamresearch.com/technical-glossary/)
