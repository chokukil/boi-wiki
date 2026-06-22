---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Advanced Packaging
description: 2.5D/3D integration, chiplet, HBM 등 고밀도 연결과 집적을 위한 packaging 기술 범주
tags:
- Dictionary
- Semiconductor
- advanced-packaging
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:advanced-packaging
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
term: Advanced Packaging
definition: 2.5D/3D integration, chiplet, HBM 등 고밀도 연결과 집적을 위한 packaging 기술 범주
aliases:
- 첨단 패키징
- advanced package
- 2.5D packaging
- 3D packaging
domain: advanced-packaging
examples:
- Advanced Packaging 품질 이슈는 wafer inspection, metrology, traceability가 중요하다.
links: []
related_terms:
- HBM
- TSV
- Hybrid Bonding
- Interposer
- Wafer Level Package
source_refs:
- type: external-reference
  ref: Applied Materials Hybrid Bonding
  url: https://www.appliedmaterials.com/us/en/semiconductor/markets-and-inflections/heterogeneous-integration/hybrid-bonding.html
- type: external-reference
  ref: KLA Wafer Inspection and Metrology for Advanced Packaging
  url: https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging
- type: external-reference
  ref: SK hynix 16-layer HBM3E
  url: https://news.skhynix.com/sk-hynix-announces-16-layer-hbm3e-at-sk-ai-summit-2024/
---

# Summary

2.5D/3D integration, chiplet, HBM 등 고밀도 연결과 집적을 위한 packaging 기술 범주

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `Advanced Packaging` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Applied Materials Hybrid Bonding](https://www.appliedmaterials.com/us/en/semiconductor/markets-and-inflections/heterogeneous-integration/hybrid-bonding.html)
- [KLA Wafer Inspection and Metrology for Advanced Packaging](https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging)
- [SK hynix 16-layer HBM3E](https://news.skhynix.com/sk-hynix-announces-16-layer-hbm3e-at-sk-ai-summit-2024/)
