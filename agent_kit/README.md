# BoI Wiki Agent Kit

BoI Wiki v2를 Codex, Claude 또는 일반 API client에서 사용할 때 필요한 최소 계약이다.

1. Web의 `외부 도구 연결`에서 개인 연결 키를 만든다.
2. 키를 저장소 밖의 `BOI_PAT` 환경 변수나 secret manager에 넣는다.
3. 일반 요청은 `boi_agent`에 자연어로 보낸다. 검색, 분석, 초안, 심층 작업 경로는 BoI Wiki가 자동으로 정한다.
4. 근거 검색은 `boi_search(view="ranked")`, 연결 관계·경로·영향·이해 순서는 같은 도구의 `neighbors|path|impact|tour` 보기를 사용한다. 정확한 단건은 `boi_get`, 결정적 자동화 초안은 `boi_plan`, 명시적 검토 확인은 `boi_confirm`을 사용한다.

후속 요청에서는 첫 응답의 `work_session_id`를 다시 보내야 Web Pet과 같은 대화, source set, citation, artifact를 이어 쓸 수 있다. `capability_id`는 사용자가 모드를 고르는 값이 아니라 결정적 외부 자동화에만 사용한다.

```bash
export BOI_BASE_URL=http://localhost:28000
export BOI_PAT='<issued-token>'
scripts/install_boi_agent_kit.sh --client codex
```

MCP Streamable HTTP endpoint는 기본 `http://localhost:8200/mcp/v2`다. 모든 요청에 `Authorization: Bearer $BOI_PAT`를 보낸다.

연결 키를 `.env.example`, source file, Skill 문서, prompt 또는 대화에 기록하지 않는다.
