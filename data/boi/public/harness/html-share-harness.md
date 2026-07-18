---
okf_version: "0.1"
boi_profile_version: "0.1"
harness_version: "1.1.0"
type: boi/harness
title: HTML Share Harness
description: self-contained HTML 문서를 단축주소로 게시할 때의 BoI HTML Profile, 지식 카드, 이름/스코프/tombstone, preview→확인→publish 계약
tags: [BoIWiki, HTML, Share, Shortlink, Harness, MCP]
timestamp: 2026-07-17T00:00:00+09:00
boi_id: boi:public:harness:html-share-harness
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
    ref: harness/html-share-harness.md
review:
  reviewer: agent-curator
  review_status: reviewed
---

# Summary

self-contained HTML 문서(보고서, 대시보드, 가이드 등 무엇이든)를 BoI Wiki 단축주소(`/{name}`)로 게시할 때는 이 하네스를 따른다. Web UI(`/share`)와 MCP 경로(`html_share_*`, `shortlink_*`)는 같은 레지스트리, 같은 이름 정책, 같은 BoI HTML Profile 주입, 같은 지식 카드 계약을 사용한다. 웹 사용자는 하네스를 몰라도 되고, Agent는 반드시 이 계약을 지킨다.

# Self-contained 원칙

- 단일 `.html` 파일, 20MB 이하. CSS/JS/데이터를 모두 인라인한다. 사내망에는 외부 CDN이 없어 외부 `<script src=`/`<link href=` http(s) 참조는 lint warning으로 보고되고 열람자 화면에서 깨질 수 있다.
- 인라인 스크립트는 허용되며 `sandbox="allow-scripts"` iframe과 `Content-Security-Policy: sandbox allow-scripts; frame-ancestors 'self'` + `Referrer-Policy: no-referrer` 응답 헤더로 opaque origin에 격리된다(`frame-ancestors`는 외부 사이트의 iframe 끼워넣기를, `Referrer-Policy`는 referer를 통한 단축주소 유출을 막는다). `allow-same-origin`은 어떤 경우에도 추가 금지 — 업로드된 HTML이 위키 쿠키/세션에 접근할 수 있게 된다.
- api key/token/password로 보이는 비밀 값이 있으면 업로드가 거부된다.

# BoI HTML Profile 계약 (JSON-LD)

저장되는 모든 HTML의 `<head>`에는 단일 `<script type="application/ld+json" id="boi-profile">` 블록이 서버에 의해 주입된다(재업로드 시 기존 블록 교체, 본문은 그대로 보존). 페이로드는 schema.org `DigitalDocument` + Markdown frontmatter와 같은 필드를 담는 `boiProfile` 객체다.

| 필드 | 값 |
|---|---|
| `okf_version` / `boi_profile_version` | `"0.1"` / `"0.1"` |
| `type` | `boi/html-document` |
| `title` / `description` | 업로드 폼/인자 값 (description이 비면 한 줄 자동 생성) |
| `timestamp` | 게시 시각 (KST ISO) |
| `boi_id` | `boi:public:html:{name}` / `boi:team:{team_id}:html:{name}` / `boi:private:{사번}:html:{name}` |
| `visibility` | `public` / `team` / `private` |
| `classification` | `internal` |
| `owner` | private 스코프는 경로 사번과 반드시 일치, team/public은 업로더 라벨 |
| `acl_policy` | `acl:public` / `acl:team:{team_id}` / `acl:private:{사번}` |
| `status` | `reviewed` (`review.reviewer` = 업로더 라벨, `review.review_status: user_confirmed`) |
| `content_role` | `html_artifact` |
| `shortlink` | `/{name}` |
| `source_refs` | 업로드 provenance: `{type: upload, ref: 원본 파일명, uploaded_by: 사번, sha256: 원본 업로드 바이트의 sha256}` |

`okf_lint`는 `data/boi` 아래 모든 `*.html`에 대해 블록 파싱, 필수 필드/enum, 경로↔ACL 일치를 검증한다.

# 이름 / 스코프 / Tombstone 규칙

- 이름: `^[a-z0-9][a-z0-9-]{1,63}$`, 루트 예약어 금지, FCFS 선점. 기본값은 파일명 slug이며 `GET /api/share/names/{name}/availability` 또는 MCP `shortlink_check`로 중복을 확인한다.
- 같은 이름 재업로드/변경은 소유자만 가능하다(타인은 409 + 대안 이름 제시).
- 스코프가 저장 경로를 결정한다: `data/boi/{public|team/{team_id}|private/{사번}}/html/{name}.html`. team 스코프는 팀 멤버십이 필요하다.
- 삭제 = tombstone: 이름은 영구히 재사용 불가(북마크 하이재킹 방지)이며 저장 HTML과 지식 카드가 함께 삭제된다.
- 기존 BoI 문서용 doc-kind 단축주소는 `POST /api/share/links` 또는 MCP `shortlink_register`로 등록하며 이름 정책은 업로드와 동일하다.

# 게시 흐름 (preview → user_confirmed → publish)

1. Preview: `POST /api/share/preview` 또는 MCP `html_share_preview` — 비변경. 본문 검증, 이름 중복, 스코프를 확인하고 게시될 결과를 보여준다.
2. 확인: Agent는 사용자 명시 확인을 받아야 한다. MCP `html_share_publish`와 `shortlink_register`는 `user_confirmed=true`가 없으면 MCP 단계에서 차단된다.
3. Publish: `POST /api/share/html` (Web UI는 multipart, MCP/자동화는 JSON `content_base64`) — BoI HTML Profile 주입, 지식 카드 생성, 레지스트리 갱신, git 커밋, `html.share.published.v1` best-effort 발행이 한 번에 일어난다.

# 지식 카드 계약

- 게시 성공 시 같은 이름의 카드 `data/boi/{scope}/html/{name}.md`가 동기적으로 생성된다. 카드가 정본 `boi_id`를 소유하며(콜론→경로 매핑이 이 `.md`로 해석됨), 전체 OKF frontmatter(`type: boi/html-document`, `status: reviewed`, reviewer, tags `[HTML, Share]`)와 `source_refs` 두 건 — (a) 저장본(주입 후) HTML의 `html_artifact` ref + sha256, (b) 업로드 provenance — 을 담는다.
- 검색, 링크 그래프, 신선도, promotion 루프에는 카드가 들어가고, 카드가 HTML을 대표한다.
- lint가 카드↔HTML 무결성을 강제한다: 카드 누락 또는 sha256 불일치는 오류다.
- 재업로드 시 카드가 재생성되고(최초 생성 시각은 레지스트리에서 보존), 삭제 시 카드도 함께 삭제된다.

# 금지사항

- 외부 http(s) `<script src=`/`<link href=` 참조(사내망에서 깨짐 — 인라인으로 대체, lint warning).
- HTML 본문 내 비밀 값(api key/token/password) 일체.
- sandbox 속성/CSP 헤더의 `allow-same-origin` 추가(코드 주석 + 테스트로 고정).

# Validation

```bash
python scripts/okf_lint.py --root data --strict-media --strict-links
python scripts/check_html_share.py --base-url http://localhost:28000
```

`GET /api/harness/acceptance`에는 `html_share_lint`(Verification)와 `shortlink_registry_integrity`(State) 체크가 포함된다.

# Citations

- Repo source: `harness/html-share-harness.md`
- [BoI Agent API, MCP, Ontology Search Harness](/public/harness/agent-api-mcp-search-harness.md)
