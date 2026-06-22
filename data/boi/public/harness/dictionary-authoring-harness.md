---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Dictionary Authoring Harness
description: 반도체/품질/설비/AI Native Workflow dictionary term을 추가하거나 승격할 때 agent가 따라야 하는 작성 기준
tags:
  - Harness
  - Dictionary
  - OntologySearch
  - Agent
timestamp: "2026-06-23 10:00:00+09:00"
boi_id: boi:public:harness:dictionary-authoring-harness
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
  - type: repo
    ref: tests/test_public_dictionary_quality.py
  - type: boi
    ref: boi:public:harness:agent-api-mcp-search-harness
---

# Summary

Dictionary는 BoI Agent가 현장 용어, 약어, 도메인 표현을 SOP/Event/Action/BoI 관계로 해석하기 위한 public/team/private vocabulary layer다.

이 하네스는 Codex, Claude, Cursor, Langflow Agent, custom agent가 dictionary term을 만들 때 같은 품질 기준을 따르게 한다. 단순 tag 목록이 아니라 OKF Markdown link graph와 BoI Profile mapping을 함께 만든다.

# Scope

Dictionary term을 추가하거나 수정할 때는 먼저 scope를 정한다.

| Scope | 저장 위치 | 사용 기준 |
|---|---|---|
| Private | `data/boi/private/{employee_id}/dictionary/*.md` | 개인 표현, 팀 검증 전 현장 약어, 개인 memory 보조 |
| Team | `data/boi/team/{team_id}/dictionary/*.md` | 팀 내 합의된 업무/설비/품질 표현 |
| Public | `data/boi/public/dictionary/*.md` | 여러 팀 agent가 공통으로 써야 하는 curated seed vocabulary |

동일 용어가 여러 scope에 있으면 해석 우선순위는 `private -> team -> public`이다.

# Required Fields

모든 `boi/dictionary-term`은 다음 field를 갖는다.

| Field | 기준 |
|---|---|
| `term` | canonical 용어. Agent 답변과 search knowledge panel에 표시된다. |
| `definition` | 한 문장으로 업무 의미를 설명한다. |
| `aliases` | 한글/영문/약어/현장 표현을 모두 넣는다. |
| `domain` | `quality`, `spc`, `equipment`, `process-module`, `advanced-packaging`, `ai-native-workflow` 같은 검색 분류. |
| `examples` | 실제 업무 문장 1개 이상. |
| `related_terms` | 다른 dictionary term 이름 1개 이상. |
| `source_refs` | repo, BoI, 공식 문서, 외부 reference 중 최소 1개. |

Public term은 `visibility: public`, `status: reviewed`, `acl_policy: acl:public`이어야 한다.

# Link Graph Rule

OKF에서 중요한 것은 metadata만이 아니라 Markdown link다.

모든 dictionary term 본문에는 다음 섹션을 둔다.

- `# Summary`
- `# BoI Usage`
- `# Agent Notes`
- `# Related Dictionary Terms`
- `# Citations`

`# Related Dictionary Terms`는 `related_terms` metadata를 실제 Markdown 링크로 표현한다. 예를 들어 [HBM](/public/dictionary/hbm.md)은 [TSV](/public/dictionary/tsv.md), [Hybrid Bonding](/public/dictionary/hybrid-bonding.md), [Advanced Packaging](/public/dictionary/advanced-packaging.md)으로 링크한다.

앱 route나 raw log URL은 dictionary graph edge가 아니다. 실행 증거는 Event Stream, Action Raw, Workflow Status에서 다룬다.

# Mapping Rule

Dictionary는 실행 권한을 주지 않지만, 용어 해석을 Event/Action/SOP 후보로 확장할 수 있다.

| Mapping | 사용 기준 |
|---|---|
| `maps_to_event_type` | 용어가 특정 event trigger 또는 workflow stage와 강하게 연결될 때만 사용 |
| `maps_to_action_key` | 용어가 특정 action spec 또는 manual handoff와 직접 연결될 때만 사용 |
| `maps_to_sop` | 용어가 특정 SOP의 기준 context일 때만 사용 |

mapping은 반드시 실제 catalog나 BoI로 resolve되어야 한다. 근거가 약하면 `related_terms`와 Markdown link만 둔다.

# Public Seed Categories

Public dictionary는 최소 다음 범주를 유지한다.

- Semiconductor objects: [Fab](/public/dictionary/fab.md), [Wafer](/public/dictionary/wafer.md), [Lot](/public/dictionary/lot.md), [Die](/public/dictionary/die.md)
- Process modules: [Etch](/public/dictionary/etch.md), [Lithography](/public/dictionary/lithography.md), [Deposition](/public/dictionary/deposition.md), [CMP](/public/dictionary/cmp.md)
- Quality/SPC: [SPC](/public/dictionary/spc.md), [Control Chart](/public/dictionary/control-chart.md), [Cpk](/public/dictionary/cpk.md), [Out-of-Control](/public/dictionary/out-of-control.md)
- Evidence: [Response Trend](/public/dictionary/response-trend.md), [Map View](/public/dictionary/map-view.md), [Cross-section Inspection](/public/dictionary/cross-section-inspection.md)
- Equipment/operations: [Equipment](/public/dictionary/equipment.md), [Alarm](/public/dictionary/alarm.md), [FDC](/public/dictionary/fdc.md), [Root Cause Analysis](/public/dictionary/root-cause-analysis.md)
- Memory/package: [HBM](/public/dictionary/hbm.md), [TSV](/public/dictionary/tsv.md), [Hybrid Bonding](/public/dictionary/hybrid-bonding.md)
- Workflow: [Event Broker](/public/dictionary/event-broker.md), [Action Gateway](/public/dictionary/action-gateway.md), [Manual Handoff](/public/dictionary/manual-handoff.md), [Approval](/public/dictionary/approval.md)

# Agent Workflow

1. 사용자의 용어를 그대로 검색하기 전에 `dictionary_resolve`를 호출한다.
2. 이미 private/team/public dictionary에 있으면 기존 term을 갱신하거나 관련 문서만 추가한다.
3. 없으면 가장 좁은 scope에 초안을 만든다. Public 승격은 curated seed vocabulary로 가치가 있을 때만 한다.
4. 용어 정의는 공식 reference, 기존 SOP/Event/Action 문서, 팀 지식을 근거로 쓴다.
5. `related_terms`를 metadata에 넣고 본문 `# Related Dictionary Terms`에 실제 Markdown links로 반복한다.
6. `maps_to_*`는 실제 catalog/BoI로 resolve될 때만 넣는다.
7. `index.md`를 갱신한다.
8. 저장 전 self-check와 repository test를 실행한다.

# Quality Gates

Public dictionary 변경 후 최소 검증:

```bash
pytest tests/test_public_dictionary_quality.py -q -s
python scripts/okf_lint.py --root data --include-logs --strict-media --strict-links
pytest tests/test_boi_api_routes.py -q -s -k "ontology_search or dictionary or boi_agent"
```

품질 게이트는 다음을 보장한다.

- seed domain coverage가 일정 수준 이하로 떨어지지 않는다.
- 모든 public term이 index에 포함된다.
- 모든 public term이 source/citation과 related term을 갖는다.
- related dictionary links가 실제 파일로 resolve된다.
- Event/Action/SOP mapping이 실제 catalog/BoI로 resolve된다.

# Prompt Pattern

Agent에게 dictionary 추가를 요청할 때는 다음 형식을 사용한다.

```text
이 용어를 BoI Wiki dictionary에 추가해줘.
용어: <현장 표현>
의미: <사용자가 알고 있는 설명>
업무 예시: <실제 사용 문장>
관련 SOP/Event/Action 후보도 찾아서 연결해줘.
Public 승격이 맞는지는 검토해서 초안/적용을 구분해줘.
```

# Citations

- [BoI Agent API, MCP, Ontology Search Harness](/public/harness/agent-api-mcp-search-harness.md)
- Public Dictionary index: `data/boi/public/dictionary/index.md`
