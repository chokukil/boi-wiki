# 펫 에이전트 재설계안 (Pet Agent v2)

> 상태: **초기 조사 기록 / 대체됨.** 현재 구현 계약은 README의 `BoI Wiki MCP` 절과 `boi_api/app/v2`, `data/agent_catalog/capabilities-v2.yaml`, `agent_kit/`을 기준으로 한다. 현재 Pet은 `/agent`와 동일한 통합 surface를 사용하고, 별도 `pet_agent/` 패키지나 Langflow DB 공유 대신 Agent v2 전용 Postgres/pgvector, Source Set, line-addressable citation, GoalPlan과 WorkSession을 사용한다.

> 목적: 기존 에이전트가 "의도대로 답을 못 하는" 구조적 원인을 걷어내고, **BoI 자연어 Q&A**를 핵심으로 깨끗하게 다시 짠다. 로컬과 사외·사내 기본 배포는 LM Studio/OpenAI-compatible 사내 모델을 사용하고, GPT-5.5는 명시적인 비교 검증에서만 사용한다.

---

## 1. 왜 새로 짜는가 — 기존의 구조적 오답 원인 (제거 대상)

기존 `native_agent.py` 파이프라인에서 답변 품질을 깎던 장치들:

1. **컴포저 과제약**: "JSON만, title 24자, summary 1~2문장, 마크다운·표·링크·영어 금지", 실질 max_tokens 768 (`main.py:19735~19750`). 상세·구조화 답변이 원천 봉쇄.
2. **무음 폴백**: 강한 검증기(`invalid_agent_composer_answer_reason`)를 못 통과하면 조용히 템플릿 답변으로 대체 → "질문과 무관한 일반 요약" 체감.
3. **약한 기본 모델 + 예시 게이트웨이**: `gemma-4-26b-a4b-qat` @ `http://llm-gateway.example:1236`(예시 도메인).
4. **부분문자열 한국어 검색**: `weighted_text_score`가 조사 붙은 어절 통째 매칭 → 근거 오검색.
5. **안전 키워드 라우팅 납치**: `반영·적용·게시` 등이 들어간 정보성 질문도 승인 플로우로 강제(`native_agent.py:485`).

v2는 위 5개를 전부 제거하는 것이 설계 목표다.

---

## 2. 핵심 컨셉

**"직원이 자연어로 물으면, 접근 권한 내 BoI에서 근거를 찾아 한국어 업무 문장으로 답한다."**

- 검색은 문자열이 아니라 **임베딩(bge-m3)** 기반 의미 검색.
- 답변은 **스트리밍 마크다운** (형식 강제 최소화). 근거(citations)는 답변과 분리된 사이드카 구조로 첨부.
- 라우팅은 **규칙 + 현재 페이지 컨텍스트**로 최소화. LLM 라우터의 오분류·키워드 납치 제거.
- 실패는 **정직하게 노출** ("관련 BoI를 못 찾았습니다"), 무음 폴백 금지.

---

## 3. 파이프라인 (3단계, 단순하게)

```text
사용자 질문
  │
  ├─(0) 스코프 판정 [규칙]  ── 현재 doc 페이지면 "이 문서" 모드, 아니면 "전역 검색" 모드
  │
  ├─(1) 검색 [bge-m3 임베딩]
  │       질문 임베딩 → ACL 필터된 BoI 청크와 코사인 유사도 → top-k
  │       (이 문서 모드면 현재 문서 청크를 우선 포함)
  │
  ├─(2) 합성 [LM Studio / OpenAI-compatible 사내 모델]
  │       질문 + top-k 청크 → 스트리밍 마크다운 답변 (근거 인용 표기)
  │
  └─(3) 후처리
          citations 구조화(어떤 BoI를 근거로 썼는지) + followups(후속 질문 제안)
          근거 0건이면 → "못 찾음" 정직 응답 + 검색어 제안
```

핵심 원칙:
- **승인/실행은 질문에서 자동 유발하지 않는다.** 액션은 사용자가 명시적으로 버튼을 눌렀을 때만. 정보성 질문은 항상 정보로 답한다.
- **ACL은 검색 단계에서 강제.** 임베딩 인덱스 조회 시 해당 사번의 `accessible_docs` 범위로 필터 → private BoI가 RAG로 새지 않도록. (기존 `access_policy.py` 재사용)

---

## 4. 임베딩 인덱스

- **모델**: `text-embedding-bge-m3` (LM Studio에 이미 서빙 중, 한국어 강함).
- **청킹**: BoI 문서를 섹션/문단 단위(약 300~500자, 오버랩 50자)로 분할. front-matter의 title/name_ko/event_label을 청크 헤더로 부착해 검색 히트율 향상.
- **저장**: **pgvector** (이미 떠 있는 `langflow-postgres`에 `CREATE EXTENSION vector`만). 별도 벡터DB 불필요.
  - 벡터 컬럼 + `boi_id`/`visibility`/`owner`/`path` 메타 컬럼을 한 테이블에. ANN 인덱스(HNSW/IVFFlat) + `WHERE`로 ACL 필터를 한 쿼리에.
  - 로컬 PC에서 검색 품질만 빠르게 볼 때는 인메모리 numpy 코사인 폴백(던져버릴 스크립트용)만 얇게.
- **인덱싱 트리거**: 문서 쓰기(`write_boi`) 훅에서 해당 문서만 증분 재임베딩. 초기 1회는 전량 배치 빌드 스크립트.
- **메타 저장**: 청크별 `boi_id`, `visibility`, `owner`, `path`를 함께 저장 → 조회 후 ACL 필터 + citation 생성에 사용.

### 저장소 선택 = pgvector (확정)

규모 감각: BoI 120+ → 청크 수천~수만. bge-m3(1024차원)면 5만 청크여도 벡터 총량 ~200MB. 진짜 요구사항은 규모가 아니라 **ACL 메타데이터 필터링**(사번별 접근 문서만)인데, pgvector가 SQL `WHERE`로 이걸 자연스럽게 해결한다.

- **pgvector 채택 이유**: 벡터 운영 표준 + **이미 떠 있는 `langflow-postgres` 재사용**(새 서비스 0) + SQL로 ACL 필터 + sqlite→pg 마이그레이션 불필요.
- **Milvus는 과함**: 수백만~수십억 벡터·분산 ANN용. etcd/MinIO/standalone 운영부담만 증가, 이 파일럿엔 불필요.
- **확장기(나중)**: 팀 수십 개·벡터 수백만 규모가 되면 Qdrant(단일 바이너리) 또는 Milvus 검토. 그때도 `index.py` 인터페이스만 갈아끼움.

→ **`index.py`를 저장소 인터페이스로 추상화**해 pgvector 구현을 넣되, 인메모리 numpy 폴백(로컬 검증용)도 같은 인터페이스로 둔다. 후일 Qdrant/Milvus 교체 시 에이전트 코드 불변.

---

## 4c. 알림 채널 — 펫 에이전트를 사내 인앱 알림으로

외부 메신저(Slack/Teams) 연동을 파일럿에서 개발할 수 없으므로, **능동 알림(리뷰 P1-3 갭)을 펫 에이전트로 해결**한다. 배관이 이미 대부분 존재.

**이미 있는 것**: `agent_signals_payload()` (`main.py:23494`, `GET /api/agents/boi-wiki/signals`)가
- 인박스의 열린 업무·`approval_required`·`manual_required`를 신호로 변환,
- 현재 보는 페이지와 관련된 업무면 priority↑(90),
- 제목·메시지·target_tab(inbox)·trace_id 구조화 반환.

**v2에서 바꾸는 것 (수동 → 능동)**:
- 플로팅 아이콘에 **뱃지 카운트**(승인 대기 N건). 프론트가 `/signals`를 주기 폴링 → 푸시 인프라 불필요.
- **페이지 진입 시 선제 안내**: "승인 대기 2건 있어요" → 클릭하면 인박스로 이동(target_tab 이미 제공).
- **운영자 알림 확장**: 같은 신호 채널에 DLQ 실패(P0-2)·워크플로 정체를 태워, 운영자가 인지하도록.
- 승인은 시스템의 핵심 인간 개입 지점 → 알림 지연 감소가 워크플로 전체 TAT를 좌우.

**주의**: 신호도 ACL을 존중(본인 인박스만). 폴링 주기는 UX·부하 균형(예: 60초, 페이지 진입 시 즉시 1회).

---

## 4b. 온톨로지 결합 — GraphRAG (Second Brain의 핵심)

단순 임베딩 검색만으로는 "지식에 근거해 제대로 답하는" 경험이 안 나온다. 이 프로젝트는 **이미 명시적 온톨로지와 그래프 API 3종을 갖추고 있어**, 임베딩을 그 위에 얹으면 바로 GraphRAG가 된다. 새로 그래프를 만들 필요가 없다.

### 이미 존재하는 온톨로지 자산 (그대로 활용)
- **엔티티**: Event Type(18) · Action(38) · Workflow(2+SOP내 stages) · BoI 문서(120+) · 용어(56) · Agent goal profile(12).
- **관계 엣지(YAML에 인코딩됨)**: event→`recommended_actions`/`sop_ref`, action→`event_types`/`doc_ref`/`requires_manual_action`/`body.event_type`(다음 이벤트), workflow→`entry_events`/`emitted_events`/`action_refs`/`stage_display.next_stage`, BoI→`source_refs`/`source_event.trace_id`(계보).
- **서빙 중인 그래프 API 3종** (`boi_api/app/main.py`):
  - `GET /api/search/ontology` — 엔티티 그룹별 시맨틱 검색 + `knowledge_panel` + `graph_paths` + `citations`(ACL `can_cite` 준수). `ontology_search_payload()` (main.py:5023).
  - `GET /api/okf/graph`, `/api/okf/graph/doc/{boi_id}` — 문서 링크 concept 그래프 + 1-hop 이웃(outgoing/incoming/backlinks). 인접리스트 사전계산됨 → 멀티홉 즉시 가능.
  - `GET /api/sop-runs/{run_id}/graph`, `workflow_trace_graph()` — 실행 계보 그래프(SOP→event→action→BoI). "왜 이 결정이 내려졌나"에 근거 체인 제공.
- **용어사전 = 크로스-카탈로그 브릿지**: `resolve_dictionary_query()`가 aliases/same_as/broader/narrower/related_terms로 쿼리를 확장하고, term의 `maps_to_event_type`/`maps_to_action_key`/`maps_to_sop`로 자연어를 정규 엔티티에 연결. 56개 중 ~29개가 카탈로그로 직접 매핑됨.

### v2 검색 단계 = 하이브리드 (임베딩 × 온톨로지)

```text
질문
 ├─(a) 용어 확장   resolve_dictionary_query() → 별칭·상위어·정규 event/action/sop
 ├─(b) 시맨틱 회수  ① bge-m3 임베딩 top-k (신규)  +  ② /api/search/ontology (엔티티 인지)
 ├─(c) 그래프 확장  회수된 BoI의 1-hop 이웃(/api/okf/graph/doc) + 카탈로그 엣지(event↔action↔sop)
 ├─(d) 계보 보강    source_refs / source_event.trace_id 로 원천 이벤트·액션 끌어오기
 └─(e) 병합·재랭크  ACL(can_cite/can_use_in_agent_context) 필터 → 근거 세트 확정
```

- **임베딩(b①)이 채우는 공백**: 기존 부분문자열 검색이 놓치던 의미 유사·동의 표현. bge-m3가 한국어 의미 매칭 담당.
- **온톨로지(b②·c·d)가 채우는 공백**: "이 이벤트 다음에 뭐가 오나", "이 액션은 어떤 SOP 소속인가", "이 보고서의 근거 원천은" 같은 **관계형 질문**. 평면 RAG로는 못 답하는 것.
- 컴포저에는 텍스트 청크뿐 아니라 **엔티티 관계 요약**(예: "이 SOP는 detect→analyze→act 3단계, 각 단계 액션과 산출 BoI")도 함께 넘겨, 답변이 지식 구조를 반영하도록 한다.

### 답변에 온톨로지를 드러내기
- 근거는 `citations`(can_cite 준수)로 구조화 제시 — 어떤 BoI/이벤트/액션을 근거로 썼는지.
- 관계형 질문에는 답변에 **연결 경로**를 함께 보여줌(예: "알람 → 근본원인 분석 요청 → 정비 가이드"), 이는 `graph_paths`/okf graph에서 이미 나옴.
- 이것이 "Second Brain"다움의 핵심: 답 + 그 답이 지식 그래프 어디에 근거하는지.

---

## 5. 모델 매핑 (역할별, 전부 config)

| 역할 | 개발(로컬 LM Studio) | 사내 배포 |
|---|---|---|
| 컴포저(답변) | `qwen/qwen3.6-35b-a3b` | LM Studio 또는 OpenAI-compatible 사내 모델 |
| 임베딩(검색) | `text-embedding-bge-m3` | 사내 bge-m3(또는 동급) |
| (선택)경량 분류 | `qwen/qwen3-4b-2507` | 필요 시 |

기본 실행은 `BOI_LLM_BASE_URL`, `BOI_LLM_API_KEY`, `BOI_LLM_MODEL`만 사용한다. `.env`에 OpenAI test credential이 남아 있어도 자동으로 선택하지 않는다.

환경변수(제안, `PET_*`는 역할별 오버라이드):
```
# 개발 기본 = 로컬(무료)
PET_COMPOSER_BASE_URL=http://mangugil.iptime.org:1236/v1
PET_COMPOSER_MODEL=qwen/qwen3.6-35b-a3b
PET_EMBED_BASE_URL=http://mangugil.iptime.org:1236/v1
PET_EMBED_MODEL=text-embedding-bge-m3
PET_VECTOR_STORE=pgvector           # 기본 pgvector, 로컬 검증 시 memory 폴백
PET_PG_DSN=postgresql://...@langflow-postgres:5432/boi   # 기존 postgres 재사용
PET_COMPOSER_MAX_TOKENS=2048        # 기존 768 → 상향
PET_COMPOSER_TEMPERATURE=0.3
PET_RETRIEVAL_TOP_K=6
PET_STREAM=true

# GPT-5.5 비교 검증 전용. 상시 서비스 설정에 넣지 않는다.
# BOI_GPT55_TEST_MODE=true
# BOI_AGENT_USE_OPENAI_RUNTIME=true
# BOI_GPT55_TEST_BASE_URL=https://api.openai.com/v1
# BOI_GPT55_TEST_MODEL=gpt-5.5
# BOI_GPT55_TEST_API_KEY=<test credential>
```
전환은 컴포저 3개 변수만 교체. 임베딩은 어느 환경이든 로컬/사내 bge-m3 사용(OpenAI 임베딩 미사용).

### 5b. 비용 통제 원칙 (중요)

GPT-5.5는 호출당 비용이 크므로, **개발·테스트 단계에서는 OpenAI를 거의 호출하지 않는다.**

- **개발/테스트 기본 = 100% 로컬**: 컴포저 qwen3.6-35b-a3b, 임베딩 bge-m3. 반복 개발·회귀 테스트는 전부 무료 로컬에서.
- **임베딩은 항상 로컬**: 인덱스 전량 빌드(수천 청크)는 반드시 로컬 bge-m3로. OpenAI 임베딩 절대 사용 안 함.
- **GPT-5.5 호출은 "테스트 단계 최소 스모크"로 한정**: 로컬로 파이프라인이 다 돌고 난 뒤, 프롬프트가 GPT-5.5에서도 잘 작동하는지 **소수의 대표 질문(예: 3~5개)만** 1회 확인. 자동 회귀 스위트에 OpenAI를 넣지 않는다(로컬 모델로만 CI).
- **사외·사내 상시 서비스도 로컬/사내 모델**: GPT-5.5는 운영 경로로 사용하지 않는다.
- 안전장치: `BOI_GPT55_TEST_MODE=true`와 `BOI_AGENT_USE_OPENAI_RUNTIME=true`가 동시에 없으면 OpenAI runtime 호출을 차단한다. GPT-5.5 모델명이 v2에 잘못 들어와도 로컬 모델로 되돌리거나 readiness에서 차단한다.

> 보안 메모: 실제 provider credential은 예제 파일이나 Git에 기록하지 않는다. GPT-5.5 비교 검증용 credential도 실행 시점의 secret으로만 주입하고 검증 후 제거한다.

---

## 6. 프롬프트 방향 (기존 대비 완화)

컴포저 시스템 프롬프트 골자 (형식 강제 대폭 완화):
- 역할: "BoI Wiki의 업무 도우미. 제공된 BoI 근거만으로 한국어 업무 문장으로 답한다."
- 허용: 마크다운, 짧은 목록, 필요한 표. **금지 조항 최소화** (JSON 강제·길이 24자 제한 제거).
- 근거 규칙: "제공된 근거에 없는 내용은 지어내지 말고 '해당 내용은 BoI에 없습니다'라고 답한다."
- 인용: 답변에 사용한 BoI를 문장 끝에 `[출처: {name_ko}]` 형태로 표기. 구조화 citation은 서버가 별도 부착.
- 용어: 한국어 기본, 고유명사(BoI/SOP/Event/Action/MCP)만 영어 허용.

라우팅은 LLM 없이 규칙:
- 현재 URL이 `/boi/{id}` doc 페이지 → "이 문서 우선" 모드.
- 그 외 → 전역 검색 모드.
- 명시적 액션 버튼(승격/워크플로 시작)은 별도 핸들러. 채팅 질문에서 자동 라우팅하지 않음.

---

## 7. 프론트엔드

- 기존 `pet_agent.js`의 SSE 처리(`answer_delta`/`followups`/`citations`)는 재사용 가능 — 백엔드 계약만 맞추면 됨.
- intent 칩 단순화: `검색` / `이 페이지` / `요약` 3개로 축소. `도식 생성·승인 필요·권한 확인`은 v2 코어에서 제외(추후).
- 활성화 플래그 `BOI_PET_AGENT_ENABLED` 유지(현재 false) → v2 완성 후 true.
- 페이지 본문을 서버가 컨텍스트로 확보(현재는 title만 전송) → "이 페이지" 질문 정확도 개선.

---

## 8. 파일 구성 (신규, 격리)

```
boi_api/app/pet_agent/           # 새 패키지 (기존 native_agent.py 미수정)
  __init__.py
  config.py        # 역할별 모델/URL/파라미터 로딩
  embeddings.py    # bge-m3 호출 + 청킹
  index.py         # pgvector 인덱스 빌드/조회/증분갱신 + ACL 필터 (인메모리 numpy 폴백)
  ontology.py      # 기존 그래프 API 래핑: 용어확장·ontology_search·okf_graph·source_refs 트래버설
  retrieve.py      # 하이브리드 회수(임베딩 × 온톨로지) → 병합·재랭크 → 근거 세트
  compose.py       # 컴포저 LLM 스트리밍 호출 + 프롬프트
  service.py       # 파이프라인 오케스트레이션(스코프판정→검색→합성→citation)
  routes.py        # /api/agents/boi-wiki/chat/stream (v2)
scripts/build_pet_index.py       # 초기 전량 임베딩 빌드
tests/test_pet_agent_v2.py       # 검색 정확도/ACL 격리/근거없음 정직응답 회귀
```

---

## 9. 구현 단계 제안

1. **하이브리드 검색** (`embeddings/index/ontology/retrieve` + build 스크립트): bge-m3 임베딩 + 기존 온톨로지 API(용어확장·ontology_search·okf_graph) 결합, ACL 필터 검색이 맞는 문서·관계를 반환하는지 먼저 검증. — *여기서 "지식 근거" 품질이 결정됨.*
2. **컴포저 + 스트리밍** (`compose/service/routes`): qwen3.6-35b-a3b로 근거 기반 답변 스트리밍. 근거없음 정직응답 포함.
3. **프론트 연결 + config + 플래그 on**: intent 3종으로 단순화, 페이지 컨텍스트 전달, 환경변수 정리.
4. **회귀 테스트 + 로컬 실측**: 실제 질문 세트로 검색 hit·오답·ACL 격리 검증. (당신 PC에서 LM Studio 실측)

---

## 10. 열린 결정 사항

- 사내 OpenAI-compatible 모델의 품질·지연 기준과 GPT-5.5 일회성 비교 검증의 합격 기준.
- 벡터 저장 1안(sqlite) vs 2안(faiss) — Pilot 문서 수 규모 확정 후.
- 임베딩 재빌드 주기(문서 쓰기 증분 vs 야간 배치).
