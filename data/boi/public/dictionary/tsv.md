---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: TSV
description: through-silicon via. 적층 chip 사이를 수직으로 연결하는 silicon 관통 전극
tags:
- Dictionary
- Semiconductor
- advanced-packaging
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:tsv
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
term: TSV
definition: through-silicon via. 적층 chip 사이를 수직으로 연결하는 silicon 관통 전극
aliases:
- Through-Silicon Via
- 실리콘 관통전극
- TSV via
- 수직 배선
domain: advanced-packaging
examples:
- TSV defect나 resistance issue는 HBM/advanced packaging 품질 분석에서 중요하다.
links: []
related_terms:
- HBM
- Advanced Packaging
- Hybrid Bonding
- Interposer
source_refs:
- type: external-reference
  ref: SK hynix HBM Leadership
  url: https://news.skhynix.com/one-team-spirit-sk-hynix-journey-to-hbm-leadership/
- type: external-reference
  ref: Applied Materials Hybrid Bonding
  url: https://www.appliedmaterials.com/us/en/semiconductor/markets-and-inflections/heterogeneous-integration/hybrid-bonding.html
- type: external-reference
  ref: Rambus HBM3 Overview
  url: https://www.rambus.com/blogs/hbm3-everything-you-need-to-know/
---

# Summary

through-silicon via. 적층 chip 사이를 수직으로 연결하는 silicon 관통 전극

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `TSV` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [SK hynix HBM Leadership](https://news.skhynix.com/one-team-spirit-sk-hynix-journey-to-hbm-leadership/)
- [Applied Materials Hybrid Bonding](https://www.appliedmaterials.com/us/en/semiconductor/markets-and-inflections/heterogeneous-integration/hybrid-bonding.html)
- [Rambus HBM3 Overview](https://www.rambus.com/blogs/hbm3-everything-you-need-to-know/)
