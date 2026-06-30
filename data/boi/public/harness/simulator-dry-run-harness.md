---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/harness
title: Simulator Dry Run Harness
description: Langflow Universal Simulator를 dry-run/PoC 도구로 검증하는 기준
tags: [BoIWiki, Langflow, Simulator, Harness]
timestamp: 2026-06-30T00:00:00+09:00
boi_id: boi:public:harness:simulator-dry-run-harness
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
    ref: harness/simulator-dry-run-harness.md
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Simulator Dry Run Harness

Langflow Universal Simulator는 실행 전 확인, PoC, 외부 시스템이 없는 local demo용이다. 검증된 Inbox 보고서의 기본 evidence source가 아니다.

Simulator output은 `시뮬레이션 결과`로 표시한다. dry-run/PoC 실패는 해당 검증을 실패시킬 수 있지만 `/inbox` 렌더링이나 이미 materialized된 report 조회를 막으면 안 된다.

```bash
python scripts/check_langflow_universal_simulator.py --langflow-url http://localhost:7860 --boi-api-url http://localhost:28000
```
