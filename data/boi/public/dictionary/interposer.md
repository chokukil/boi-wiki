---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Interposer
description: chiplet, memory, logic 사이의 고밀도 연결을 중개하는 package substrate 또는 silicon
  layer
tags:
- Dictionary
- Semiconductor
- advanced-packaging
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:interposer
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
term: Interposer
definition: chiplet, memory, logic 사이의 고밀도 연결을 중개하는 package substrate 또는 silicon layer
aliases:
- 인터포저
- silicon interposer
- package interposer
domain: advanced-packaging
examples:
- Interposer 기반 2.5D package는 HBM과 logic die를 고대역폭으로 연결한다.
links: []
related_terms:
- Advanced Packaging
- HBM
- TSV
- Hybrid Bonding
source_refs:
- type: external-reference
  ref: Applied Materials Hybrid Bonding
  url: https://www.appliedmaterials.com/us/en/semiconductor/markets-and-inflections/heterogeneous-integration/hybrid-bonding.html
- type: external-reference
  ref: SK hynix 16-layer HBM3E
  url: https://news.skhynix.com/sk-hynix-announces-16-layer-hbm3e-at-sk-ai-summit-2024/
---

# Summary

chiplet, memory, logic 사이의 고밀도 연결을 중개하는 package substrate 또는 silicon layer

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `Interposer` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Applied Materials Hybrid Bonding](https://www.appliedmaterials.com/us/en/semiconductor/markets-and-inflections/heterogeneous-integration/hybrid-bonding.html)
- [SK hynix 16-layer HBM3E](https://news.skhynix.com/sk-hynix-announces-16-layer-hbm3e-at-sk-ai-summit-2024/)
