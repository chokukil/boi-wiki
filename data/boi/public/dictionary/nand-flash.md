---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: NAND Flash
description: 전원이 없어도 데이터를 보존하는 non-volatile flash memory
tags:
- Dictionary
- Semiconductor
- memory
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:nand-flash
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
term: NAND Flash
definition: 전원이 없어도 데이터를 보존하는 non-volatile flash memory
aliases:
- NAND
- 낸드
- flash memory
- 비휘발성 메모리
domain: memory
examples:
- NAND 공정/품질 분석도 wafer, lot, yield, defect 용어 체계를 공유한다.
links: []
related_terms:
- Wafer
- Yield
- Defect
- Metrology
source_refs:
- type: external-reference
  ref: Intel Common Chip Terms
  url: https://newsroom.intel.com/de/tech101/explaining-common-chip-terms
- type: external-reference
  ref: Applied Materials Product Library
  url: https://www.appliedmaterials.com/us/en/product-library.html
---

# Summary

전원이 없어도 데이터를 보존하는 non-volatile flash memory

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `NAND Flash` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Wafer](wafer.md)
- [Yield](yield.md)
- [Defect](defect.md)
- [Metrology](metrology.md)

# Citations

- [Intel Common Chip Terms](https://newsroom.intel.com/de/tech101/explaining-common-chip-terms)
- [Applied Materials Product Library](https://www.appliedmaterials.com/us/en/product-library.html)
