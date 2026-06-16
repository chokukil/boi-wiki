# PPT Capture Plan

## Purpose

경영진 대상 PPT는 개념 설명만으로 끝내지 않고, 실제 PoC가 동작한 핵심 화면을 증거로 포함한다. 캡처는 Chrome/Computer Use로 실제 브라우저와 PowerPoint 화면에서 수행하고, 원본 이미지와 PPT 반영본을 분리 보관한다.

## Required Screens

| 화면 | URL 또는 앱 | PPT에서 증명할 내용 |
|---|---|---|
| BoI Wiki 홈 | `http://localhost:8000/?employee_id=100001` | Public/Team/Private BoI가 사번/ACL 기준으로 보이는지 |
| SOP Library | `http://localhost:8000/sops?employee_id=100001` | Agent Harness, BoI Wiki, SOP가 실제 Wiki 문서로 존재하는지 |
| Event Type Catalog | `http://localhost:8000/event-types?employee_id=100001` | Event Broker가 기술 topic이 아니라 업무 이벤트 catalog로 설명되는지 |
| Event Stream | `http://localhost:8000/events?employee_id=100001` | 이벤트가 발행/처리되고 audit log가 업무 화면에 남는지 |
| Action Catalog | `http://localhost:8000/actions?employee_id=100001` | BoI Writer, Langflow, API/Webhook, high-risk action이 peer connector로 보이는지 |
| Action Logs | `http://localhost:8100/api/actions/logs` | 실제 action dispatch 결과와 approval_required 상태가 남는지 |
| Private BoI 문서 | 생성된 `/docs/{boi_id}` | 업무 이벤트가 OKF 기반 metadata/body로 materialize되는지 |
| Team 승격 draft | 생성된 `/docs/{promoted_boi_id}` | Private-first 후 명시적 Team/Public 승격 draft가 생성되는지 |
| Langflow | `http://localhost:7860` | BoI reference flow 또는 BoI custom components가 실제 Langflow에서 확인되는지 |
| Kafka UI | `http://localhost:8081` | `boi.events`, `boi.audit`, `boi.dead-letter` topic/message가 실제 Kafka에 있는지 |

## Capture Rules

- 모든 이미지는 실제 화면 캡처로 만들고, 합성 다이어그램은 보조 설명에만 사용한다.
- 각 캡처 파일명에는 순서, 화면명, 시나리오를 포함한다.
- PPT에는 캡처 일시, URL 또는 앱 이름, 데모 사번 `100001`을 작은 caption으로 남긴다.
- 원본 캡처는 `captures/boi-poc/`에 보관하고, PPT export PNG는 `artifacts/ppt/exports/`에 보관한다.
- PowerPoint ChatGPT add-in으로 수정하더라도 수정 주체와 검증 주체는 Codex이며, 최종 PPTX와 화면 export를 모두 확인한다.

## PPT Storyline

1. 이천 포럼 메시지 cascade: TM → CEO → AIX 확산 TF
2. 이번 PoC의 한 문장: 1인 1 Agent를 조직의 지식으로 축적하는 업무 맥락 자산화 PoC
3. Reference architecture: Event Broker → Action Gateway → Peer Connectors → BoI Wiki
4. 실제 동작 증거: Event Stream, Action Logs, Private BoI, Team 승격 draft
5. Langflow/Agent Builder 연결: OpenAI-compatible Gemma 설정과 BoI custom components
6. PoC 범위와 제외 범위
7. 2026 H2, 2027, 2028+ roadmap
8. 첨부: 기술 상세, API, Event Catalog, Action Catalog, 운영/보안 전환 과제
