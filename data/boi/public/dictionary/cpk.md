---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Cpk
description: 공정 평균과 산포가 spec limit에 얼마나 여유가 있는지 나타내는 process capability 지표
tags:
- Dictionary
- Semiconductor
- spc
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:cpk
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
term: Cpk
definition: 공정 평균과 산포가 spec limit에 얼마나 여유가 있는지 나타내는 process capability 지표
aliases:
- Process Capability Index
- 공정능력지수
- CpK
- cpk index
domain: spc
examples:
- Cpk 저하는 Response Trend 분석과 Spec / Rule 검토에서 핵심 evidence가 된다.
links:
- /public/actions/api/request-trend-history.md
related_terms:
- Process Capability
- SPC
- Spec / Rule
- Response Trend
source_refs:
- type: external-reference
  ref: NIST Cpk
  url: https://www.itl.nist.gov/div898/software/dataplot/refman2/ch2/cpk.pdf
- type: external-reference
  ref: NIST Process Capability
  url: https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm
---

# Summary

공정 평균과 산포가 spec limit에 얼마나 여유가 있는지 나타내는 process capability 지표

# BoI Usage

- [request-trend-history](/public/actions/api/request-trend-history.md)

# Agent Notes

- Agent는 `Cpk` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Citations

- [NIST Cpk](https://www.itl.nist.gov/div898/software/dataplot/refman2/ch2/cpk.pdf)
- [NIST Process Capability](https://www.itl.nist.gov/div898/handbook/pmc/section1/pmc16.htm)
