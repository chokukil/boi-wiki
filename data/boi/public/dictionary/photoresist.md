---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Photoresist
description: lithography에서 빛에 반응해 pattern 전사를 가능하게 하는 감광성 막
tags:
- Dictionary
- Semiconductor
- process-material
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:photoresist
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
term: Photoresist
definition: lithography에서 빛에 반응해 pattern 전사를 가능하게 하는 감광성 막
aliases:
- PR
- resist
- 감광액
- 포토레지스트
domain: process-material
examples:
- PR coating 또는 develop 이상은 defect와 CD shift의 원인이 될 수 있다.
links: []
related_terms:
- Lithography
- Reticle / Photomask
- Defect
source_refs:
- type: external-reference
  ref: Applied Materials Technical Glossary
  url: https://www.appliedmaterials.com/us/en/glossary.html
---

# Summary

lithography에서 빛에 반응해 pattern 전사를 가능하게 하는 감광성 막

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `Photoresist` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Lithography](lithography.md)
- [Reticle / Photomask](reticle-photomask.md)
- [Defect](defect.md)

# Citations

- [Applied Materials Technical Glossary](https://www.appliedmaterials.com/us/en/glossary.html)
