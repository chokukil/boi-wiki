---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Local Private 시작하기
description: 일반 사용자가 Codex, Claude, Cursor로 개인 로컬 BoI Wiki workspace와 Local Second Brain을 쓰는 방법
tags: [Manual, LocalPrivate, BoIWikiLocal, Agent, LocalSecondBrain]
timestamp: 2026-07-05T22:00:00+09:00
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

Local Private은 개인 PC의 agent가 사용하는 로컬 BoI workspace다. Web BoI Wiki에는 보이지 않고, 사용자가 명시적으로 승인한 sanitized promotion candidate만 원격 검증/게시 절차로 넘어간다.

사용자는 매번 폴더 구조를 읽을 필요가 없다. agent가 capture inbox에 임시 메모를 받고, 업무 BoI로 나누고, memory 후보와 cleanup 후보를 보여주며, 공유가 필요할 때만 promotion preflight를 만든다.

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

MCP가 연결되어 있으면 agent는 shared BoI Wiki의 SOP, Event Type, Action Spec, Workflow Status를 검색할 수 있다. MCP가 없어도 Local Private 작성은 계속 동작한다. 공식 경로는 skills-first local workspace이며 local MCP 서버는 요구하지 않는다.

# Typical Requests

- `설비 이상 대응 SOP를 Mermaid 프로세스 플로우로 그려줘`
- `이 이벤트가 발생하면 어떤 SOP와 Action이 이어지는지 알려줘`
- `기존 API 문서를 BoI Action Spec 초안으로 만들어줘`
- `원격 BoI Wiki를 검색해서 이번 업무용 context pack을 만들어줘`
- `MCP 설정은 모르겠으니 local만 써줘`
- `방금 복사한 메모를 capture inbox에 넣고 업무 BoI 후보로 정리해줘`
- `이번 주 내 local memory 후보와 정리 후보를 보여줘`
- `이 문서를 팀 문서로 올리기 전에 promotion preflight만 먼저 보여줘`

# Local Automation

agent는 가능하면 다음 경량 helper를 사용한다.

| Helper | 역할 |
|---|---|
| `scripts/local_capture.py` | 임시 메모를 Local Private capture 후보로 저장 |
| `scripts/local_review.py` | memory 후보, stale/duplicate 후보, cleanup preview, promotion 후보 산출 |
| `scripts/promotion_preflight.py` | 원격 제출 전 local-only preview와 민감정보/source_refs 확인 |

이 helper들은 서버, DB, Docker가 없어도 동작한다. 원격 BoI Wiki와 붙을 때는 MCP/API URL과 service token 설정만 개인 환경에 둔다.

# Citations

- [Local Private Agent Harness](/public/harness/local-private-agent-harness.md)
- [MCP Optional Guide](/public/boi-wiki-manual/local-private/mcp-optional.md)
- [Promotion Flow](/public/boi-wiki-manual/local-private/promotion-flow.md)
- [BoI Wiki Use Cases](/public/boi-wiki-manual/use-cases/sop-flow-visualization.md)
- [BoI Wiki 종합 가이드](/public/boi-wiki-manual/guide/final-operator-guide.md)
