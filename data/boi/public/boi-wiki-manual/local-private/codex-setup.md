---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Codex로 BoI Wiki Local 사용하기
description: Codex가 boi-wiki-local의 AGENTS.md와 skill을 사용해 Local Private BoI를 생성하는 방법
tags: [Manual, Codex, LocalPrivate, Skill]
timestamp: 2026-06-19T18:02:00+09:00
boi_id: boi:public:boi-wiki-manual:local-private:codex-setup
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
    ref: boi:public:harness:local-private-agent-harness
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

Codex는 `AGENTS.md`와 `.agents/skills/boi-wiki-local/SKILL.md`를 읽어 Local Private 작성, 검증, 승격 draft 생성을 수행한다.

# Setup

사용자는 Codex에게 다음처럼 요청한다.

```text
이 repo 설치해줘.
이 폴더를 BoI Wiki Local로 써줘.
```

Codex는 Git, Python, MCP가 없어도 local Markdown workspace를 만들고 작업한다. MCP 설정이 있으면 shared BoI Wiki 검색을 추가로 사용한다.

# Codex Rules

- 저장 전 Level 0 self-check를 수행한다.
- 가능한 경우 `check.sh` 또는 `check.ps1`을 실행한다.
- Local Private 원문은 사용자 승인 없이 원격 전송하지 않는다.
- 공유 요청은 local promotion draft, preview, 사용자 승인, remote draft-only 순서로 처리한다.

# Citations

- [Local Private Overview](/public/boi-wiki-manual/local-private/overview.md)
- [MCP Optional Guide](/public/boi-wiki-manual/local-private/mcp-optional.md)
