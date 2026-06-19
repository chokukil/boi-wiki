---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Local Private 승격과 공유 절차
description: Local Private BoI를 Team/Public draft로 승격할 때 필요한 사용자 확인과 draft-only 정책
tags: [Manual, Promotion, LocalPrivate, Draft]
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
    ref: boi:public:boi-wiki-manual:operations:draft-and-git-policy
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Local Private 원본은 자동 publish하지 않는다. 공유 요청은 local promotion draft를 먼저 만들고, 사용자 preview와 명시 승인을 거친 뒤 원격 draft-only 절차로 넘어간다.

# Flow

1. 사용자가 `Public으로 공유해줘` 또는 `팀 주간보고로 올려줘`라고 요청한다.
2. agent가 local promotion draft를 만든다.
3. agent가 민감정보 제거, source/citation, target visibility, preview/diff를 확인한다.
4. 사용자가 명시 승인한다.
5. agent가 MCP 또는 Web draft API로 remote draft-only 요청을 만든다.
6. shared BoI Wiki repo에서 별도 agent가 lint, test, commit을 수행한다.

# Non Goals

- Local Private 원본 직접 publish
- 사용자 승인 없는 원격 전송
- remote source file 즉시 변경

# Citations

- [Draft and Git Policy](/public/boi-wiki-manual/operations/draft-and-git-policy.md)
- [Local Private Agent Harness](/public/harness/local-private-agent-harness.md)
