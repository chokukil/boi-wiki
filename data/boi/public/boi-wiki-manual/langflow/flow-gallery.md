---
okf_version: "0.1"
boi_profile_version: "0.1"
type: boi/reference
title: Langflow Flow Gallery
description: BoI Wiki PoC에서 사용하는 Reference, Equipment Stage Analysis, Universal Action Simulator Langflow canvas 증거와 실행 의미
tags: [Langflow, BoIComponent, Workflow, Screenshot]
timestamp: 2026-06-23T00:10:00+09:00
boi_id: boi:public:boi-wiki-manual:langflow:flow-gallery
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: image
    ref: public/boi-wiki-manual/_media/browser/langflow-flow-gallery/20260622-boi-reference-flow.png
  - type: image
    ref: public/boi-wiki-manual/_media/browser/langflow-flow-gallery/20260622-boi-equipment-stage-analysis-flow.png
  - type: image
    ref: public/boi-wiki-manual/_media/browser/langflow-flow-gallery/20260622-boi-universal-action-simulator-flow.png
review:
  reviewer: tf-lead
  review_status: reviewed
---

# Summary

이 문서는 BoI Wiki PoC의 public Langflow canvas 증거를 한 곳에 모은 gallery다. 세 flow는 모두 같은 원칙을 따른다. Event 또는 chat input을 BoI 업무 맥락으로 정규화하고, BoI Wiki context와 Agent Harness를 사용해 실행 결과를 만들며, 결과는 BoI Wiki 문서 또는 action log와 연결된다.

# BoI Reference Flow

![BoI Reference Flow](/public/boi-wiki-manual/_media/browser/langflow-flow-gallery/20260622-boi-reference-flow.png)

`BoI Reference Flow`는 BoI custom component 연결 상태를 검증하는 기준 flow다. Event input은 `BoI Context Normalizer`를 거쳐 업무 맥락이 되고, `BoI Wiki Reader`와 `BoI Harness Loader`가 prompt composer에 근거와 작성 원칙을 제공한다. Gemma OpenAI-compatible LLM 출력은 `BoI Policy & Validation Guard`, `BoI Wiki Writer`, `BoI Action Invoker`, `BoI Result Composer`로 이어진다.

`BoI Wiki Writer`의 `Body` 필드가 비어 있어도 정상이다. 이 flow는 정적 body override를 쓰지 않고, Gemma LLM의 `Model Response`를 Writer의 `Body Message` 입력으로 전달한다. 따라서 실행 시 본문은 연결된 LLM message에서 생성된다.

# BoI Equipment Stage Analysis Flow

![BoI Equipment Stage Analysis Flow](/public/boi-wiki-manual/_media/browser/langflow-flow-gallery/20260622-boi-equipment-stage-analysis-flow.png)

`BoI Equipment Stage Analysis Flow`는 설비 이상 대응 SOP의 stage별 분석을 담당한다. `BoI Wiki Reader`는 equipment abnormal response SOP와 관련 action context를 읽고, `BoI Prompt Composer`는 normalized work context, harness, wiki documents, prior action results를 합쳐 stage-specific Korean analysis prompt를 만든다.

이 flow의 핵심 차이는 action key와 instruction이다. Reference flow가 일반 workflow draft를 생성한다면, Stage Analysis flow는 `root_cause.analysis.requested`, `maintenance.guide.requested`, `corrective_action.requested` 같은 SOP stage event를 받아 원인 후보, 보전 가이드, 조치 후보, manual handoff 요구사항을 trace별 결과로 정리한다.

# BoI Universal Action Simulator Flow

![BoI Universal Action Simulator Flow](/public/boi-wiki-manual/_media/browser/langflow-flow-gallery/20260622-boi-universal-action-simulator-flow.png)

`BoI Universal Action Simulator Flow`는 실제 사내 시스템이 연결되지 않은 action을 PoC evidence로 시뮬레이션하는 공식 flow다. 입력은 Event Broker 영역에서 들어오고, `BoI Context Normalizer`가 이를 WorkContext로 변환한다. 이후 `BoI Universal Simulator Agent`가 BoI Wiki 지식, action spec, event context, prior results를 기반으로 tool-loop 방식의 simulation result를 만든다.

Simulator flow는 standalone LLM pipeline이 아니다. 공식 completion 기준은 `BoI Universal Simulator Agent`가 중심 노드로 존재하고, 그 결과가 `BoI Metadata Builder`, `BoI Policy & Validation Guard`, `BoI Result Composer`, `BoI Draft Output`으로 이어지는 것이다. 결과에는 실제 시스템 호출이 아니라는 `SIMULATED` 표시와 human review 필요 여부가 포함되어야 한다.

local-full acceptance는 flow 존재 여부만 보지 않는다. Universal Simulator는 실제 호출 smoke에서 `coverage_score >= 0.85`, `evidence_packets`, 그리고 `equipment_id`, `lot_id`, `wafer_id`, `alarm_code` 같은 업무 차이 판단 필드를 포함한 business context를 반환해야 한다. 이 값은 Action log, generated BoI, Inbox group 요약으로 전파되어 “같은 유형 N건”의 차이를 장비/LOT/Alarm/근거 상태 기준으로 비교하는 데 쓰인다.

# BoI Agent Flow

`BoI Agent Flow`는 우측 하단 Web Pet Agent와 MCP `boi_agent_chat`의 visual workflow/debug 예제다. endpoint는 `boi-agent`이며, 공식 외부 인터페이스는 BoI API와 `boi-wiki-mcp`다. BoI API의 production path는 Native BoI Agent이고, Langflow flow는 같은 tool-loop 개념을 화면에서 확인하는 용도다. Canvas completion 기준은 `Chat Input -> native Agent -> BoI Agent Tools -> BoI Agent Result Composer -> Chat Output` 경로가 연결되어 있고, standalone LLM -> Output 경로가 없어야 한다. Agent toolset은 read/action tool 중심이며 `boi_agent_chat` 자체는 recursion 방지를 위해 연결하지 않는다.

# Runtime Checks

아래 명령으로 runtime에 등록된 flow가 이 gallery의 의도와 일치하는지 확인한다.

```bash
python scripts/setup_langflow_reference_flows.py --summary --skip-smoke
python scripts/audit_langflow_flows.py --runtime --auth-mode api-key --langflow-api-key "$LANGFLOW_API_KEY"
python scripts/check_langflow_universal_simulator.py --langflow-url http://localhost:7860 --boi-api-url http://localhost:28000
```

완료 기준은 고정 flow id가 아니라 flow name, endpoint, 연결 구조, Action Gateway invocation 결과다. NAS나 local에서 setup script를 다시 실행하면 flow id는 바뀔 수 있다.

# Citations

- [Langflow Connected Flow Guide](/public/boi-wiki-manual/langflow/connected-flow-guide.md)
- [Langflow Reference Flow 호출](/public/actions/langflow/reference-flow.md)
- [Langflow 설비 SOP Stage 분석](/public/actions/langflow/stage-analysis.md)
- [SOP Image to E2E Workflow](/public/boi-wiki-manual/use-cases/sop-image-to-e2e-workflow.md)
