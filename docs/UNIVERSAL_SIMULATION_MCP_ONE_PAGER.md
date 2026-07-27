# BoI Universal Simulation MCP

## 한 줄 소개

업무 요청을 Wiki·Ontology 근거로 이해하고 LM Studio Gemma가 실제 시스템을 호출하지 않는
시뮬레이션을 만든 뒤, 확인된 결과만 개인 Wiki 초안 후보로 남기는 대표 Flow다.

## 처음 사용하는 방법

1. Agent Playground에서 Langflow 연결 키를 등록한다.
2. 자동 준비된 `BoI Universal Simulation MCP`로 샘플 요청을 실행한다.
3. 업무 맥락, Ontology provenance, Wiki 근거, 부족 근거를 확인한다.
4. 같은 Flow를 MCP tool `boi_universal_simulate`로 연결하거나 Agent Hub 기존 UI에서 배포한다.
5. Agent Hub 배포 Flow를 Playground가 exact Flow ID와 checksum으로 다시 찾고 검증한다.
6. 검증된 Flow를 connector-neutral BoI Action의 Langflow binding으로 연결한다.

## 안전 경계

- 결과에는 `SIMULATED`와 실제 업무 시스템 미호출 사실이 표시된다.
- 외부 MCP는 조회와 preview만 수행하며 Wiki를 변경하지 않는다.
- 개인 초안은 Playground 또는 BoI Action이 호출자별 1회성 run token을 전달한 실행만 만든다.
- Langflow API Key, BoI PAT, Action run token은 서로 다른 자격이며 Flow와 문서에 원문을 남기지 않는다.
- Langflow와 Agent Hub 소스는 수정하지 않는다.

## 교체 가능한 부분

가운데 Agent만 `boi.agent-slot.v1` 호환 Component로 교체할 수 있다. 교체 후에도 Task Context,
source references, Ontology provenance, grounding, 저장 계약을 보존하고 실제 실행 provenance에
Component ID가 남아야 Action으로 연결할 수 있다.

## 담당자 전달 사항

대표 모달 선정은 Agent Hub 담당자가 수행한다. BoI는 secret-free Flow JSON, read-only Component
bundle, compatibility manifest, checksum, Canvas와 실제 E2E 증거를 전달한다.
