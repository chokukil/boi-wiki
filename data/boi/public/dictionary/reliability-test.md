---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Reliability Test
description: 제품이나 공정 조건이 장기 동작, 반복 stress, disturb, retention 조건에서 안정적인지 확인하는 평가 범주
tags:
- Dictionary
- Semiconductor
- reliability
timestamp: '2026-06-30 13:20:00+09:00'
boi_id: boi:public:dictionary:reliability-test
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
term: Reliability Test
term_kind: concept
definition: 제품이나 공정 조건이 장기 동작, 반복 stress, disturb, retention 조건에서 안정적인지 확인하는 평가 범주
aliases:
- reliability evaluation
- reliability qualification
- 신뢰성 평가
- 신뢰성 시험
domain: reliability
examples:
- Word Line Disturbance Test는 NAND Flash reliability test의 세부 test-method로 다룬다.
links: []
related_terms:
- NAND Flash
- Quality System
- SPC
broader: []
narrower:
- Word Line Disturbance Test
same_as: []
curation_status: curated
compound_reason: ''
source_refs:
- type: qwen-import-curation
  ref: qwen-dictionary-granularity-parent
---

# Summary

제품이나 공정 조건이 장기 동작, 반복 stress, disturb, retention 조건에서 안정적인지 확인하는 평가 범주

# BoI Usage

- Reliability Test는 Qwen이 추출한 세부 test/mode 용어를 상위 품질 평가 맥락에 연결하기 위한 parent concept이다.

# Agent Notes

- Agent는 세부 disturb, retention, stress 조건 표현을 발견하면 바로 단독 canonical로 승격하지 않고 Reliability Test 또는 구체 test-method와 연결한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [NAND Flash](nand-flash.md)
- [Quality System](quality-system.md)
- [SPC](spc.md)

# Citations

- qwen-dictionary-granularity-parent
