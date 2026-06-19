---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Local Private Agent Harness
description: Codex, Claude, Cursor가 Local Private BoI workspace를 같은 방식으로 만들고 검증하는 기준
tags: [Harness, LocalPrivate, Codex, Claude, Cursor]
timestamp: 2026-06-19T18:00:00+09:00
boi_id: boi:public:harness:local-private-agent-harness
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
    ref: boi:public:boi-wiki-manual:local-private:overview
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Local Private Agent Harness는 일반 사용자가 lint, MCP, Git을 몰라도 agent가 Local Private BoI를 OKF 구조로 저장하도록 하는 기준이다.

# Agent Rules

1. 전체 파일을 먼저 뒤지지 말고 `index.md`에서 시작해 필요한 폴더의 `index.md`와 concept 문서로 좁힌다.
2. 개인 기록은 local workspace의 `data/boi/private/me/...` 아래에 저장한다.
3. Local Private 문서에는 `visibility: local-private`, `local_only: true`, `promotion_status`, lifecycle metadata를 넣는다.
4. 저장 전 Level 0 self-check를 반드시 수행하고, 가능하면 `check.ps1` 또는 `check.sh`도 실행한다.
5. `index.md`와 `log.md`를 업데이트한다.
6. 사용자 명시 승인 없이 Local Private 원문을 원격 MCP/API/GitHub/외부 서비스에 전송하지 않는다.

# Validation Levels

| Level | Actor | Description |
|---|---|---|
| 0 | Agent | frontmatter, path, lifecycle, index/log, citation, publish confirmation self-check |
| 1 | OS shell | `check.ps1` 또는 `check.sh` no-dependency 구조 점검 |
| 2 | Developer agent | Python이 있을 때 local strict OKF lint |
| 3 | Shared repo agent | 원격 반영 전 shared BoI Wiki OKF lint, tests, CI |

# Citations

- [Local Private Overview](/public/boi-wiki-manual/local-private/overview.md)
- [Promotion Flow](/public/boi-wiki-manual/local-private/promotion-flow.md)
