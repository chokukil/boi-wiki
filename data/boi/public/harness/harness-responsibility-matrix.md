---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Harness Responsibility Matrix
description: BoI Wiki harness runtime responsibilities and verification boundaries
tags:
  - Harness
  - Agent
  - MCP
  - ActionGateway
  - Verification
timestamp: "2026-07-05 00:00:00+09:00"
boi_id: boi:public:harness:harness-responsibility-matrix
visibility: public
classification: internal
owner: aix-tf
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
review:
  reviewer: harness-curator
  review_status: reviewed
source_refs:
  - type: external-reference
    ref: https://revfactory.github.io/harness-paper/
  - type: repo
    ref: harness/harness-responsibility-matrix.md
---

# Harness Responsibility Matrix

BoI Wiki는 core를 OKF Markdown/JSONL로 가볍게 유지하고, API/MCP/Action Gateway에서 강한 실행면을 제공한다. 아래 matrix는 agent, DT Platform 담당자, Legacy System 담당자가 같은 경계를 보도록 하는 기준이다.

| Responsibility | BoI contract | Primary surfaces | Verification |
|---|---|---|---|
| Observation | 사용자 요청, 현재 페이지, runtime event, artifact, 보이는 Inbox task를 모으되 raw log를 사용자-facing 보고서에 섞지 않는다. | Web UI, BoI API, MCP `ontology_search`, `boi_inbox`, `work_context_get` | Inbox report tests, WorkContextPack tests, OKF lint |
| Context | OKF Markdown/JSONL이 core source다. Data Lake artifact와 Legacy DB Demo는 선택형 evidence overlay다. | OKF docs, Data Lake artifact API, private/team/public ACL | Data Lake disabled/enabled smoke, ACL tests |
| Control | plan/preview/draft와 apply/submit/execute를 분리한다. 제약은 prompt가 아니라 서버 validator에 pinning한다. | API validators, MCP wrappers, Web forms, RBAC checks | mutation confirmation tests, RBAC audit tests |
| Action | 실제 외부 작업은 Action Gateway allowlist와 approval policy를 지난다. `user_confirmed`와 high-risk `approved_by`를 구분한다. | Action Gateway, Event Router, MCP `action_invoke`, Agent execution cards | Action catalog tests, high-risk approval tests |
| State | runtime 변경과 판단은 append-only log/artifact로 남긴다. raw ID는 내부/diagnostic에만 둔다. | Action logs, Event Stream, artifact attachments, Inbox history | append-only tests, raw-ID visibility tests |
| Verification | public scenario마다 좁은 자동 테스트와 optional overlay 없이도 실행되는 smoke command를 둔다. | pytest, scripts, compose profiles, local workspace check | final acceptance suite and compose config smoke |
| Science Source Curation | exact Source version, locator, quote hash, translation, claim scope, ACL, 별도 Admin review를 보존한다. | OKF Science Source/Evidence, Admin review UI/API | source reachability, digest, scope, self-approval tests |
| Science Knowledge Authoring | Dictionary/Ontology 해석과 atomic Knowledge, locator-bound Evidence 역할을 분리한다. | sci-profile Knowledge, Ontology bindings, EvidenceUse | atomicity, overclaim, applicability, version tests |
| Science Rule Qualification | deterministic Rule마다 실제 과학 주장 열 가지를 실행한 뒤 독립 sealed holdout을 수행한다. | candidate RuleSet, qualification matrices, release preflight | five-verdict, false-red, ambiguity, candidate-authority tests |
| Science Verification | untrusted interpretation을 verdict authority 밖에 두고 Web/REST/MCP/export가 한 report를 공유한다. | Science Verifier canvas, REST/MCP, Markdown/PDF | anchor, confirmation, evidence visibility, parity, restart tests |

# Guardrail Defaults

- Preview tool은 confirmation 전에 가능 여부와 blocker를 보여줄 수 있다.
- Submit, apply, publish, workflow start, real action invoke, evidence adoption은 `user_confirmed=true`가 필요하다.
- High-risk Action Gateway 호출은 별도 `approved_by`가 필요할 수 있으며, `user_confirmed`는 승인자를 대체하지 않는다.
- UI는 Inbox task에 opaque public ref를 사용한다. raw request/action/trace ID는 API 응답, audit log, diagnostics에만 둔다.
- Langflow는 connector/debug backend다. Native BoI Agent와 BoI API/MCP가 production contract다.
