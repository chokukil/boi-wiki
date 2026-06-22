---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Ion Implant
description: wafer에 ion을 주입해 전기적 특성을 조절하는 공정
tags:
- Dictionary
- Semiconductor
- process-module
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:ion-implant
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
term: Ion Implant
definition: wafer에 ion을 주입해 전기적 특성을 조절하는 공정
aliases:
- ion implantation
- implant
- 이온주입
- 임플란트
domain: process-module
examples:
- Implant dose/energy 이상은 electrical result와 recipe evidence를 같이 본다.
links: []
related_terms:
- Recipe
- Metrology
- Process Capability
source_refs:
- type: external-reference
  ref: Applied Materials Product Library
  url: https://www.appliedmaterials.com/us/en/product-library.html
---

# Summary

wafer에 ion을 주입해 전기적 특성을 조절하는 공정

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `Ion Implant` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Applied Materials Product Library](https://www.appliedmaterials.com/us/en/product-library.html)
