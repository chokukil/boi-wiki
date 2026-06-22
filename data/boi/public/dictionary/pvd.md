---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: PVD
description: physical vapor deposition. 물리적 방식으로 target material을 wafer에 증착하는 공정
tags:
- Dictionary
- Semiconductor
- process-module
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:pvd
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
term: PVD
definition: physical vapor deposition. 물리적 방식으로 target material을 wafer에 증착하는 공정
aliases:
- Physical Vapor Deposition
- sputter
- 스퍼터
- 물리기상증착
domain: process-module
examples:
- PVD target 상태나 chamber condition은 particle defect와 관련될 수 있다.
links: []
related_terms:
- Deposition
- Chamber
- Defect
- Inspection
source_refs:
- type: external-reference
  ref: Applied Materials Product Library
  url: https://www.appliedmaterials.com/us/en/product-library.html
- type: external-reference
  ref: Lam Research Deposition Essentials
  url: https://newsroom.lamresearch.com/Deposition-Essentials-Semi-101?blog=true
---

# Summary

physical vapor deposition. 물리적 방식으로 target material을 wafer에 증착하는 공정

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `PVD` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Deposition](deposition.md)
- [Chamber](chamber.md)
- [Defect](defect.md)
- [Inspection](inspection.md)

# Citations

- [Applied Materials Product Library](https://www.appliedmaterials.com/us/en/product-library.html)
- [Lam Research Deposition Essentials](https://newsroom.lamresearch.com/Deposition-Essentials-Semi-101?blog=true)
