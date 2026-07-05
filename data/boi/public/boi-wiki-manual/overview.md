---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: BoI Wiki Manual Overview
description: BoI Wiki, Workflow/Task Builder, MCP, Harness acceptance, Source Wiki, Local Second Brain, Data Lake artifact, validated editing, OKF media 운영 가이드 진입점
tags: [Manual, BoIWiki, Workflow, Task, MCP, Harness, SourceWiki, LocalSecondBrain, DataLake, OKF]
timestamp: 2026-07-05T22:00:00+09:00
boi_id: boi:public:boi-wiki-manual:overview
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
    ref: harness/README.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

BoI Wiki는 OKF 기반 LLM Wiki와 실행 가능한 workflow runtime을 함께 제공한다. 현재 사용자-facing 작성 모델은 `Workflow / Task`다. 사용자는 `/sops/new`에서 Workflow 전체와 Task 맵을 먼저 잡고, 필요한 Task만 상세화한다. Agent와 외부 client는 [BoI Wiki MCP](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)를 통해 같은 지식을 검색하고 workflow/action/edit 작업을 수행한다.

# Core Manuals

- [BoI Wiki 종합 가이드](/public/boi-wiki-manual/guide/final-operator-guide.md)
- [BoI Wiki MCP 등록과 사용](/public/boi-wiki-manual/mcp/register-and-use-boi-wiki-mcp.md)
- [Multi-action connector guide](/public/boi-wiki-manual/actions/multi-action-connector-guide.md)
- [Langflow connected flow guide](/public/boi-wiki-manual/langflow/connected-flow-guide.md)
- [Workflow/Task Builder Step-by-step](/public/boi-wiki-manual/sop-workflows/workflow-task-builder-step-by-step.md)
- [SOP workflow 작성과 runtime 연결](/public/boi-wiki-manual/sop-workflows/create-and-connect-sop.md)
- [Data Lake Artifact Lifecycle](/public/boi-wiki-manual/data-lake/data-lake-artifact-lifecycle.md)
- [BoI Wiki 활용 사례](/public/boi-wiki-manual/use-cases/sop-flow-visualization.md)
- [Local Private 시작하기](/public/boi-wiki-manual/local-private/overview.md)
- [OKF media와 Browser screenshot 규칙](/public/boi-wiki-manual/media/okf-media-and-screenshots.md)
- [Visibility and Promotion Policy](/public/boi-wiki-manual/operations/visibility-and-promotion-policy.md)
- [Web edit와 Git commit 정책](/public/boi-wiki-manual/operations/draft-and-git-policy.md)
- [NAS SERVICE_TOKEN 운영 절차](/public/boi-wiki-manual/operations/nas-service-token-rotation.md)
- [SSO와 권한 체계](/public/boi-wiki-manual/security/sso-and-permissions.md)
- [BoI Profile ACL 정책](/public/boi-wiki-manual/security/boi-profile-acl-policy.md)
- [팀 RBAC 관리](/public/boi-wiki-manual/security/team-rbac-management.md)
- [Agent Guardrail and ACL](/public/boi-wiki-manual/agent/agent-guardrail-and-acl.md)
- [Pet Agent UX and Artifacts](/public/boi-wiki-manual/agent/pet-agent-ux-and-artifacts.md)
- [Agent Execution and Event Authoring](/public/boi-wiki-manual/agent/agent-execution-and-event-authoring.md)

# Operating Model

1. OKF Markdown 문서와 action/skill catalog가 source of truth다.
2. Source/body 직접 수정은 Web/MCP preview, validation, apply, auto-commit 경로를 사용한다.
3. Team/Public promotion은 사용자 승인과 자동 검증 통과 후 즉시 게시하고 HOTL로 사후 개입한다.
4. Langflow는 실행 채널 중 하나이며 API, Webhook, MCP, Manual, Event Broker action과 같은 수준으로 관리한다.
5. Workflow는 전체 Process, Task는 판단/근거/실행/결과/TAT를 가진 작은 업무 단위다.
6. BoI Agent, MCP, Search, Inbox, Action 실행은 모두 BoI Profile ACL과 팀 RBAC guardrail을 통과한다.
7. Data Lake는 MinIO artifact store이며 OKF에는 원본 파일 대신 URL, profile, sample, checksum, validation metadata만 남긴다.
8. Harness acceptance는 Observation, Context, Control, Action, State, Verification을 API/MCP/test에서 함께 확인한다.
9. Source Wiki와 Local Second Brain은 선택형 overlay다. repo/source wiki refresh, capture inbox, memory review, promotion preflight는 core를 무겁게 만들지 않고 agent가 반복 운영을 돕는 경량 흐름으로 둔다.

# Local Private

Local Private은 개인 PC의 `boi-wiki-local` workspace에만 저장되는 개인 BoI 영역이다. 일반 사용자는 MCP나 Git을 몰라도 agent 하네스가 OKF 구조, lifecycle metadata, self-check, promotion draft/preflight/submit 절차를 수행한다.

- [Codex로 BoI Wiki Local 사용하기](/public/boi-wiki-manual/local-private/codex-setup.md)
- [MCP 없이도 쓰는 BoI Wiki Local](/public/boi-wiki-manual/local-private/mcp-optional.md)
- [Local Private 승격과 공유 절차](/public/boi-wiki-manual/local-private/promotion-flow.md)
- [Private BoI 보관 정책](/public/boi-wiki-manual/local-private/private-lifecycle.md)

# Use Cases

- [SOP Flow Visualization](/public/boi-wiki-manual/use-cases/sop-flow-visualization.md)
- [Workflow/Task Builder Step-by-step](/public/boi-wiki-manual/sop-workflows/workflow-task-builder-step-by-step.md)
- [Event-to-Action Workflow Planning](/public/boi-wiki-manual/use-cases/event-to-action-workflow-planning.md)
- [API Doc to Action Spec](/public/boi-wiki-manual/use-cases/api-doc-to-action-spec.md)
- [Agent Context Pack](/public/boi-wiki-manual/use-cases/agent-context-pack.md)
- [Workflow Simulation](/public/boi-wiki-manual/use-cases/workflow-simulation.md)
- [Langflow Workflow Planning](/public/boi-wiki-manual/use-cases/langflow-workflow-planning.md)

# Citations

- [BoI Agent Harness Overview](/public/harness/overview.md)
- [Public Action Library](/public/actions/overview.md)
