# `origin/main` 기반 Agent Playground 완료 감사

감사 기준일: 2026-07-26

브랜치: `codex/agent-playground-mainline`

기준점: `origin/main@53912644c443b0a2af0e5c367901575a111b18ae`

이 문서는 `codex/agent-playground-integration`의 과거 증거가 아니라 운영 main과 같은
기준점에서 다시 구성한 mainline 구현의 감사 기준이다. 최종 적용 커밋은 handoff의
`source-state.json`과 `CHERRY_PICK_ORDER.md`에 기록된 단일 커밋만 사용한다.

## 소스 경계

| 항목 | 결과 | 근거 |
| --- | --- | --- |
| exact main 기반 | PASS | merge-base와 base가 `53912644…b18ae`로 일치한다. |
| 단일 체리픽 | PASS | base 이후 Agent Playground 커밋은 한 개다. |
| Agent v2 제외 | PASS | `boi_api.app.v2`, `PatService`, `AgentV2Service`, semantic kernel 의존이 없다. |
| 인증 계약 | PASS | main의 `AuthIdentity`를 직접 사용한다. |
| pet 기본 비활성 | PASS | 전역 기본값은 `false`, `/playground`는 `hide_pet_agent=True`다. |
| Langflow 비수정 | PASS | 공식 image digest, public `/api/v1`, read-only bundle만 사용한다. |
| Agent Hub 비수정 | PASS | checkout은 `7ca556b7…f7e5`, git diff가 비어 있다. |

`scripts/check_agent_playground_mainline_boundary.py`와
`scripts/check_agent_playground_langflow_boundary.py`가 위 경계를 정적으로 검사한다.
`scripts/audit_agent_playground_mainline_completion.py`는 source state, 브라우저 결과,
Langflow 회귀, 테스트, secret scan, live listener를 하나의 JSON 감사 결과로 묶는다.

## 기능·보안 계약

| 영역 | 결과 | 확인 내용 |
| --- | --- | --- |
| Endpoint | PASS | 사용자별 최대 5개, AES-GCM key 암호화, 빈 key 유지, fingerprint만 응답 |
| Credential | PASS | 전용 SQLite, hash-only PAT, 무기한 기본값, 폐기·회전, run token 1회 소비 |
| MCP v2 | PASS | `boi_search/get/plan/confirm`만 제공하며 client 사번을 받지 않음 |
| Wiki/Ontology | PASS | main ACL, `ontology_search_payload`, SOP/Task Context, preview/private draft |
| Flow | PASS | canonical, LM Studio Gemma model Agent, incompatible Flow를 별도 identity로 검증 |
| 타 작성자 자산 | PASS | `100001` 작성 Flow와 `.py` component를 승인 후 `100002`가 채택 |
| Action | PASS | connector-neutral contract와 교체 가능한 binding 유지, Playground만 Langflow binding |
| 호출 권한 | PASS | endpoint owner key로 Flow를 호출하고 Wiki ACL은 caller run token으로 결정 |

새 Playground Action draft에는 `execution_mode=gateway`,
`boi.action-contract.v1`, `boi.connector-binding.v1`, exact deployment reference를
저장한다. API, MCP, Webhook, Manual, Event Broker, BoI Writer, Langflow는 같은
수준의 connector다. 레거시 `execution_kind`는 읽기 호환에만 남는다.

## 실제 HTTP·브라우저 결과

모든 브라우저 검증은 `file://`이 아니라 실제 HTTP와 OIDC authorization-code +
PKCE S256으로 수행했다.

| 시나리오 | 결과 |
| --- | --- |
| 빈 사용자 온보딩 | `100002`, endpoint 0개에서 key 발급·bootstrap·기준 Flow smoke 완료 |
| 연결 실패·복구 | invalid key 502, 타 사용자 key 403, 미지원 버전 409, 재시도 중복 없음 |
| Wiki 가이드 | 시작/운영 문서 OIDC 200, desktop/390px, pet DOM 0 |
| Agent Hub canonical | invalid key 실패 후 복구, `boi-100002` 선택, exact Flow 배포 |
| Agent Hub model Agent | LM Studio `google/gemma-4-26b-a4b-qat` 실제 추론·Action E2E |
| 타 작성자 채택 | 승인 Flow와 component를 개인 endpoint/project로 배포·재발견 |
| incompatible Flow | `BoIWikiSave` 누락을 `blocked`로 기록하고 Action draft 409 |
| Action 실행 | 일반 질문, SOP Task, preview, private draft 모두 exact Flow로 실행 |
| 권한 격리 | private draft owner `100002`, `100003` Action 실행 403 |
| 브라우저 오류 | 모든 최종 runner의 unexpected HTTP/page/console 오류 0건 |

### canonical exact chain

```text
Keycloak empno 100002
→ Agent Hub asset d345c5e7-c2b0-4116-aa00-d5e9bad143e5
→ project boi-100002
→ Flow 73ad7fff-c624-47af-9b57-56d3ab895336
→ checksum 680fe5f4942ec8f8b8641d8d5b0a02cc81202352581961f132388326f8893f8d
→ draft action-registration-20260726175415-c3aed475
→ validate → publish_requested → validation-only operator fixture
→ exact Action
→ 일반 질문 → SOP Task → caller-private draft
```

### LM Studio model Agent exact chain

```text
Keycloak empno 100002
→ Agent Hub asset 8ada6718-f852-4f15-9312-5f186d32d293
→ project boi-100002
→ Flow ec3bc2d9-3c27-424c-812c-98c1f25ae54e
→ checksum 00e54b53b8104b86e1afcc002c9c557e052e41afe477b92be131898eefcfc982
→ exact Action
→ LM Studio google/gemma-4-26b-a4b-qat 실제 응답
→ 일반 질문 → SOP Task → caller-private draft
```

일반 실행은 source reference 6개와 provenance가 있는 Ontology 관계 40개를 반환한다.
SOP Task에는 Task/SOP/Stage/Event/Action/선행 결과/필요·부족 근거가 보존된다.
graph가 없는 private draft 실행은 Ontology 성공으로 오표기하지 않고
`grounded_document_fallback`으로 표시한다.

## Langflow 전환·회귀

- 공식 image:
  `langflowai/langflow:1.11.0@sha256:f7de8256fdbba725d7765bcff9d984ad272e0f726daabf2d7e3c3b0fa8dc31bf`
- 1.10 Flow export → clean 1.11 upload 201 → `/api/v1/run` 200
- 1.10 DB clone → 1.11 migration → user Flow/Credential 복호화 유지
- 1.10 image·DB·secret 세트 rollback 성공
- 순정 runtime에는 BoI component 없음
- read-only bundle runtime에만 `BoIWikiKnowledge`, `BoIWikiSave`,
  `BoIModelAgent` 존재
- 공식 package hash가 순정/bundle runtime에서 동일

## 자동 회귀와 인수 패키지

- 전체 main 회귀: `613 passed`
- Action connector 회귀: `19 passed`
- secret scan: 원문 API Key/PAT/run token 0건
- checksum: handoff의 `SHA256SUMS`
- 최종 인수 위치:
  `artifacts/agent-playground-handoff/<run_id>-mainline-final-audit/`
- 기계 판독 완료 감사:
  `regression/mainline-completion-audit.json`

최종 패키지는 Flow JSON, read-only bundle, compatibility manifest, Wiki 시작·운영
가이드, Playwright screenshots/JSON, Langflow import·migration·rollback 증거,
connector 회귀, source state, secret scan, checksum, 단일 체리픽 순서를 포함한다.
임시 `/tmp` 경로는 인수 위치나 사용자 문서의 증거 경로로 사용하지 않는다.

## 실행 경계

- 기존 main `:28000`, 기존 Langflow `:7860`은 계속 실행되며 mainline은
  BoI `:28005`, Gateway `:18105`, MCP `:18205`, Langflow `:7867`에서 격리한다.
- Agent Hub는 `:18080/:18001`, Keycloak `:18082`, Mock HCP `:18083`을 사용한다.
- LM Studio는 기존 `:1236`의 Gemma를 재사용한다.
- 대표 Flow 선정, 대표 모달 노출, 사내 Caddy/DNS/Keycloak 인프라 구현은 외부 후속이다.
- 사내 적용 대상은 이 mainline 단일 커밋뿐이며 과거 `9fee2118`이나 이전 Playground
  브랜치를 적용 대상으로 안내하지 않는다.
