---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Langflow 프로젝트를 MCP 도구로 연결하기
description: 대표 Flow를 streamable HTTP MCP 도구로 노출하고 실제 호출하는 방법
tags: [Manual, Langflow, MCP, APIKey]
timestamp: 2026-07-27T15:10:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:universal-simulation-mcp-connect
visibility: public
classification: internal
owner: AIX 확산 TF
author: {type: agent, agent_id: codex}
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: boi_api/app/agent_playground.py
  - type: repo
    ref: langflow/compatibility-manifest.json
review:
  reviewer: tf-lead
  review_status: reviewed
---

# 연결 절차

1. Playground에서 대표 Flow를 선택한다.
2. `MCP 도구 준비`를 누른다.
3. API Key 인증과 tool 이름 `boi_universal_simulate`를 확인한다.
4. `실제 MCP 호출`로 `list_tools`와 tool call을 함께 시험한다.
5. 외부 client에는 표시된 streamable HTTP URL과 개인 Langflow API Key를 등록한다.

```json
{
  "transport": "streamable_http",
  "url": "https://langflow.example/api/v1/mcp/project/PROJECT_ID/streamable",
  "headers": {
    "x-api-key": "${LANGFLOW_API_KEY}"
  }
}
```

실제 키는 문서나 설정 예시에 적지 않는다. 외부 MCP는 프로젝트 소유자 권한으로 조회하고 결과 후보만 반환한다. `private_draft`를 요청해도 Action run token이 없으면 저장하지 않는다.

# Python MCP 파일과의 차이

사내 FastMCP Python 파일 자체를 Langflow에 업로드하지 않는다. 파일의 tool 입력·출력 계약을 검토한 뒤 `boi.agent-slot.v1` custom Component로 변환하고 read-only extension bundle로 제공한다. Langflow 소스와 기본 화면은 수정하지 않는다.
