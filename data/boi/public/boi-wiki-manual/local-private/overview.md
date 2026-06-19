---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Local Private 시작하기
description: 일반 사용자가 Codex, Claude, Cursor로 개인 로컬 BoI Wiki workspace를 쓰는 방법
tags: [Manual, LocalPrivate, BoIWikiLocal, Agent]
timestamp: 2026-06-19T18:01:00+09:00
boi_id: boi:public:boi-wiki-manual:local-private:overview
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

Local Private은 개인 PC의 agent가 사용하는 로컬 BoI workspace다. Web BoI Wiki에는 보이지 않고, 사용자가 명시적으로 승인한 curated draft만 원격 공유 절차로 넘어간다.

# One Minute Start

1. agent에게 `boi-wiki-local repo 설치해줘`라고 요청한다.
2. 설치된 폴더에서 `이 폴더를 BoI Wiki Local로 써줘`라고 요청한다.
3. 이후 `이 회의 내용을 BoI로 정리해줘`, `이 SOP 이미지를 BoI Wiki 형식으로 초안 만들어줘`처럼 말한다.

# What Stays Local

- 개인 회의 메모
- 미정리 업무 맥락
- SOP 초안
- 팀 공유 전 보고서 초안
- 오래된 Private BoI archive 후보

# What Can Use Remote BoI Wiki

MCP가 연결되어 있으면 agent는 shared BoI Wiki의 SOP, Event Type, Action Spec을 검색할 수 있다. MCP가 없어도 Local Private 작성은 계속 동작한다.

# Citations

- [Local Private Agent Harness](/public/harness/local-private-agent-harness.md)
- [MCP Optional Guide](/public/boi-wiki-manual/local-private/mcp-optional.md)
- [Promotion Flow](/public/boi-wiki-manual/local-private/promotion-flow.md)
