---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Reticle / Photomask
description: lithography에서 회로 pattern을 wafer에 전사하기 위해 쓰는 mask 원판
tags:
- Dictionary
- Semiconductor
- lithography
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:reticle-photomask
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
term: Reticle / Photomask
definition: lithography에서 회로 pattern을 wafer에 전사하기 위해 쓰는 mask 원판
aliases:
- reticle
- photomask
- mask plate
- 마스크
- 레티클
- 포토마스크
domain: lithography
examples:
- 특정 reticle layer에서 반복 defect가 생기면 lot/wafer map과 함께 원인 분석한다.
links: []
related_terms:
- Lithography
- Photoresist
- Wafer
- Defect
source_refs:
- type: external-reference
  ref: UCSB Nanofab Reticle Layout Note
  url: https://wiki.nanofab.ucsb.edu/w/images/c/cb/Demis_D_John_-_Stepper_Reticle_Layout_vs_Wafer_Layout.pdf
- type: external-reference
  ref: Applied Materials Product Library
  url: https://www.appliedmaterials.com/us/en/product-library.html
---

# Summary

lithography에서 회로 pattern을 wafer에 전사하기 위해 쓰는 mask 원판

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `Reticle / Photomask` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Lithography](lithography.md)
- [Photoresist](photoresist.md)
- [Wafer](wafer.md)
- [Defect](defect.md)

# Citations

- [UCSB Nanofab Reticle Layout Note](https://wiki.nanofab.ucsb.edu/w/images/c/cb/Demis_D_John_-_Stepper_Reticle_Layout_vs_Wafer_Layout.pdf)
- [Applied Materials Product Library](https://www.appliedmaterials.com/us/en/product-library.html)
