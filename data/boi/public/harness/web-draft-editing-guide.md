---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Web Draft Editing Guide
description: BoI Wiki Web 수정이 draft-only이며 agent 검증 후 반영/commit되는 절차
tags: [Harness, Draft, Git, Review]
timestamp: 2026-06-18T00:46:00+09:00
boi_id: boi:public:harness:web-draft-editing-guide
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
    ref: harness/web-draft-editing-guide.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

BoI Wiki Web 편집과 MCP draft tool은 원본 Markdown/YAML을 바로 바꾸지 않는다. `Save Draft`는 draft queue에 제안만 저장하며, 실제 파일 반영과 Git commit은 Codex, Claude 같은 agent가 수행한다.

# User Flow

1. 문서나 source 화면에서 내용을 수정하거나 MCP draft tool을 호출한다.
2. `Save Draft`를 누른다.
3. 화면의 상태가 `not applied · not committed`임을 확인한다.
4. agent에게 draft 적용을 요청한다.

# Agent Flow

1. draft의 `base_sha256`과 현재 파일 hash를 비교한다.
2. Markdown/YAML validation, OKF lint, catalog validation, secret scan을 실행한다.
3. 필요한 테스트와 smoke 검증을 수행한다.
4. 파일을 적용하고 Git commit을 만든다.
5. draft status에 `applied_by`, `applied_at`, `commit_hash`를 기록한다.

# Citations

- [Harness Overview](/public/harness/overview.md)
