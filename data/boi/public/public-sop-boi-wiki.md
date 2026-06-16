---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: BoI Wiki SOP v0.1
description: Public, Team, Private BoI Wiki의 저장/조회/승격 기준
tags: [AIX, SOP, BoIWiki, OKF]
timestamp: 2026-06-16T09:10:00+09:00
boi_id: boi:public:sop:boi-wiki-v0.1
visibility: public
classification: internal
owner: aix-expansion-tf
author:
  type: human
  agent_id: seed
acl_policy: acl:public
status: approved
source_refs:
  - type: poc-design
    ref: BoI Wiki PRD
review:
  reviewer: tf-lead
  reviewed_at: 2026-06-16T09:10:00+09:00
  review_status: approved
---

# Summary

BoI Wiki는 OKF 기반 SK하이닉스형 업무 맥락 저장소다.

# Visibility

- Public: 누구나 읽을 수 있는 SOP, 표준, 용어, 가이드
- Team: 사번의 Team ACL 기준으로 접근 가능한 팀 지식
- Private: Web/Langflow에 저장된 개인 업무 맥락
- Local Private: 개인 로컬 Agent에만 저장되며 Web BoI Wiki에는 보이지 않음

# Promotion

Private BoI는 자동 공유하지 않는다. 사용자의 명시적 요청이 있을 때 Team/Public 공유용 사본을 draft로 생성한다.
