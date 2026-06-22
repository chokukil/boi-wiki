---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: HBM
description: 여러 DRAM die를 3D stack으로 적층해 높은 bandwidth를 제공하는 memory package
tags:
- Dictionary
- Semiconductor
- advanced-packaging
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:hbm
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
term: HBM
definition: 여러 DRAM die를 3D stack으로 적층해 높은 bandwidth를 제공하는 memory package
aliases:
- High Bandwidth Memory
- 고대역폭 메모리
- HBM stack
- 하이밴드위스메모리
domain: advanced-packaging
examples:
- HBM 관련 issue는 TSV, hybrid bonding, advanced packaging evidence와 함께 해석한다.
links: []
related_terms:
- DRAM
- TSV
- Hybrid Bonding
- Advanced Packaging
source_refs:
- type: external-reference
  ref: SK hynix HBM Leadership
  url: https://news.skhynix.com/one-team-spirit-sk-hynix-journey-to-hbm-leadership/
- type: external-reference
  ref: SK hynix 16-layer HBM3E
  url: https://news.skhynix.com/sk-hynix-announces-16-layer-hbm3e-at-sk-ai-summit-2024/
- type: external-reference
  ref: Rambus HBM3 Overview
  url: https://www.rambus.com/blogs/hbm3-everything-you-need-to-know/
---

# Summary

여러 DRAM die를 3D stack으로 적층해 높은 bandwidth를 제공하는 memory package

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `HBM` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [SK hynix HBM Leadership](https://news.skhynix.com/one-team-spirit-sk-hynix-journey-to-hbm-leadership/)
- [SK hynix 16-layer HBM3E](https://news.skhynix.com/sk-hynix-announces-16-layer-hbm3e-at-sk-ai-summit-2024/)
- [Rambus HBM3 Overview](https://www.rambus.com/blogs/hbm3-everything-you-need-to-know/)
