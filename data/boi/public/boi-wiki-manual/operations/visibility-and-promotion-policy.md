---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: Visibility and Promotion Policy
description: Public, Team, Private, Local Private BoI의 접근 범위와 사용자 승인 기반 승격/HOTL 운영 정책
tags: [Manual, Visibility, Promotion, HOTL, LocalPrivate]
timestamp: 2026-06-19T22:30:00+09:00
boi_id: boi:public:boi-wiki-manual:operations:visibility-and-promotion-policy
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
    ref: boi:public:boi-wiki-manual:operations:draft-and-git-policy
  - type: boi
    ref: boi:public:boi-wiki-manual:local-private:promotion-flow
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

BoI Wiki는 source/body edit apply와 promotion publish를 분리한다. Web/MCP source/body 직접 수정은 사용자 승인 후 preview, 자동 검증, apply, Git commit을 통과해야 완료된다. Team/Public 승격은 사용자 명시 승인과 자동 검증을 통과하면 즉시 게시한다. 품질과 정책 판단은 사전 전수 승인 대신 HOTL로 운영한다.

# Visibility

| Visibility | Scope | Default handling |
|---|---|---|
| Private | 본인 Web BoI Wiki | 기본 저장 위치이며 자동 공유하지 않는다. |
| Team | 사번의 Team ACL | 사용자 승인과 자동 검증 통과 시 즉시 게시한다. |
| Public | 전 구성원 | 사용자 승인과 자동 검증 통과 시 즉시 게시하고 HOTL이 사후 개입한다. |
| Local Private | 개인 PC의 `boi-wiki-local` | Web BoI Wiki에 보이지 않으며, 원문은 사용자 승인 없이 전송하지 않는다. |

# Promotion Flow

1. agent가 local promotion draft 또는 Web Private 공유본을 만든다.
2. agent가 민감정보, 출처, 공개 범위, preview/diff, local preflight 결과를 보여준다.
3. 사용자가 명시적으로 승인한다.
4. agent가 MCP `promotion_submit` 또는 Web promotion API를 호출한다.
5. 원격 BoI Wiki가 동기 자동 검증을 실행한다.
6. 검증 실패 시 파일 생성과 게시 없이 validation report를 반환한다.
7. 검증 통과 시 Team/Public 문서를 즉시 게시하고 promotion status report를 기록한다.

# Direct Edit Flow

1. 사용자가 Web editor에서 `Preview / Validate`를 누르거나 agent가 MCP preview tool을 호출한다.
2. BoI Wiki가 `base_sha256`, Markdown/YAML 구조, OKF lint, catalog validation, secret scan을 확인한다.
3. 오류가 있으면 파일 변경 없이 validation feedback과 수정 제안을 반환한다.
4. 사용자가 승인하면 Web `Apply & Commit` 또는 MCP apply tool이 같은 검증을 다시 실행한다.
5. 검증 통과 시 파일을 적용하고 post-apply validation 후 Git commit을 만든다.
6. validation 또는 commit 실패 시 파일을 rollback하고 성공으로 처리하지 않는다.

# HOTL

즉시 게시된 문서는 `status: reviewed`, `review.review_status: user_confirmed`, `hotl.status: watching`으로 시작한다. curator 또는 owner는 사후에 `hidden`, `needs_revision`, `rolled_back`으로 개입할 수 있다. `status: approved`는 curator 또는 owner의 명시 검토 후에만 사용한다.

# Validation

원격 검증은 최소한 OKF metadata, target visibility, source_refs, reviewer, secret/token 패턴, Team/Public ACL을 확인한다. Direct edit 검증은 여기에 source hash, Markdown/YAML parse, OKF link/media lint, catalog 구조를 더한다. 검증 실패는 공유/수정 실패가 아니라 적용 전 차단이며, agent가 수정안을 만들고 사용자의 재승인을 받은 뒤 다시 submit/apply한다.

# Citations

- [Web Edit and Git Commit Policy](/public/boi-wiki-manual/operations/draft-and-git-policy.md)
- [Local Private 승격과 공유 절차](/public/boi-wiki-manual/local-private/promotion-flow.md)
