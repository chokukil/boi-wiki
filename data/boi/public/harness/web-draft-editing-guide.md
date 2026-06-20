---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Web Validated Editing Guide
description: BoI Wiki source/body 직접 수정은 preview, validation, apply, auto-commit을 쓰고 promotion publish는 별도 경로를 쓰는 절차
tags: [Harness, Edit, Git, Review]
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

BoI Wiki Web 편집과 MCP source/body apply tool은 사용자 승인 후 원본 Markdown/YAML에 바로 반영되는 경로다. 변경은 preview, source validation, OKF lint, catalog validation, secret scan을 통과해야 하며, 적용 후 자동 Git commit까지 성공해야 완료된다. 실패하면 원본은 유지되고 validation feedback과 수정 제안만 반환된다.

# User Flow

1. 문서나 source 화면에서 내용을 수정하거나 MCP preview tool을 호출한다.
2. `Preview / Validate`로 Markdown preview와 validation feedback을 확인한다.
3. 필요하면 수정 제안을 반영하고 다시 검증한다.
4. 사용자가 승인하면 `Apply & Commit` 또는 MCP apply tool을 실행한다.
5. 완료 상태와 commit hash를 확인한다.

# Agent Flow

1. `base_sha256`과 현재 파일 hash를 비교한다.
2. Markdown preview, Markdown/YAML validation, OKF lint, catalog validation, secret scan을 실행한다.
3. validation 실패 시 파일을 변경하지 않고 오류와 수정 제안을 반환한다.
4. validation 통과 시 파일을 적용한다.
5. post-apply validation과 Git commit을 실행한다.
6. commit 실패 시 파일을 rollback하고 실패 상태를 반환한다.

# Promotion Path

`promotion_submit`은 source/body edit apply tool이 아니다. 사용자가 preview를 명시 승인한 Team/Public promotion candidate는 원격 검증 실패 시 게시되지 않고, 검증 통과 시 즉시 게시되며 `hotl.status: watching`으로 시작한다.

# Citations

- [Harness Overview](/public/harness/overview.md)
