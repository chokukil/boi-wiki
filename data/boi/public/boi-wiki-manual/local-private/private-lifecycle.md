---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Private BoI 보관 정책
description: Private BoI 폭증에 대비한 retention, archive, review 기준
tags: [Manual, Private, Lifecycle, Archive]
timestamp: 2026-06-19T18:05:00+09:00
boi_id: boi:public:boi-wiki-manual:local-private:private-lifecycle
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: boi
    ref: boi:public:sop:boi-wiki-v0.1
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Private BoI는 많이 생길 수 있으므로 Git 제외만으로는 부족하다. agent는 생성 시 lifecycle metadata를 붙이고, 오래된 문서는 삭제보다 archive 후보로 제안한다.

# Retention Classes

| Class | Use |
|---|---|
| `ephemeral` | 자동 workflow 실행 기록 |
| `working` | 개인 업무 메모와 회의록 |
| `record` | 주간보고, 업무증빙, 장기 참조 문서 |
| `promoted_source` | Team/Public 승격 원본 |

# Archive

Local archive 경로는 `data/boi/private/me/_archive/YYYY/MM/`이다. Web Private archive 경로는 `data/boi/private/{employee}/_archive/YYYY/MM/`이다. PoC v1은 hard delete보다 archive를 우선한다.

# Citations

- [BoI Wiki SOP](/public/public-sop-boi-wiki.md)
- [Promotion Flow](/public/boi-wiki-manual/local-private/promotion-flow.md)
