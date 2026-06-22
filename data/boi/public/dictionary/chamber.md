---
okf_version: '0.1'
boi_profile_version: '0.1'
type: boi/dictionary-term
title: Chamber
description: 공정 설비 내부에서 wafer가 실제 처리되는 반응/처리 공간
tags:
- Dictionary
- Semiconductor
- equipment
timestamp: '2026-06-23 09:00:00+09:00'
boi_id: boi:public:dictionary:chamber
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
term: Chamber
definition: 공정 설비 내부에서 wafer가 실제 처리되는 반응/처리 공간
aliases:
- 챔버
- process chamber
- reaction chamber
domain: equipment
examples:
- Chamber 상태 변화는 particle, film, etch rate trend 이상으로 이어질 수 있다.
links:
- /public/actions/api/request-trend-history.md
related_terms:
- Equipment
- Recipe
- Alarm
- Response Trend
source_refs:
- type: external-reference
  ref: Lam Research Our Processes
  url: https://www.lamresearch.com/products/our-processes/
- type: external-reference
  ref: Lam Research Technical Glossary
  url: https://www.lamresearch.com/technical-glossary/
---

# Summary

공정 설비 내부에서 wafer가 실제 처리되는 반응/처리 공간

# BoI Usage

- [request-trend-history](/public/actions/api/request-trend-history.md)

# Agent Notes

- Agent는 `Chamber` 또는 별칭이 query에 나오면 관련 SOP/Event/Action 후보를 함께 조회한다.
- 실행 권한이나 approval policy는 dictionary가 아니라 Action Gateway와 BoI Profile metadata가 결정한다.

# Related Dictionary Terms

- [Equipment](equipment.md)
- [Recipe](recipe.md)
- [Alarm](alarm.md)
- [Response Trend](response-trend.md)

# Citations

- [Lam Research Our Processes](https://www.lamresearch.com/products/our-processes/)
- [Lam Research Technical Glossary](https://www.lamresearch.com/technical-glossary/)
