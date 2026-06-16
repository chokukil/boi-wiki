---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: AIX 확산 TF 업무 맥락 자산화 PoC 계획
description: Agent Harness, BoI Wiki, Langflow BoI 공통 컴포넌트, Kafka Event Broker 범위
tags: [AIX, PoC, Langflow, Kafka, BoIWiki]
timestamp: 2026-06-16T10:00:00+09:00
boi_id: boi:team:aix-tf:poc-plan-v0.1
visibility: team
team_id: aix-tf
classification: internal
owner: aix-expansion-tf
author:
  type: human
  agent_id: seed
acl_policy: acl:team:aix-tf
status: reviewed
source_refs:
  - type: poc-discussion
    ref: AIX TF PoC planning
review:
  reviewer: tf-lead
  reviewed_at: 2026-06-16T10:00:00+09:00
  review_status: reviewed
---

# Summary

이번 PoC는 1인 1 Agent를 조직의 지식으로 축적하는 업무 맥락 자산화를 검증한다.

# Scope

- Langflow 설치 및 BoI 공통 컴포넌트 제공
- Web 기반 BoI Wiki 제공
- Kafka Event Broker 실제 구동
- Event Adapter가 Kafka 이벤트를 Langflow Webhook 또는 BoI Writer connector로 전달
- 사번 기준 Public, Team, Web Private BoI 조회

# Out of Scope

- Local-only Private BoI의 Web 노출
- 전사 SSO/IAM 완전 연동
- R&D/양산/개발 도메인 자동화
