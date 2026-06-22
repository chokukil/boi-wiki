---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Lithography
description: photoresist와 mask pattern을 이용해 wafer 위에 회로 pattern을 형성하는 노광 공정
tags:
- Dictionary
- Semiconductor
- process-module
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:lithography
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
term: Lithography
definition: photoresist와 mask pattern을 이용해 wafer 위에 회로 pattern을 형성하는 노광 공정
aliases:
- photolithography
- 노광
- 리소
- 포토 공정
domain: process-module
examples:
- Lithography issue는 overlay, CD, pattern defect 관점으로 metrology/inspection evidence와
  연결된다.
links: []
related_terms:
- Reticle / Photomask
- Photoresist
- Metrology
- Inspection
source_refs:
- type: external-reference
  ref: Applied Materials Product Library
  url: https://www.appliedmaterials.com/us/en/product-library.html
- type: external-reference
  ref: Applied Materials Technical Glossary
  url: https://www.appliedmaterials.com/us/en/glossary.html
---

# Summary

photoresist와 mask pattern을 이용해 wafer 위에 회로 pattern을 형성하는 노광 공정

# BoI Usage

- 이 용어는 ontology search의 query expansion과 context pack 구성에 사용한다.

# Agent Notes

- Agent는 `Lithography` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [Applied Materials Product Library](https://www.appliedmaterials.com/us/en/product-library.html)
- [Applied Materials Technical Glossary](https://www.appliedmaterials.com/us/en/glossary.html)
