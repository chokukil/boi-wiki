---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Wafer Level Package
description: wafer 상태에서 packaging 또는 test를 수행한 뒤 singulation하는 packaging 방식
tags:
- Dictionary
- Semiconductor
- advanced-packaging
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:wafer-level-package
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
term: Wafer Level Package
definition: wafer 상태에서 packaging 또는 test를 수행한 뒤 singulation하는 packaging 방식
aliases:
- WLP
- Wafer Level Packaging
- 웨이퍼 레벨 패키지
domain: advanced-packaging
examples:
- WLP는 wafer 단위 traceability와 inspection/metrology evidence 관리가 중요하다.
links: []
related_terms:
- Wafer
- Advanced Packaging
- Inspection
- Metrology
source_refs:
- type: external-reference
  ref: SK hynix HBM Leadership
  url: https://news.skhynix.com/one-team-spirit-sk-hynix-journey-to-hbm-leadership/
- type: external-reference
  ref: KLA Wafer Inspection and Metrology for Advanced Packaging
  url: https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging
---

# Summary

wafer 상태에서 packaging 또는 test를 수행한 뒤 singulation하는 packaging 방식

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `Wafer Level Package` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [SK hynix HBM Leadership](https://news.skhynix.com/one-team-spirit-sk-hynix-journey-to-hbm-leadership/)
- [KLA Wafer Inspection and Metrology for Advanced Packaging](https://www.kla.com/products/packaging-manufacturing/wafer-inspection-and-metrology-for-advanced-packaging)
