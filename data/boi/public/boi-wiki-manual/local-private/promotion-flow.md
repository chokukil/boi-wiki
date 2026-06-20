---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Local Private 승격과 공유 절차
description: Local Private BoI를 Team/Public로 승격할 때 필요한 사용자 승인, 자동 검증, 즉시 게시, HOTL 정책
tags: [Manual, Promotion, LocalPrivate, HOTL]
timestamp: 2026-06-19T18:04:00+09:00
boi_id: boi:public:boi-wiki-manual:local-private:promotion-flow
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
    ref: boi:public:boi-wiki-manual:operations:visibility-and-promotion-policy
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Local Private 원본은 자동 publish하지 않는다. 공유 요청은 local promotion draft와 local preflight를 먼저 만들고, 사용자가 preview를 명시 승인한 뒤 원격 동기 검증/게시 절차로 넘어간다.

# Flow

1. 사용자가 `Public으로 공유해줘` 또는 `팀 주간보고로 올려줘`라고 요청한다.
2. agent가 local promotion draft를 만든다.
3. agent가 민감정보 제거, source/citation, target visibility, preview/diff, local preflight를 확인한다.
4. 사용자가 명시 승인한다.
5. agent가 MCP `promotion_submit` 또는 Web promotion API로 remote sync validation을 요청한다.
6. 검증 통과 시 Team/Public에 즉시 게시되고 `hotl.status: watching`으로 사후 모니터링된다.
7. 검증 실패 시 게시하지 않고 validation report를 사용자와 agent에게 반환한다.

# Non Goals

- Local Private 원본 직접 publish
- 사용자 승인 없는 원격 전송
- 자동 검증 없는 Team/Public 게시

# Citations

- [Visibility and Promotion Policy](/public/boi-wiki-manual/operations/visibility-and-promotion-policy.md)
- [Local Private Agent Harness](/public/harness/local-private-agent-harness.md)
