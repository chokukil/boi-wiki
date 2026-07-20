# SOP Internal Alpha Preview 비파괴 Smoke Evidence

## 실행 정보

- 실행 시각: 2026-07-21T08:12:12+09:00
- 문서 worktree: `/home/chokukil/boi-wiki-sop-demo-enablement`
- 문서 브랜치: `codex/sop-demo-enablement`
- 기준 commit: `7d7f22f2bd4c7a8974b3879bf99963fb23b8dca2`
- 확인 대상: `http://localhost:8769`
- 독립 시험 공간: `sop-alpha-20260721-a`
- 시험 사용자: `990021`과 권한 없는 비교 사용자 `990022`
- 변경 범위: 시험 사용자의 memory-mode WorkSession과 private provisional note만 생성. Action 실행, Event 발행, Task 완료, 제품 코드 변경은 하지 않음.

현재 API는 dirty North Star 안정화 checkout에서 실행 중이었다. 따라서 이 기록은 해당 시각의 로컬 runtime 관측이며 문서 브랜치만의 재현 가능한 release 증거가 아니다.

문서 브랜치의 기준 commit에는 현재 runtime에서 확인한 `/api/v2/ontology/query`, `/api/v2/outcomes/{ref}`와 관련 MCP 확장이 아직 없다. 이 브랜치 단독 build를 데모 대상으로 사용하면 안 되며, 기능이 정식 통합된 build에서 다시 smoke해야 한다.

## 준비 상태

| 확인 | 결과 | 판정 |
|---|---|---|
| `/health` | `status=ok` | 통과 |
| `/agent` | HTTP 200 | route 통과 |
| `/tasks/console` | task ID 없이 HTTP 400, 존재하지 않는 시험 task ID로 HTTP 404 | 샘플 Task 미준비 |
| `/api/v2/bootstrap` 현재 SOP 맥락 | `boi:public:sop:equipment-abnormal-response`로 해석 | 통과 |
| core | `core_ready=true` | 통과 |
| 전체 준비 상태 | `state=degraded`, `ready=false` | 제한 상태 |
| Postgres | 미연결 | 실패 |
| 저장 방식 | memory, 재시작 시 소실 | 제한 상태 |
| 검색 색인 | 준비되지 않음 | 실패 |
| Knowledge Graph | 준비되지 않음 | 실패 |
| Deep worker | 준비되지 않음 | 실패 |
| Docker Web `:28000` | 응답 없음 | 실패 |

이 상태에서는 실제 Action, 영속 private 재사용과 전체 브라우저 여정을 데모 성공으로 주장할 수 없다.

## 읽기 여정

### WorkSession과 SOP 맥락

- WorkSession: `ws_2c7b5e4858f846308c57b86948a88483`
- 제목: `sop-alpha-20260721-a smoke`
- page: `/docs/boi:public:sop:equipment-abnormal-response`
- 결과: 고유 사용자에게 session이 생성되고 SOP 맥락이 연결됨.

### 근거 답변

- request: `sop-alpha-20260721-a-read-01`
- run: `run_01fb7d52aea849388c83752196bda734`
- WorkRun: `workrun_fb64a94486e0975f6f8c36c4a245ef90`
- 결과: `status=completed`, `capability_id=knowledge.search`, `grounding_status=grounded`
- 사용 source:
  - `boi:public:sop:equipment-abnormal-response`
  - `boi:public:dictionary:fdc`
- `사용한 지식` next action: ready

### Citation 원문

- citation: `cite_6b8bec5f86bc487f8a731f5b6d6c2fe1`
- source: `boi:public:sop:equipment-abnormal-response`
- heading: `Summary`
- line: 1~4
- target URL 존재
- 결과: 원문 위치와 이동 정보 조회 통과.

### Source Set

- source set: `sources_ws_2c7b5e4858f846308c57b86948a88483`
- `used` 그룹이 응답의 두 source와 일치
- 검색 후보는 별도 `related` 그룹으로 분리
- 결과: 사용한 source와 관련 후보 구분 통과.

## Ontology와 Action 미리보기

| 항목 | 요청 | 결과 | 사용자 영향 |
|---|---|---|---|
| Ontology projection | SOP ref를 `knowledge_stewardship` projection으로 조회 | HTTP 422, 대상 유형 불일치 | 표·Mermaid·Explorer 표준 데모 미검증 |
| Action plan preview | `sop.equipment.request_maintenance_guide`, `DEMO-EQP-01`, 고유 중복 방지 식별값 | HTTP 403, `action.plan` 사용 불가 | 실제 실행과 중복 실행 방지 smoke를 수행하지 않음 |

제품 코드나 fixture를 수정해 우회하지 않았다. 데모에서는 준비된 환경에서 사전 smoke를 다시 수행하고, 실패하면 관계 표와 Action 확인 카드 캡처로 전환해야 한다.

## private 저장과 재사용

### 저장

- artifact: `artifact_b75b13bcf81f4d6f88a6d694af733bd3`
- 제목: `sop-alpha-20260721-a 설비 Alarm 확인 기준`
- 상태: `provisional`
- owner artifact 조회: HTTP 200
- 결과: 현재 memory store 안에서 private note 생성 통과.

### 새 WorkSession 재사용

- 새 WorkSession: `ws_bc3cba39b44844f1a131325943446a8e`
- 재사용 run: `run_5ac19eef1b10490ebab4c1911a0e676c`
- 결과: 요청은 완료됐으나 저장한 private artifact가 `used_source_refs`에 포함되지 않음. `grounding_status=partial`.
- 판정: **private note의 새 세션 재사용 실패 또는 미검증**. 검색 색인과 영속 저장이 준비된 환경에서 재시험 필요.

### 다른 사용자 비노출

| 확인 | 결과 |
|---|---|
| 다른 사용자의 WorkSession 직접 조회 | HTTP 403 |
| 다른 사용자의 private artifact 직접 조회 | HTTP 403 |
| 다른 사용자의 citation 직접 조회 | HTTP 403 |
| 다른 사용자의 WorkSession 목록에서 시험 제목 검색 | 0건 |

현재 process 안의 교차 사용자 비노출은 통과했다. 재시작과 영속 DB를 포함한 권한 검증은 수행하지 않았다.

## 실행하지 않은 항목

- Action 확인 및 실제 실행
- 동일 실행 요청 반복과 Task·Action·Outcome 수 비교
- Outcome과 실행 Evidence Ledger
- Pet·Expanded·Fullpage·Task Console 브라우저 연속성
- MCP 연결과 Web·REST·MCP 의미 동일성
- 전체 pytest, Product/Platform Golden, 240 holdout
- 성능, 동시 요청, 장시간 실행과 DeepAgents worker

## 결론

Web route, SOP 맥락, WorkSession, 근거 응답, citation 원문, 사용 source 구분, private note 생성과 현재 process의 교차 사용자 차단은 확인했다. 대상 환경은 제한 상태이므로 Ontology 표준 projection, Action 미리보기·실행, 중복 방지, 새 세션 private 재사용과 영속성은 데모 전 필수 재검증 항목이다.
