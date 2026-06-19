---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/manual
title: OKF Media and Browser Screenshot Guide
description: OKF bundle 안에서 이미지와 Browser 캡처를 저장, dedupe, manifest, 렌더링, 인용하는 규칙
tags: [Manual, OKF, Media, Browser, Screenshot]
timestamp: 2026-06-18T15:25:00+09:00
boi_id: boi:public:boi-wiki-manual:media:okf-media-and-screenshots
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: okf-spec
    ref: https://raw.githubusercontent.com/GoogleCloudPlatform/knowledge-catalog/main/okf/SPEC.md
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

OKF v0.1은 이미지 asset 전용 규칙을 정의하지 않는다. BoI Wiki에서는 이미지를 concept가 아닌 bundle-local asset으로 두고, 중요한 이미지는 별도 media reference BoI 문서로 설명한다.

# Storage Rule

이미지는 `_media/` 아래에만 둔다.

```text
data/boi/public/boi-wiki-manual/_media/browser/{page-slug}/{yyyyMMdd-HHmmss}-{semantic-slug}-{width}x{height}-{sha256_12}.png
```

사용자가 제공한 원본 SOP 이미지나 업무 문서는 evidence source로 취급한다. 원본은 에이전트가 재생성하지 않고 `_media/source/{source-slug}/...`에 보존한 뒤, OCR/요약/재구성 결과와 분리해 인용한다.

# Manifest Rule

각 `_media` root에는 `media-manifest.yaml`을 둔다. 항목에는 `path`, `sha256`, `captured_url`, `captured_at`, `viewport`, `source_kind`, `related_doc`, `created_by`를 기록한다.

# Markdown Rule

문서에는 표준 Markdown image syntax만 쓴다.

```markdown
![Workflow Status 화면](/public/boi-wiki-manual/_media/browser/workflow-status/example.png)
```

# Dedupe Rule

같은 sha256 이미지가 이미 있으면 재사용한다. 같은 hash가 다른 파일명으로 중복 저장되면 strict media lint에서 실패한다.

# Browser Evidence Targets

- BoI Wiki Explorer folder navigation
- SOP detail
- Source/Draft editor
- Workflow Status
- Action Raw detail
- BoI Wiki MCP check result
- Langflow connected canvas

# Example

![BoI Wiki Explorer with OKF media](/public/boi-wiki-manual/_media/browser/boi-wiki-explorer/20260619-150927-boi-wiki-explorer-current-1440x1000-bbb0010f80d7.png)

# Citations

- [BoI Wiki Manual Overview](/public/boi-wiki-manual/overview.md)
