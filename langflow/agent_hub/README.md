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
4. 대표 자산은 `langflow/flows/boi_universal_simulation_mcp.json`을 배포합니다.
5. 기존 기준 Flow는 `langflow/flows/boi_wiki_agent_loop.json`, 실제 모델 예제는
   `langflow/flows/boi_wiki_agent_loop_model_agent.json`으로 별도 유지합니다.
6. 반환된 Flow URL과 Flow ID를 Agent Playground에서 live 조회로 다시 찾습니다.
7. 대표 Flow는 Playground에서 MCP API Key 인증을 켜고 `boi_universal_simulate` 도구를 실제 호출해 확인합니다.
8. Agent Playground에서 BoI Action 등록 초안을 만들고 validate, publish-request 순서로 검토합니다.

Flow는 Langflow `/api/v1/run/{flow_id}` 계약을 사용합니다. 기본 저장 방식은 `preview`이며,
`private_draft`를 명시한 실행만 현재 사용자의 개인 Wiki 초안을 만듭니다.

대표 Flow는 같은 exact Flow를 Langflow
`/api/v1/mcp/project/{project_id}/streamable`에서도 제공합니다. 외부 MCP 호출은 항상
preview이며 개인 Wiki를 변경하지 않습니다. `private_draft`는 BoI Playground 테스트 또는
BoI Action이 호출자에게 귀속된 1회성 run token을 전달한 경우에만 허용됩니다.

실제 모델 예제의 `BOI_LLM_BASE_URL`, `BOI_AGENT_EXAMPLE_MODEL`, `BOI_LLM_API_KEY`는 Langflow
Variable/Credential로 제공합니다. Flow JSON에 값 자체를 넣지 않습니다. 지원 버전과 공개 API 경계는
`langflow/compatibility-manifest.json`을 기준으로 합니다.

## 비밀값 경계

- Agent Hub: 개인 Langflow API Key만 저장
- Langflow Credential Variable: `BOI_WIKI_PAT`
- BoI Action 실행: `BOI_RUN_TOKEN` request variable을 한 실행 동안만 사용
- Flow JSON과 컴포넌트 bundle: PAT, API Key, service token 원문 없음

Langflow API Key, BoI PAT, BoI Action run token은 서로 대체할 수 없습니다. API Key는 Langflow
endpoint/Flow/MCP 접근, PAT는 개인 개발 중 Wiki 지식 조회, run token은 공유 Action 실행자의
Wiki 권한에 각각 사용합니다.

`BoIWikiKnowledge`와 `BoIWikiSave` 사이의 Agent는 `boi.agent-slot.v1` 입출력 계약이 명확히 맞을
때만 Playground가 자동 연결합니다. `source_references`, Ontology provenance, Task Context,
`grounding_status`, 저장 입력 계약을 보존하고 실제 runtime provenance에 Component ID가 남아야
합니다. 규약이 불명확하면 Langflow Canvas에서 수동으로 연결한 뒤 다시 검증합니다.

팀 Action도 endpoint 소유자의 개인 Langflow 연결을 서버에서 사용하며 API Key를 다른 사용자에게
노출하지 않습니다. Wiki 접근과 개인 초안 소유자는 HCP로 허용된 실제 Action 호출자의 단기 run
token으로 결정합니다. 별도 팀 endpoint 기능은 이 패키지의 구현 범위가 아닙니다.
