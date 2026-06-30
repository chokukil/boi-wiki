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
7. `index.md`에는 대표 domain entry만 유지한다. 전체 term 목록을 직접 나열하지 않고 업무 용어 UI/API cursor 검색으로 찾게 한다.
8. 저장 전 self-check와 repository test를 실행한다.

# Context Budget Rule

Dictionary는 수천~수만 건으로 커질 수 있으므로 Agent/MCP 기본 경로는 항상 compact retrieval을 사용한다.

| Contract | 기준 |
|---|---|
| `dictionary_resolve` 기본 match | 8건 |
| `dictionary_resolve` 최대 match | 25건 |
| `definition` excerpt | 240자 이하 |
| `aliases` | term당 8개 이하 |
| `related_terms` | term당 8개 이하 |
| `query_expansion` | 전체 24개 이하 |

match가 더 많으면 `overflow.total_matches`, `overflow.omitted_count`, `overflow.refine_hint`를 보고 검색어, domain, scope를 좁힌다. full 목록은 admin/debug 목적 외에는 사용하지 않는다.

# Large Dictionary Authoring

대량 용어를 추가할 때는 domain/folder 단위로 나누고 다음 순서를 따른다.

1. `dictionary_resolve`로 중복과 private/team/public overlay를 확인한다.
2. 새 term은 가장 좁은 scope에 먼저 만든다.
3. `same_as`와 `aliases`는 동의어, `broader/narrower`는 계층, `related_terms`는 약한 참고 관계로 분리한다.
4. 관계는 depth 1 기준으로 충분히 설명하고, 무의미한 dense graph를 만들지 않는다.
5. Public/team 승격 전 ontology search 영향 preview와 context budget test를 확인한다.

# Granularity Rule

Public dictionary는 상위 개념과 세부 현업 용어를 모두 허용한다. 다만 세부 test/mode/variant 용어는 graph 없이 단독 canonical로 승격하지 않는다. 세부 용어가 public에 올라가려면 상위 public term과의 관계가 metadata와 Markdown 본문 양쪽에 남아야 한다.

권장 `term_kind`는 다음 중 하나다.

| term_kind | 사용 기준 |
|---|---|
| `concept` | 여러 업무/문서에서 재사용되는 상위 개념 |
| `acronym` | 현장 약어 또는 시스템 약어 |
| `test-method` | 특정 평가/검증 방법 |
| `variant-group` | 여러 조건/모드/수치 variant를 묶은 표현 |
| `variant` | 상위 test-method나 variant-group에 속한 개별 변형 |

`test-method`, `variant-group`, `variant`는 `broader` 또는 `related_terms`에 상위 public term을 반드시 연결한다. 본문 `# Related Dictionary Terms`에도 같은 상위 term을 Markdown link로 표시한다.

## Slash/Numeric Bundle Rule

`/`, 숫자 variant, 조건 묶음형 용어는 기본적으로 canonical title 후보가 아니라 `상위 개념 + alias/variant` 후보로 검토한다.

예를 들어 `0-PG Dist / 1-NG Dist`는 그대로 public canonical로 승격하지 않고 [Word Line Disturbance Test](/public/dictionary/word-line-disturbance-test.md)의 alias 또는 variant로 둔다. `2HI / 4HI / 8HI Stack`도 그대로 canonical로 두지 않고 [Memory Stack Height](/public/dictionary/memory-stack-height.md)의 alias 또는 하위 variant로 정리한다.

Qwen 같은 자동 추출 source에서 slash/numeric bundle이 들어오면 override 없이 `selected public canonical`로 쓰지 않는다. import manifest에는 `needs_parent_curation`, `compound_reason`, `canonical_term`, `broader` 판단을 남긴 뒤 curator가 `replace_with_canonical`, `split_into_terms`, `alias_to_existing`, `exclude_from_public` 중 하나를 선택한다.

# Quality Gates

Public dictionary 변경 후 최소 검증:

```bash
pytest tests/test_public_dictionary_quality.py -q -s
python scripts/okf_lint.py --root data --include-logs --strict-media --strict-links
pytest tests/test_boi_api_routes.py -q -s -k "ontology_search or dictionary or boi_agent"
```

품질 게이트는 다음을 보장한다.

- seed domain coverage가 일정 수준 이하로 떨어지지 않는다.
- public index가 모든 term을 직접 나열하지 않고 scale policy와 대표 domain entry를 설명한다.
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
