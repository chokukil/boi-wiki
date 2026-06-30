---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Memory Stack Height
description: memory package 또는 3D stack에서 적층 높이 변형을 묶어 부르는 현업 표현
tags:
- Dictionary
- QwenImport
timestamp: '2026-06-30T17:14:51+09:00'
boi_id: boi:public:dictionary:memory-stack-height
visibility: public
classification: internal
owner: aix-tf
author:
  type: agent
  agent_id: qwen-dictionary-import
acl_policy: acl:public
status: reviewed
review:
  reviewer: dictionary-curator
  review_status: reviewed
term: Memory Stack Height
term_kind: concept
definition: memory package 또는 3D stack에서 적층 높이 변형을 묶어 부르는 현업 표현
aliases:
- 2HI
- 4HI
- 8HI
- 2HI Stack
- 4HI Stack
- 8HI Stack
- 3DS Stack Height
- 2HI / 4HI / 8HI Stack
domain: advanced-packaging
examples:
- Memory Stack Height 용어를 BoI Wiki dictionary에서 해석한다.
links: []
related_terms:
- Advanced Packaging
- HBM
- TSV
broader:
- Advanced Packaging
narrower: []
same_as: []
curation_status: curated
compound_reason: numeric variant bundle for memory stack height
source_refs:
- type: qwen-import
  ref: qwen-source:72c7bdd7175f
- type: qwen-override
  ref: replace_with_canonical
---

# Summary

memory package 또는 3D stack에서 적층 높이 변형을 묶어 부르는 현업 표현

# BoI Usage

- Canonical term: Memory Stack Height
- Term kind: concept
- Qwen source terms are preserved as aliases or curation manifest rows; embedding vectors are not stored.

# Agent Notes

- Use this term for ontology search interpretation and query expansion only.
- Execution authority remains with Event Broker, Action Gateway, and BoI Profile ACL.

# Related Dictionary Terms

- [Advanced Packaging](advanced-packaging.md)
- [HBM](hbm.md)
- [TSV](tsv.md)

# Citations

- qwen-source:72c7bdd7175f
- replace_with_canonical
