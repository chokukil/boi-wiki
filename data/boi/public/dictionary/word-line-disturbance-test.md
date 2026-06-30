---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Word Line Disturbance Test
description: NAND word line disturbance 평가에서 program state 조건별 disturb 변형을 묶어 부르는
  현업 표현
tags:
- Dictionary
- QwenImport
timestamp: '2026-06-30T17:14:51+09:00'
boi_id: boi:public:dictionary:word-line-disturbance-test
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
term: Word Line Disturbance Test
term_kind: test-method
definition: NAND word line disturbance 평가에서 program state 조건별 disturb 변형을 묶어 부르는 현업
  표현
aliases:
- 0-PG Dist
- 1-NG Dist
- 0-PG Dist / 1-NG Dist
domain: reliability
examples:
- Word Line Disturbance Test 용어를 BoI Wiki dictionary에서 해석한다.
links: []
related_terms:
- Reliability Test
- NAND Flash
broader:
- Reliability Test
- NAND Flash
narrower: []
same_as: []
curation_status: curated
compound_reason: slash-bundle of program-state-specific disturbance test variants
source_refs:
- type: qwen-import
  ref: qwen-source:fe6f3572f6da
- type: qwen-override
  ref: replace_with_canonical
---

# Summary

NAND word line disturbance 평가에서 program state 조건별 disturb 변형을 묶어 부르는 현업 표현

# BoI Usage

- Canonical term: Word Line Disturbance Test
- Term kind: test-method
- Qwen source terms are preserved as aliases or curation manifest rows; embedding vectors are not stored.

# Agent Notes

- Use this term for ontology search interpretation and query expansion only.
- Execution authority remains with Event Broker, Action Gateway, and BoI Profile ACL.

# Related Dictionary Terms

- [Reliability Test](reliability-test.md)
- [NAND Flash](nand-flash.md)

# Citations

- qwen-source:fe6f3572f6da
- replace_with_canonical
