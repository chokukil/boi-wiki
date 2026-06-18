---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Web Draft and Git Commit Policy
description: Web/MCP 저장은 draft-only이고 agent가 validation 후 원본 반영과 Git commit을 수행하는 정책
tags: [Manual, Draft, Git, Validation]
timestamp: 2026-06-18T15:30:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:draft-and-git-policy
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

Web UI와 MCP tool에서 저장한 내용은 draft queue에만 들어간다. 원본 Markdown/YAML 변경과 Git commit은 Codex/Claude 같은 agent가 검증 후 수행한다.

# Apply Flow

1. draft와 `base_sha256`을 확인한다.
2. target file hash가 여전히 같은지 확인한다.
3. source validation, OKF lint, catalog validation, secret scan을 실행한다.
4. 변경을 적용한다.
5. focused tests와 runtime smoke를 실행한다.
6. Git commit을 만든다.

# Citations

- [Web Draft Editing Guide](/public/harness/web-draft-editing-guide.md)
