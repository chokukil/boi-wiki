---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: CMP
description: chemical mechanical planarization. 화학 반응과 기계적 polishing으로 wafer 표면을 평탄화하는
  공정
tags:
- Dictionary
- Semiconductor
- process-module
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:cmp
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
term: CMP
definition: chemical mechanical planarization. 화학 반응과 기계적 polishing으로 wafer 표면을 평탄화하는
  공정
aliases:
- Chemical Mechanical Planarization
- Chemical Mechanical Polishing
- 평탄화
- CMP 공정
domain: process-module
examples:
- CMP 이상은 thickness uniformity, scratch defect, slurry 상태 evidence와 함께 판단한다.
links: []
related_terms:
- Wafer
- Defect
- Metrology
- Inspection
source_refs:
- type: external-reference
  ref: Applied Materials Product Library
  url: https://www.appliedmaterials.com/us/en/product-library.html
---

# Summary

chemical mechanical planarization. 화학 반응과 기계적 polishing으로 wafer 표면을 평탄화하는 공정

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `CMP` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Wafer](wafer.md)
- [Defect](defect.md)
- [Metrology](metrology.md)
- [Inspection](inspection.md)

# Citations

- [Applied Materials Product Library](https://www.appliedmaterials.com/us/en/product-library.html)
