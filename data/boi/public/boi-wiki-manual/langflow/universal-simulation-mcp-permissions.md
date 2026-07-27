---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: MCP 미리보기와 BoI Action 저장 권한의 차이
description: Langflow API Key, BoI PAT, Action run token의 역할과 저장 가능 범위
tags: [Manual, Security, MCP, Action, PAT]
timestamp: 2026-07-27T15:25:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-permissions
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: langflow/custom_components/boi/boi_wiki_save.py
  - type: repo
    ref: boi_api/app/agent_playground_credentials.py
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 세 자격의 역할

| 자격 | 누가 준비하나 | 용도 |
|---|---|---|
| Langflow API Key | 사용자가 Langflow에서 발급 | Playground·Agent Hub·MCP client가 개인 endpoint와 Flow에 접근 |
| BoI PAT | Playground가 자동 발급 | 개인 개발 중 Langflow가 내 권한으로 Wiki·Ontology를 조회 |
| Action run token | BoI가 실행마다 발급 | 공유 Action 호출자의 Wiki 조회·개인 초안 권한 |

API Key 하나로 모든 사용자의 Wiki 권한이 결정되는 것이 아니다. 공유 Action은 endpoint 소유자의 API Key로 Langflow Flow를 호출하지만 Wiki 조회와 초안 소유자는 실제 호출자의 1회성 run token으로 결정한다.

# 저장 정책

- 외부 MCP: preview만 가능
- Playground preview: Wiki 변경 없음
- Playground private draft: 현재 로그인 사용자에게 묶인 단기 run token 필요
- BoI Action private draft: Action 호출자에게 묶인 단기 run token 필요

token이 없거나 Action·Flow·trace·execution audience가 다르면 저장하지 않는다.
