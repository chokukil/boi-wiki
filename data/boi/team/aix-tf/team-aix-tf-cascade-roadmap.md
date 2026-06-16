---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: TM CEO AIX 확산 TF Cascade와 업무 맥락 자산화 PoC Roadmap
description: 이천 포럼 메시지를 AIX 확산 TF 실행 과제와 2개월 PoC 범위, 향후 로드맵으로 연결한 경영진 보고용 BoI
tags: [AIX, PoC, Roadmap, Executive, BoIWiki]
timestamp: 2026-06-17T09:00:00+09:00
boi_id: boi:team:aix-tf:cascade-roadmap-v0.1
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
  - type: transcript
    ref: 곽노정_CEO_대화.txt
  - type: transcript
    ref: 최태원_회장_대화.txt
  - type: planning
    ref: ChatGPT/Codex planning discussion
review:
  reviewer: tf-lead
  reviewed_at: 2026-06-17T09:00:00+09:00
  review_status: reviewed
---

# Summary

TM → CEO → AIX 확산 TF의 메시지는 하나로 연결된다.

- TM: 개인 AI 활용만으로는 회사 성과가 되지 않으며, 먼저 "우리 일"을 정의하고 조직을 이해하는 AI 활용 환경이 필요하다.
- CEO: DT가 데이터를 연결했다면, AI는 판단과 실행을 연결해야 하며 SK하이닉스는 AI Native Memory Creator로 진화해야 한다.
- AIX 확산 TF: 구성원이 각자 쓰는 Claude, ChatGPT, M365 Copilot, Langflow, Custom Agent가 회사 방식으로 일하도록 Agent Harness와 BoI Wiki 공통 기반을 제공한다.

# PoC Name

1인 1 Agent를 조직의 지식으로 축적하는 업무 맥락 자산화 PoC

# 2개월 PoC 범위

이번 2개월 PoC는 경영진 방향성과 Align해야 할 전체 과제 중에서 가장 먼저 필요한 최소 공통 기반을 검증한다.

| 범위 | 내용 |
|---|---|
| Agent Harness | AI에게 쥐어주는 SK하이닉스 업무 가이던스, Private-first, 출처/권한/승격 원칙 |
| BoI Wiki | OKF 기반 SK하이닉스형 업무 맥락 저장소, Public/Team/Private 구조 |
| Langflow | 사내 Agent Builder 역할, BoI 공통 컴포넌트와 Webhook 실행 채널 |
| Event Broker | Kafka 기반 업무 이벤트 Trigger, meeting/action/report/SOP workflow 이벤트 |
| Action Gateway | BoI Writer, Langflow, API, Webhook, MCP를 동등한 peer connector로 실행 |
| Demo | 회의/보고/Action 및 설비 이상 SOP workflow를 실제 이벤트와 BoI로 검증 |

# Roadmap

| Phase | 초점 | 주요 항목 |
|---|---|---|
| Now: 2개월 PoC | 업무 맥락 자산화 최소 구조 검증 | Agent Harness v0.1, BoI Wiki Profile v0.1, Langflow Reference Flow, Event Broker, Private → Team/Public draft 승격 |
| 2026 H2 | 확산 운영모델 정립 | 3~5개 팀 Pilot, BoI Curator 역할, Event Catalog 초안, CSP별 적용 패턴, 보안/검토 체크리스트 |
| 2027 | 기능 조직 확산 | Staff 업무 고도화, R&D BoI Wiki, 개발 Agentic AI, 고객 요구 변경 BoI, AI 교육/인증, Langflow Template Library |
| 2028+ | Enterprise Agentic Operating Model | 전사 Event Broker, Enterprise Knowledge Graph, Agentic Workflow, Digital Twin/Operational Physical AI, Management Intelligence |

# Executive Message

Agent는 각자 만들지만, 지식은 회사 방식으로 쌓이게 한다.

이번 PoC는 Claude, ChatGPT, M365 Copilot, Langflow 중 어느 하나를 대체하거나 특정 도구를 강제하는 프로젝트가 아니다. 실행 채널은 계속 바뀔 수 있다. 유지되어야 하는 것은 Event Type, BoI Wiki, Agent Harness, 권한/출처/승격 원칙이다.
