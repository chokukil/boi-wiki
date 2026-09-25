# DB 기반 MCP 기능 배포

OPER·SVID·DEXA 자료를 기존 OKF/Profile과 원천 근거 계약으로 준비한다. 설치 패키지에는 모델·실제 DB·추출 데이터·접속 정보가 없다. 의미 작성은 사용자의 외부 에이전트가 수행하고 서버는 현재 권한·검토·게시·계산 계약을 검증한다.

## 설치와 연결

API와 MCP는 이 브랜치의 제품 코드와 각 `requirements.txt`로 설치한다. 영속 지식 저장소는 PostgreSQL을 사용한다. 원천 SQLite와 지식 저장소는 별개다. 기존 운영 설정과 비밀 값은 배포 파일에 복사하지 않는다.

1. `python agent_kit/install.py --help`에서 호스트별 설치 옵션을 확인한다. 패키지는 `agent_kit/`만으로 설치할 수 있다. 설치 대상에서 `runtime/requirements.txt`, `runtime/mcp-requirements.txt`의 고정 의존성을 설치하고 `scripts/boi_local.py doctor`로 확인한다.
2. [연결 템플릿](../config/database-sources.example.json)을 서버의 개인 설정 디렉터리로 복사하고 실제 principal·경로·허용 테이블을 지정한다. API 서버에 `BOI_DATABASE_SOURCES_PATH`를 설정한다. 원천 파일은 읽기 전용으로 마운트한다. `BOI_DATABASE_QUERY_STORAGE`는 보호된 쿼리 결과 저장 디렉터리다.
3. 호스트에 공식 `/mcp/v2`와 PAT를 설정한다. PAT 권한은 읽기 `boi.read`, 준비 `boi.draft`, HOTL 게시 `boi.execute.low`와 현재 사용자 역할을 따른다. 토큰을 저장소나 대화에 넣지 않는다.
4. [MCP 사용 순서](../agent_kit/references/database-intake.md)에 따라 연결 발견, 페이지 적재, Profile 재사용/확장, 게시, 새 세션 질문을 진행한다. 기존 승인된 Native 연결은 registration_discover/register 경로도 유지한다.

## 합성 예시

```sh
python examples/database/generate.py /PRIVATE/generated.sqlite --variant 47
```

- OPER: “RINSE-47의 목적·관리점·수행 조건은?” 먼지 제거, 배출수 탁도, 덮개 온도 조건을 각각 답한다. 조건을 변경하면 해당 지식을 교정하고 새 세션에서 현재 값을 확인한다.
- SVID: “ORBIT-47의 측정값과 설정값, 단위와 범위를 보여줘.” 역할과 단위를 유지하며 공란과 문서 사이의 범위 충돌을 드러낸다. Formula에는 별도로 선언된 계산식과 입력이 필요하다.
- DEXA: “모듈별 공정 연결 전체와 연결 건수를 보여줘.” 합성 DB에는 같은 연결 두 행과 미연결 모듈이 있다. native 물리 Profile에서 LEFT 관계와 행 단위 집계를 선언해 보존한다.

생성 코드는 처음부터 만든 예시다. 생성 DB와 실행 결과는 커밋하지 않는다. 이름·ID·값을 바꾸려면 `--variant`를 사용한다.

## 재현 검사

`python scripts/build_boi_local_runtime.py --check`는 설치 runtime이 제품 코드와 일치하는지 확인한다. `tests/test_database_source.py`는 페이지·중복·공란·권한·변경 스냅샷을 검사하고, `test_database_native_binding.py`는 실제 발급된 검토/Profile 연결과 재사용을 검사한다.

`tests/test_database_mcp_release.py`는 빈 디렉터리에 설치한 키트, 실제 HTTP MCP/API, 별도의 PostgreSQL을 사용해 원천 캡처·재개·게시·새 세션 읽기·최종 렌더링·조건 교정을 검사한다. 검사 전용 새 DB의 DSN을 `BOI_RELEASE_TEST_PG_DSN`으로 지정한다. 의미 판단은 명시적인 합성 검사 의견이며 독립 모델 평가나 사내 운영 승인을 뜻하지 않는다.

0.3.0 최종 출시 검증은 집중 계약/회귀와 설치 키트 MCP 전 구간 검사를 합해 125개를 통과했다. OPER 조건 교정, SVID 공란·역할, DEXA 중복 연결·미연결 객체와 현재 출처를 확인했다. Native 물리 매핑·집계와 Formula는 집중 회귀로 확인했다. API/MCP 이미지를 개발 checkout 마운트 없이 기동했으며 두 health 경로와 인증 없는 MCP 요청의 거절을 확인했다.

키트 ZIP은 별도로 생성할 수 있다. 목적 파일은 아직 존재하지 않는 경로로 지정한다.

```sh
python scripts/build_boi_local_runtime.py --check
python agent_kit/install.py --bundle /PRIVATE/boi-mcp-agent-kit-0.3.0.zip
```

ZIP은 선언된 설치 리소스와 해시를 포함한다. 원천 DB, 실행 상태와 게시 산출물은 패키지 리소스가 아니다.

현재 어댑터는 SQLite와 기존 SQLite 조회 게이트웨이다. 사내 DB별 연결 드라이버, 큰 단일 행/LOB 분할, 대규모 성능 평가와 웹 개편은 후속 범위다.

이 배포는 기존 Profile/native 실행기를 포함하되 특정 MES 원자료에 고정된 과거 평가 어댑터·정답 SQL·스냅샷 해시는 포함하지 않는다. 기존 연구 checkout과 이력은 별도로 유지한다. `BOI_DEXA_ACTUAL_ANSWER_ENABLED`와 역사적 fixture 실행 설정은 이 패키지의 기능이 아니다.

## 서버를 새로 구성할 때

기존 운영 서버가 있으면 기존 원천 정책/ledger/object 경로를 그대로 사용한다. 신규 서버는 저장소 루트를 build context로 하는 `docker-compose.mcp.yml`을 사용한다. 이 구성은 공개 코드·하네스만 이미지에 복사하며 원천 DB는 `/srv/boi-sources`에 읽기 전용으로 마운트한다.

인증 제공자 설정, PostgreSQL 비밀번호와 DSN, PAT 해시·세션 비밀, 외부 URL, 개인 설정 디렉터리와 원천 디렉터리는 커밋하지 않는 환경 파일에 설정한다. `config/database-sources.example.json`의 경로는 컨테이너 기준이다. 먼저 `docker compose -f docker-compose.mcp.yml build`를 실행한다.

처음 한 번만 다음 초기화를 실행한다. `BOI_PRINCIPAL`은 관리자가 지정한 실제 인증 principal이다.

```sh
docker compose -f docker-compose.mcp.yml run --rm --no-deps api \
  python scripts/initialize_mcp_state.py --state-dir /var/lib/boi/native \
  --principal "$BOI_PRINCIPAL" --valid-days 30
```

출력된 `BOI_SOURCE_INTAKE_POLICY_DIGEST`를 개인 환경 파일에 기록하고 `docker compose -f docker-compose.mcp.yml up -d`를 실행한다. 원천 정책은 store/derive/cite/model_input 권한과 만료 시각을 명시하며, 기존 디렉터리에 초기화를 다시 실행하면 거절한다. 실제 인증 principal과 연결 registry의 principal이 일치해야 한다. 만료·권한 변경은 운영자가 기존 정책/revision 절차로 갱신한다.
