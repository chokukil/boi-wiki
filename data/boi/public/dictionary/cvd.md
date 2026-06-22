---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: CVD
description: chemical vapor deposition. gas phase precursor 반응으로 wafer 위에 박막을 형성하는
  증착 방식
tags:
- Dictionary
- Semiconductor
- process-module
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:cvd
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
term: CVD
definition: chemical vapor deposition. gas phase precursor 반응으로 wafer 위에 박막을 형성하는
  증착 방식
aliases:
- Chemical Vapor Deposition
- 화학기상증착
- CVD 공정
domain: process-module
examples:
- CVD chamber condition 변화는 film uniformity와 defect trend로 확인한다.
links: []
related_terms:
- Deposition
- Chamber
- Metrology
- Defect
source_refs:
- type: external-reference
  ref: Applied Materials Product Library
  url: https://www.appliedmaterials.com/us/en/product-library.html
- type: external-reference
  ref: Lam Research Deposition Essentials
  url: https://newsroom.lamresearch.com/Deposition-Essentials-Semi-101?blog=true
---

# Summary

chemical vapor deposition. gas phase precursor 반응으로 wafer 위에 박막을 형성하는 증착 방식

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `CVD` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Deposition](deposition.md)
- [Chamber](chamber.md)
- [Metrology](metrology.md)
- [Defect](defect.md)

# Citations

- [Applied Materials Product Library](https://www.appliedmaterials.com/us/en/product-library.html)
- [Lam Research Deposition Essentials](https://newsroom.lamresearch.com/Deposition-Essentials-Semi-101?blog=true)
