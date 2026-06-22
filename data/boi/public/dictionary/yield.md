---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Yield
description: 투입 wafer/die 중 요구 spec을 만족해 사용 가능한 비율
tags:
- Dictionary
- Semiconductor
- quality
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:yield
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
term: Yield
definition: 투입 wafer/die 중 요구 spec을 만족해 사용 가능한 비율
aliases:
- 수율
- good die ratio
- usable die percentage
domain: quality
examples:
- Yield 하락은 defect density, process capability, lot history와 함께 분석한다.
links: []
related_terms:
- Die
- Wafer
- Defect Density
- Process Capability
source_refs:
- type: external-reference
  ref: Applied Materials Technical Glossary
  url: https://www.appliedmaterials.com/us/en/glossary.html
- type: external-reference
  ref: Intel Common Chip Terms
  url: https://newsroom.intel.com/de/tech101/explaining-common-chip-terms
---

# Summary

투입 wafer/die 중 요구 spec을 만족해 사용 가능한 비율

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `Yield` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Applied Materials Technical Glossary](https://www.appliedmaterials.com/us/en/glossary.html)
- [Intel Common Chip Terms](https://newsroom.intel.com/de/tech101/explaining-common-chip-terms)
