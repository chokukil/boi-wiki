---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Agent Playground 문제 해결
description: 연결, Agent Hub 배포, Component, Flow drift와 Action 오류 해결 절차
tags: [Manual, AgentPlayground, Troubleshooting]
timestamp: 2026-07-27T09:00:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:agent-playground-troubleshooting
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: docs/AGENT_PLAYGROUND_INTEGRATION.md
  - type: boi
    ref: boi:public:boi-wiki-manual:langflow:agent-playground-onboarding
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 연결 오류

| 표시 | 해결 방법 |
|---|---|
| API Key 오류 | Langflow에서 새 Key를 발급하고 endpoint Key만 교체한다. |
| 사용자 불일치 | 현재 SSO 사번의 Langflow 사용자가 발급한 Key인지 확인한다. |
| 버전 불일치 | 지원 범위 `>=1.11.0,<1.12.0`인지 확인한다. |
| 자동 준비 실패 | 같은 endpoint에서 다시 실행해 실패 단계부터 이어간다. |
| bundle 확인 실패 | 운영자에게 read-only custom component mount 상태를 요청한다. |

# Agent Hub 배포 오류

- endpoint에는 브라우저용 `/builder` 경로가 아니라 안내된 host-root URL을 사용한다.
- Agent Hub와 Playground의 Key는 자동 동기화되지 않는다.
- 배포 결과를 찾지 못하면 선택한 endpoint와 `boi-{사번}` 프로젝트가 같은지 확인한다.
- Agent Hub 자체 기능 변경이 필요해 보이면 패치하지 말고 운영 담당자에게 계약 변경을 요청한다.

# Flow·Component 오류

- `연결 필요`: `boi.agent-slot.v1` 계약이면 자동 연결하고 아니면 Canvas에서 직접 연결한다.
- `실행 검증 안 됨`: Component가 Chat Input부터 Save까지 실제 실행 경로에 있는지 확인한다.
- `Flow 변경 감지`: checksum drift다. 현재 graph로 전체 검증을 다시 수행한다.
- `Ontology 관계 없음`: 문서 fallback 여부와 부족 근거를 확인한다.

# 공유하면 안 되는 값

- Langflow API Key
- `BOI_WIKI_PAT`
- `boi_run_*` 실행 token
- 모델 API Key
- 비밀값이 포함된 네트워크 payload와 화면 캡처
