# DB에서 OKF·Profile 지식 준비하기

서버 관리자는 읽기 전용 연결과 허용 테이블을 등록한다. 사용자는 MCP에서 연결을 선택하고 질문한다. 에이전트가 구조와 실제 행을 읽고 Profile과 의미를 작성한다. 사용자에게 SQL, 원시 JSON, 개발 저장소 경로를 요구하지 않는다.

## MCP 작업 순서

1. `boi_bootstrap`과 `boi_domain_packages`로 설치된 하네스·스킬·Profile을 발견한다. 진행 중인 작업은 `boi_knowledge_work(status/resume)`로 복원한다.
2. `boi_native_query(source_discover)` → `source_schema`로 연결의 허용 테이블, 현재 snapshot, planner catalog를 읽는다. 연결명과 컬럼명은 탐색 단서다. 도메인·업무 identity·관계를 확정하는 근거가 아니다.
3. `source_capture`에 서버가 반환한 `source_id`, `table`, `snapshot_digest`를 전달한다. `next_offset`이 null이 될 때까지 이어간다. 반환되는 행에는 기존 SourceArtifact·EvidenceSpan과 DB 컬럼·스냅샷·행 위치가 있다. 행 위치는 업무 키가 아니다. 원천 DB를 수정하지 않는다.
4. 대량 페이지와 중단 복원은 설치된 `scripts/boi_database.py`를 사용한다. 같은 API와 권한 계약을 쓰며, 같은 페이지는 기존 근거를 재사용한다. 명령은 에이전트가 실행한다.

   ```sh
   python scripts/boi_database.py --source-id SOURCE_ID --table TABLE --output-dir PRIVATE_STATE
   ```

   `BOI_BASE_URL`, `BOI_PAT`는 호스트의 비밀 설정으로 제공한다. `source-records.json`과 `source-scope.json`은 기존 `boi_local.py profile-prepare` 입력이다. `authoring-sources.json`은 `assemble`의 `sources` 입력이다. 페이지 원문과 기존 artifact/span을 함께 검증하므로 새 원천으로 복제하지 않는다. 준비 결과와 기록은 개인 작업 디렉터리에 보존한다.
5. 현재 사용 가능한 Profile을 읽고 `profile-prepare → profile-candidates → profile-route`로 재사용/확장을 결정한다. 필요한 행의 의미를 원문에 맞춰 작성한다. `profile-layout-*`으로 모든 행의 처리 여부를 유지한다. 합의된 Profile이 없으면 새로운 선언으로 준비한다. 새 의미를 기존 필드 이름에 맞춰 억지로 변환하지 않는다.
6. 기존 `assemble → review → pack`과 `boi_knowledge_work(publication)`의 preview, impact, admit, upload, prepare, validate, qualify, preflight, publish를 사용한다. 자세한 명령은 [로컬 준비](local-preparation.md)를 따른다. 의미 검토 의견은 실제 읽은 원문에 대해 작성해야 한다. 기계 검사가 통과했다고 supported 의견을 만들지 않는다.
7. publish 영수증, `publication_resume/status`의 현재 basis와 revision을 확인한다. 새 MCP 연결에서 `boi_knowledge_catalog` 또는 공통 질문 경로로 다시 발견하고 `boi_knowledge_read(view="document")`로 현재 지식과 근거를 읽는다. 로컬 준비 완료는 게시 완료가 아니다.
8. DEXA 물리 조회는 `source_schema`의 정확한 planner catalog에 대해 작성·검토된 Native Profile이 필요하다. `source_bind`에 `source_id`, `snapshot_digest`, `profile_revision`, `review_revision`을 전달한다. 서버가 기존 NativeQueryHost의 근거·검토·매핑 검증을 통과한 연결만 등록한다. 이후 `discover → prepare → plan → execute → result`를 사용한다. 텍스트 설명용 KnowledgeProfile만으로 SQL 관계를 실행하지 않는다.

## 의미와 답변

- OPER: 목적·대상·방법·작용·관리점과 조건·예외를 각각 근거에 연결한다.
- SVID: 장비/모듈/파라미터 식별자, 측정·설정·한계 역할, 단위, 설명 범위, 실제 min/max를 구분한다. 공란을 수치로 채우거나 상충하는 범위를 하나로 합치지 않는다. Formula는 선언된 입력 역할·단위·식과 실제 관측값으로만 실행한다.
- DEXA: 업무 객체, 행의 단위, 키, 카디널리티, 조인 방향, 필터·집계·시간 조건을 선언한다. 전체 목록에서 중복이나 미연결 행을 제거하지 않는다. 저장 행 수와 업무 객체 수를 구분한다.

질문의 요청 항목을 검색 전에 정리하고, 항목마다 답과 근거 또는 미해결 이유를 전달한다. 핵심 답, 필요한 설명/표, 관련 한계, 출처 순서로 쓴다. 호스트의 요청 누락 검사는 의미 정확성 판정을 대체하지 않는다.

## 재개와 교정

같은 snapshot은 같은 작업 디렉터리에서 재개한다. 데이터 변경은 새 디렉터리로 보존한다. 기존 논리 identity가 확인된 항목만 `previous_revision`과 `correction`을 사용해 교정한다. 이전 원천은 `existing_sources`로 유지한다. Profile이 그대로면 `existing_profile_revision`을 재사용하고, 변경 없는 지식은 기존 게시 revision을 그대로 쓴다. DB 전체 해시가 달라졌다는 이유로 관련 없는 모든 지식을 다시 게시하지 않는다.

교정 admission에는 현재 참조 영향 검사가 필요하다. 서버의 durable PostgreSQL 지식 색인을 사용한다. 백엔드가 없으면 새 게시가 일부 가능해도 교정 완료라고 보고하지 않는다. 실패한 영수증과 검토 의견은 보존하고 실패한 단계만 다시 진행한다.

지원 범위: 봉인된 SQLite 스냅샷, 기존 SQLite 조회 게이트웨이, 승인된 테이블, 최대 1,000행의 페이지와 64 KiB 원문 페이지. 큰 단일 행은 명시적으로 거절된다. gateway 상한은 서버 binding을 따른다. SQLite WAL에 미반영 내용이 있으면 관리자가 일관된 읽기 전용 스냅샷을 제공해야 한다. 사내 DB별 드라이버는 후속 어댑터다.
