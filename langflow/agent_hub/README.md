# BoI Wiki Agent Loop

Agent Hub에서 접근할 수 있는 승인 Flow·컴포넌트는 작성자가 누구인지와 관계없이 사용할 수 있습니다.
일반 사용자는 선택한 자산을 자신의 Langflow 1.11 endpoint와 `boi-{employee_id}` 프로젝트로
배포합니다. 해당 endpoint에는 그 사용자가 발급한 Langflow API Key를 최초 한 번 등록합니다.
BoI PAT는 등록하지 않습니다. `BOI_WIKI_PAT`는 Agent Playground 온보딩이 해당 Langflow 사용자의 Credential
Variable로 저장합니다.

## 배포

1. Agent Hub에서 개인 endpoint 연결을 확인합니다.
2. 프로젝트 `boi-{employee_id}`를 선택합니다.
3. `langflow/custom_components/boi` bundle은 `LANGFLOW_COMPONENTS_PATH`에 read-only extension으로 설치합니다. Langflow 소스, UI, API, 내부 DB는 수정하지 않습니다.
4. `langflow/flows/boi_wiki_agent_loop.json`을 기준 Flow로 배포합니다.
5. 실제 모델 예제는 `langflow/flows/boi_wiki_agent_loop_model_agent.json`을 별도 Flow로 배포합니다.
6. 반환된 Flow URL과 Flow ID를 Agent Playground에서 live 조회로 다시 찾습니다.
7. Agent Playground에서 BoI Action 등록 초안을 만들고 validate, publish-request 순서로 검토합니다.

Flow는 Langflow `/api/v1/run/{flow_id}` 계약을 사용합니다. 기본 저장 방식은 `preview`이며,
`private_draft`를 명시한 실행만 현재 사용자의 개인 Wiki 초안을 만듭니다.

실제 모델 예제의 `BOI_LLM_BASE_URL`, `BOI_AGENT_EXAMPLE_MODEL`, `BOI_LLM_API_KEY`는 Langflow
Variable/Credential로 제공합니다. Flow JSON에 값 자체를 넣지 않습니다. 지원 버전과 공개 API 경계는
`langflow/compatibility-manifest.json`을 기준으로 합니다.

## 비밀값 경계

- Agent Hub: 개인 Langflow API Key만 저장
- Langflow Credential Variable: `BOI_WIKI_PAT`
- BoI Action 실행: `BOI_RUN_TOKEN` request variable을 한 실행 동안만 사용
- Flow JSON과 컴포넌트 bundle: PAT, API Key, service token 원문 없음

`BoIWikiKnowledge`와 `BoIWikiSave` 사이에는 Agent Hub의 여러 custom component를 자유롭게 조합할 수
있습니다. 특정 `agent_slot` 구현을 강제하지 않지만 `source_references`, Ontology provenance,
Task Context, `grounding_status`, 저장 입력 계약은 유지해야 합니다. Playground의 구조·build·runtime·SOP
검증을 모두 통과한 exact Flow만 Action으로 연결합니다.

이미 팀 endpoint에 배포된 Flow를 재사용할 때는 다른 직원의 개인 API Key를 전달하지 않습니다.
운영자가 팀 소유 endpoint 연결과 HCP 사용 권한을 관리하고, Wiki 접근 권한은 Action 호출자의 단기
run token으로 적용합니다.
