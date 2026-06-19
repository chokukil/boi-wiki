---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Wiki Local FAQ
description: 일반 사용자가 Local Private BoI를 사용할 때 자주 묻는 질문
tags: [Manual, FAQ, LocalPrivate]
timestamp: 2026-06-19T18:06:00+09:00
boi_id: boi:public:boi-wiki-manual:local-private:faq
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

Local Private은 일반 사용자가 agent와 함께 개인 업무 맥락을 쌓는 로컬 workspace다.

# FAQ

## MCP를 몰라도 되나요?

된다. MCP는 shared BoI Wiki 검색과 draft 요청을 쉽게 만드는 선택 기능이다.

## Git이 없어도 되나요?

된다. Git이 있으면 agent가 local history를 남기고, 없으면 plain folder로 동작한다.

## 내 문서가 Web BoI Wiki에 올라가나요?

아니다. Local Private은 Web BoI Wiki에 보이지 않는다. 공유하려면 사용자가 명시 승인해야 한다.

## Public 공유는 언제 되나요?

agent가 local promotion draft를 만들고, 사용자가 preview를 보고 승인한 뒤 remote draft-only 절차를 거친다.

# Citations

- [Local Private Overview](/public/boi-wiki-manual/local-private/overview.md)
- [Private Lifecycle](/public/boi-wiki-manual/local-private/private-lifecycle.md)
