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

Private BoI는 개인의 외부 기억이므로 사용자가 채택한 기억과 작업 중인 초안은 보호한다. 반대로 inbox report, sandbox/report artifact, generated BoI처럼 재생성 가능한 background 산출물은 기본 목록과 검색에서 제외하고, 중복되거나 오래된 것은 7일 quarantine 후 삭제한다.

# Retention Classes

| Class | Use |
|---|---|
| `ephemeral` | 자동 workflow 실행 기록 |
| `working` | 개인 업무 메모와 회의록 |
| `record` | 주간보고, 업무증빙, 장기 참조 문서 |
| `promoted_source` | Team/Public 승격 원본 |

# Lifecycle State

| State | Meaning | Default cleanup |
|---|---|---|
| `memory` | 사용자가 장기 기억으로 채택한 Second Brain 문서 | 삭제 금지 |
| `working` | 진행 중 메모, 초안, 개인 업무 문서 | 자동 삭제 금지 |
| `background` | inbox report, generated BoI, sandbox/report artifact | 중복/구버전 cleanup 후보 |
| `archived` | 기본 목록과 검색에서 제외된 보관 문서 | preview 후 cleanup 후보 |
| `delete_candidate` | 중복, superseded, 재생성 가능한 generated 산출물 | quarantine 후보 |
| `protected` | pinned, promoted, manually kept 문서 | 삭제 금지 |

# Quarantine and Delete

기본 정책은 archive 무한 보관이 아니라 `preview -> quarantine -> hard delete`이다.

1. `GET /api/private-memory/cleanup-preview`는 파일을 변경하지 않고 삭제 후보와 보호 후보를 보여준다.
2. `POST /api/private-memory/cleanup-run`은 `user_confirmed=true`가 있을 때만 generated/background 후보를 `BOI_RUNTIME_ROOT/private-trash/{employee_id}/{cleanup_id}/`로 이동한다.
3. Quarantine manifest는 원래 경로, BoI ID, 제목, 이동 시각, `delete_after`, restore API를 남긴다.
4. 7일 이내에는 `POST /api/private-memory/restore`로 복구할 수 있다.
5. 7일이 지나면 `POST /api/private-memory/purge-expired`가 hard delete한다.

원본 `data/boi/private`에는 tombstone을 만들지 않는다. 파일 수를 줄이는 것이 목적이다.

# Explorer

BoI Wiki Explorer와 `/api/boi` 기본 목록은 `memory`, `working`, `protected` 문서만 센다. `background`, `archived`, quarantine 문서는 명시 필터에서만 표시한다.

- `include_generated=true`
- `include_archived=true`
- `include_quarantined=true`

Inbox report는 같은 `report_id + contract_version` 기준으로 최신 1개만 유지하고, 구버전과 반복 생성물은 cleanup preview에서 quarantine 후보가 된다.

# Citations

- [BoI Wiki SOP](/public/public-sop-boi-wiki.md)
- [Promotion Flow](/public/boi-wiki-manual/local-private/promotion-flow.md)
