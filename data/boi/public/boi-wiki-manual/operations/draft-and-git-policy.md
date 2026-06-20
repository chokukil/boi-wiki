---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Source Edit and Git Commit Policy
description: Source/body 직접 수정은 preview, validation, apply, auto-commit을 사용하고 Team/Public promotion은 별도 publish 경로를 사용하는 정책
tags: [Manual, Edit, Git, Validation]
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

Web UI와 MCP의 source/body 직접 수정은 사용자 승인 후 preview, validation, apply, auto-commit 경로를 사용한다. 원본 Markdown/YAML 변경은 검증을 통과하고 Git commit까지 성공해야 완료된다. Team/Public promotion은 이 source/body edit 경로가 아니라 사용자 승인, 원격 동기 검증, 즉시 게시, HOTL 사후 개입 경로를 사용한다.

# Apply Flow

1. `base_sha256`과 target file hash가 여전히 같은지 확인한다.
2. Markdown preview를 생성하고 source validation, OKF lint, catalog validation, secret scan을 실행한다.
3. 오류가 있으면 파일 변경 없이 validation feedback과 수정 제안을 반환한다.
4. 사용자가 적용을 승인하면 같은 검증을 다시 실행한다.
5. 변경을 적용하고 post-apply validation을 실행한다.
6. Git commit을 만든다.
7. validation 또는 commit 실패 시 파일을 rollback한다.

# Promotion Exception

`promotion_submit`은 source/body edit apply tool이 아니다. 사용자가 preview를 보고 명시 승인한 Team/Public promotion candidate는 원격 자동 검증을 통과하면 즉시 게시된다. 검증 실패 시 파일 생성과 게시 없이 validation report만 반환한다.

# Citations

- [Web Validated Editing Guide](/public/harness/web-draft-editing-guide.md)
- [Visibility and Promotion Policy](/public/boi-wiki-manual/operations/visibility-and-promotion-policy.md)
