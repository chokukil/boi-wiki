---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: DRAM
description: 전하 저장 cell을 이용하는 volatile memory로 HBM stack의 기반 memory die 범주
tags:
- Dictionary
- Semiconductor
- memory
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:dram
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
term: DRAM
definition: 전하 저장 cell을 이용하는 volatile memory로 HBM stack의 기반 memory die 범주
aliases:
- Dynamic Random Access Memory
- 디램
- D램
domain: memory
examples:
- HBM은 여러 DRAM die를 적층하고 TSV로 연결하는 고대역폭 memory다.
links: []
related_terms:
- HBM
- TSV
- Die
- Advanced Packaging
source_refs:
- type: external-reference
  ref: SK hynix HBM Leadership
  url: https://news.skhynix.com/one-team-spirit-sk-hynix-journey-to-hbm-leadership/
- type: external-reference
  ref: Rambus HBM3 Overview
  url: https://www.rambus.com/blogs/hbm3-everything-you-need-to-know/
---

# Summary

전하 저장 cell을 이용하는 volatile memory로 HBM stack의 기반 memory die 범주

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `DRAM` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [HBM](hbm.md)
- [TSV](tsv.md)
- [Die](die.md)
- [Advanced Packaging](advanced-packaging.md)

# Citations

- [SK hynix HBM Leadership](https://news.skhynix.com/one-team-spirit-sk-hynix-journey-to-hbm-leadership/)
- [Rambus HBM3 Overview](https://www.rambus.com/blogs/hbm3-everything-you-need-to-know/)
