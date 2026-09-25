# 로컬에서 준비하고 하나의 묶음으로 전달하기

사용자는 원천 자료와 원하는 활용을 설명한다. 외부 에이전트는 원문을 읽고 적합한 Profile·의미·조건·근거를 작성하며 기계검사 오류를 수리한다. 사람이 Profile JSON이나 개별 산출물 파일을 직접 작성·선택하는 흐름을 요구하지 않는다.

배포 kit의 [로컬 실행 도구](../scripts/boi_local.py)는 서버와 같은 계약 코드로 원천 셀, OKF 기본 구조, Profile 타입, 본문/주장/근거 연결과 검사 의견의 범위를 확인한다. [배포 기록](../runtime/provenance.json)은 원본 코드의 해시를 보존한다. 로컬 검사를 통과했다는 사실이 의미의 정확성, 독립 검토, 서버의 용도별 사용 자격을 대신하지 않는다.

## 에이전트 환경 준비

미상 항목을 정확한 원천 위치에 연결하려면 각 `records[].unresolved[]`에 `evidence: [{field_locator, quote, quote_occurrence?}]`를 명시한다. 문맥 셀은 기존 `context_fields`에 역할과 선택 이유도 선언해야 한다. 도구는 저자가 지정한 인용을 기존 서버의 `source_spans` 및 문서의 원천 문맥 결속으로 변환한다. 미상의 설명·의미 범위·facets·판단 라벨을 자동 변경하지 않는다. 이미 지정된 `source_spans`와 새 `evidence`를 함께 사용하지 않는다.

먼저 해석 초안을 조립하고 `use_preparation.source_review_inventories`를 읽는다. 각 문서의 `inventory_digest`, 항목별 `item_digest`, `required_fields`는 서버가 참조를 치환하기 전의 정확한 원본 초안에 대한 값이다. 그 원천 범위를 실제로 검토한 뒤 `statement_review` 의견과 해당 digest를 작성한다. 가져온 native 참조로 digest를 다시 계산하지 않는다. 원천 결속이나 미상 설명이 바뀌면 바뀐 inventory를 다시 검토해야 한다. 보고서는 누락된 근거와 결속 범위 밖 인용을 따로 표시하며, 의견이나 긍정 판정을 생성하지 않는다.

`evidence`와 `source_spans`를 생략한 전역 미상은 해당 문서에 결속된 모든 원천 필드를 검토 범위로 삼는다. assertion/parameter 아래 미상은 해당 노드의 원천 문맥을 사용한다. 이 범위는 원천이 실제로 없다는 판정과 다르다. 외부 기존 source span의 실제 원천 연결과 현재 열람 권한은 여전히 서버에서 확인한다.

kit 디렉터리 안에서 Python 3.10 이상으로 전용 환경을 만들고 [해시가 고정된 의존성](../runtime/requirements.txt)을 설치한다. 제품 저장소, DB, PYTHONPATH나 개발자 스크립트가 필요하지 않다. HTTP 보조 도구만 사용할 때는 이 의존성이 필요 없다.

```sh
python -m venv .venv
.venv/bin/python -m pip install --only-binary=:all: -r runtime/requirements.txt
.venv/bin/python -I scripts/boi_local.py doctor
```

Windows에서는 `.venv/bin/python` 대신 `.venv/Scripts/python.exe`를 사용한다. 운영체제별 실행 증거는 별도로 확인하며 설치 가능성만으로 다른 호스트 인수를 통과 처리하지 않는다. 원천과 본문이 들어 있는 작업 디렉터리는 사용자의 로컬 영역에 둔다.

## 준비 흐름

계산에 사용할 입력 정의는 record의 선택 필드 `parameters`에 작성할 수 있다. 이는 관측값이 없는 정의이며, 측정/설정 역할·대상·물리량·단위·적용 범위와 원문 근거를 명시한다. `unit_definition`, `quantity_definition`에는 실제 읽은 기존 Wiki 개정을 넣는다. 조립기는 명시된 의존성과 의견의 입력 참조를 묶지만 단위 이름에서 변환식을 만들거나 현재 서버 권한을 보증하지 않는다. 전체 parameter와 `depends_on`으로 연결한 주장을 source opinion에서 함께 평가한다. 서버의 등록된 정의 검사와 `formula_input` 자격을 받아야 기존 Formula 입력으로 사용할 수 있다. 적용 조건·예외·시점 조건을 아직 평가할 수 없는 정의는 계산 자격이 보류되며 원문 읽기는 유지된다. 계산 시 관측값·관측 시각을 별도로 제공하고 실제 센서 연결을 주장하지 않는다.

kit 0.2.30의 `calculation_context`는 명시된 가정을 전제로 한 계산을 표현한다. 해석한 parameter는 `interpretation`을 유지하고, 각 가정의 `meaning_pointers`로 해당 parameter의 모든 미상·조건·예외를 빠짐없이 연결한다. `input_scope`는 실제 `depends_on` 범위 안에서 읽은 원천 주장의 정확한 값을 참조한다. 모델·모듈·위치 등의 동일성을 이름으로 추정하거나 입력에서 생략해도 되는 것으로 처리하지 않는다. `formula_input` 의견에는 전체 미상 목록과 정확한 원문 인용을 결속한 `boi/source-formula-review@1` 검토가 필요하다. 준비·pack 단계는 검토 누락과 목록 변경을 표시하며, 원천 충실성·문맥 동일성의 미상은 서버에서 계속 자격을 막는다.

계산할 때는 현재 선택한 동일 개정과 자격을 읽고 `scenario_inputs`에 정의의 context digest, 명시적인 개발 입력 설명, 가정별 참·미상과 입력 범위 값을 제공한다. 실제로 제공받지 않은 가정·장비값을 만들지 않는다. 개발용 시나리오는 가정임을 명시한다. 필요한 가정·범위·값·시각이 없거나 서로 맞지 않으면 결과는 미상 또는 계약 오류이며 리터럴 계산으로 바꾸어 연결 성공을 주장하지 않는다. 조건부 수치 결과는 원천 미상이나 실제 센서 연결을 해결하지 않는다. 게시 후 정책 변경에 따른 재검토는 현재 서버 schema의 `formula_reviews`와 기존 원천 인용을 사용하며 이전 의견·개정은 보존한다.

다음 명령의 JSON은 에이전트 내부 작업물이다. 사용자는 완성된 묶음과 읽기 쉬운 설명을 받는다.

먼저 `schema --output authoring-contracts.json`으로 설치된 버전의 실제 공유 계약과 입력 필드 대응을 읽는다. 주장을 문장마다 나열할 필요는 없다. `body_quote`로 사람이 읽을 자연스러운 문단의 정확한 구간을 주장에 연결할 수 있다. 인용 구간의 일치와 그 문단이 주장을 충실하게 표현하는지는 별개이며 후자는 원문 대조 의견에 포함한다.

1. `inspect --source FILE.xlsx --output fields.json`으로 원본 필드·좌표·빈칸·수식 표기를 읽는다. 이 명령은 도메인이나 필드 역할을 선택하지 않는다.
2. 원문과 가이드를 읽은 에이전트가 필드 역할을 명시한 layout을 작성한 뒤 `inventory --source FILE.xlsx --layout layout.json --output inventory`를 실행한다. 원문, 제공된 모델 답변, 검토 메모와 미분류 영역을 구분한다. 제공된 답변을 의미 작성의 정답으로 사용하지 않는다.
3. 에이전트가 spec의 `profile`, `records`, `assessments`를 작성한다. 본문은 자연스러운 설명으로 쓰고 주장의 원문 인용·조건·부정·예외·시간·미상을 함께 연결한다. 해석 근거가 없는 동일성·단위·센서 binding이나 긍정 판정을 자동 생성하지 않는다.
4. `assemble --spec spec.json --output checked-bundle`을 실행한다. 새 디렉터리에만 기록하며 실패한 시도와 이전 묶음을 덮어쓰지 않는다. 검사 오류의 해당 필드를 고치고 새 출력 디렉터리로 재검사한다.

kit 0.2.23부터 조립 결과의 `use_preparation`은 선언한 각 지식·용도와 제출된 의견을 대조한다. `incomplete`이면 `gaps`의 object_id·purpose·required_meaning_pointers 또는 누락된 정확한 개정을 확인해 보완한다. 초안은 남겨 원천 검토에 쓸 수 있지만 `pack`은 실제 manifest·내용·의견 바이트를 다시 검사해 필수 검토가 빠진 묶음의 전송 파일 생성을 거절한다. `filter`와 `traverse`에는 각각 자기 용도의 원천 inventory 검토가 필요하다. 부정적이거나 미상인 의견을 긍정으로 바꾸라는 뜻은 아니다. `reviews_present`는 필요한 의견이 제출됐다는 뜻이며 사용 자격·원천 완전성·현재 권한은 서버가 별도로 판정한다. 명시된 외부 KnowledgeRevision이 manifest에 빠졌는지도 표시하지만, 실제 관계 대상의 동일성·타입과 현재 개정은 공식 서버 검사를 거쳐야 한다.

kit 0.2.28은 검토 의견의 `existing_revisions`가 proposal의 **필수 native dependency** 목록과 정확히 일치하는지도 확인한다. 읽기 응답의 이전 개정이나 선택적 이력을 의견의 입력 목록에 함께 넣지 않는다. 이력은 기존 개정·manifest의 참조로 보존하고, 누락·과잉 입력은 업로드 전에 해당 개정과 함께 표시한다. 이 검사는 원천 판단이나 부정 의견을 바꾸지 않는다.

현재 게시물의 미자격 이유는 `boi_knowledge_qualification`의 `schema`를 읽고 `status`에 지식의 정확한 현재 개정을 지정해 확인한다. `KnowledgeUseQualification` 참조를 일반 asset reader에 넣는 경로와 구분한다. 진단을 위해 `refresh`를 실행하지 않는다.

원천 행 밖의 헤더나 복원·추정 기록을 근거로 쓰려면 해당 record의 `context_fields`에 `field_locator`, inventory에 선언한 `role`(`source`, `metadata`, `review_note`), 사용하는 `reason`을 명시한다. 최대 64개 셀이며 인용은 실제 원천 바이트와 대조한다. `review_note`는 명시적으로 요청할 때만 읽고, 제공된 모델 답변은 이 경로의 근거로 읽지 않는다. 각 지식에는 자기 원천 행의 근거가 반드시 하나 이상 있어야 한다. 보완 기록의 분류·전사 조각·수정값·근거를 함께 보존하고, 추정한 경로나 OCR 교정을 확인된 실물 binding으로 승격하지 않는다. 로컬 검토의 ‘원문과 대조’에서 선언한 주변 자료와 사용 이유를 함께 확인할 수 있다.
5. `review --spec spec.json --bundle checked-bundle --output review.html`로 원문과 본문을 함께 볼 수 있는 로컬 자료를 만든다. `pack --bundle checked-bundle --output prepared.boi-bundle.zip`으로 기존 manifest와 원천·본문·검사 의견의 정확한 바이트를 묶는다.

각 명령은 `.venv/bin/python -I scripts/boi_local.py COMMAND ...` 형태로 실행한다. 현재 로컬 원천 adapter는 XLSX와 서버에서 캡처한 DB JSON 페이지다. DB는 [DB 적재·재사용](database-intake.md)을 따른다. 다른 원천 형식은 지원 계약을 확인하고 불가 범위를 드러낸다. 도구는 LLM을 호출하거나 사용자를 대신해 확인하지 않는다.

같은 도메인에 자료를 추가할 때는 이미 읽은 Wiki Profile을 재사용할 수 있다. kit 0.2.20 이상에서 spec의 `existing_profile_revision`에 정확한 `{ref, revision_digest}`를 넣고, `profile`에는 그 개정에서 읽은 선언을 변경 없이 제공한다. 이때 Profile과 그 schema 원천을 새로 생성하지 않으며 새 지식·검토 의견·manifest가 기존 개정에 의존한다. 그대로 재사용할 때는 `profile_logical_id`를 사용하지 않는다. 이름이 같다는 이유로 개정을 선택하거나 로컬에서 선언을 바꿔 기존 참조에 연결하지 않는다. 로컬 검사는 제공된 선언의 타입을 검사할 뿐 해당 선언과 서버 개정의 일치·현재 권한·사용 자격을 증명하지 않는다. 서버는 게시 시 실제 Profile과 현재 접근 권한을 다시 확인한다. 새 Profile을 작성하는 경우에는 이 필드를 생략한다.

원천의 중요한 의미가 기존 Profile에 담기지 않으면 확장 내용을 명시해 같은 Profile의 개정을 제안한다. `profile_base_revision`에 실제 기준 개정을 넣고 기존 namespace와 `profile_logical_id`를 유지한다. 이때 `profile_correction`을 함께 제공해야 한다. 여기에는 현재 공간 정책의 정확한 `expected_policy_revision: {ref, revision_digest}`, 변경 이유인 `reason`, 기존 선언과 새 스키마 원천의 차이를 설명하는 `source_difference`를 넣는다. 이 설명은 manifest의 기존 교정 계약에 결속되며 권한이나 의미상 정확성을 부여하지 않는다. 새 지식은 제안한 Profile을 참조하며, 이전 지식의 Profile 참조·본문·자격을 자동으로 바꾸지 않는다. 이 필드는 `existing_profile_revision`과 함께 사용할 수 없다. 영향과 동시 수정·편집 권한은 기존 게시 절차에서 검사하고 묶음 확인에 포함한다. 새 Profile의 스키마 원천은 새 개정에 결속하고 이전 원천·이력은 보존한다. 일반 지식 본문의 교정은 기존 원천 유지 계약을 따른다. Profile을 복제하거나 미상과 조건을 지워 충돌을 우회하지 않는다.

하나의 원천 행에서 여러 개념을 작성할 수 있다. 원천 좌표는 근거 위치이며, 지식의 `logical_id`와 구분한다. 한 번 정한 지식 식별자는 원천 행이 이동했다는 이유로 바꾸지 않는다. 역할·이름이 비슷하다는 이유로 개념의 동일성이나 물리적 연결을 확정하지 않는다.

같은 묶음의 지식을 관계 값으로 참조할 때는 `{"kind":"object","target_object_id":"작성한 대상의 object_id"}`를 쓴다. Profile에 관계의 subject/target type을 선언해야 한다. 조건이 다른 지식에 적용되면 atom의 `subject_ref` 대신 `subject_object_id`를 명시한다. 조건·부정·가능성을 제거해 관계를 단정하지 않는다. 서버의 안정적인 식별자는 확인한 manifest와 현재 작성 권한에서 결정되며 에이전트가 추측해 입력하지 않는다.

이 참조에는 manifest @2와 이를 지원하는 서버가 필요하다. 서로 참조하는 지식은 같은 게시 단위로 묶이고, 단위 한도를 넘으면 로컬에서 재구성해야 한다. 대상의 타입·현재 개정은 서버에서 다시 검사한다. 기계검사 통과는 해당 관계의 의미가 참이라는 판정이 아니다. 검토 화면의 ‘연결된 지식’에서 대상과 근거를 열 수 있으며, 원천 처리 건수와 작성한 지식 개수는 따로 표시한다.

## HOTL 전송·재개

`boi_knowledge_work(operation="publication")`의 `phase="schema"`를 먼저 읽고 `preview`에 정확한 manifest와 고정 idempotency_key를 제출한다. 원천·새 본문은 아직 전송하지 않는다. `impact`에 반환된 `bundle_ref`와 `preview_digest`를 넣어 현재 model_input 권한으로 선언된 영향 범위를 준비한다. `admit`에는 같은 `bundle_ref`, `manifest_digest`, `preview_digest`와 반환된 `impact_ref`를 넣는다. 서버의 현재 쓰기 정책 아래 자동 반영하는 이 HOTL 경로는 사람의 항목/묶음 Confirm이나 Inbox 열람을 요구하지 않는다. 호출자가 승인 플래그·권한·actor를 보내는 형식은 없다.

서버는 실제 인증 PAT의 `boi.draft`·`boi.execute.low`, 현재 editor/실행 역할, source의 store/derive/model_input 권한, 대상 공간·정확한 개정·영향·크기·단위 및 CAS를 검사한다. 부족한 권한을 새로 부여하지 않는다. admission은 `authenticated_hotl_admission`으로 기록하며 `human_confirmation_observed=false`를 유지한다. 기존 `confirmation` 이름의 내부 호환 필드/receipt는 그 실제 mechanism과 함께 해석한다. 브라우저의 서명된 확인 경로와 과거 확인 이력도 그대로 사용할 수 있지만 HOTL 경로의 필수 단계가 아니다.

admission 뒤 공식 바이너리 `PUT /api/v2/local-bundles/{digest}/objects/{object_id}?offset={offset}`로 manifest에 등록된 정확한 바이트를 보낸다. `Content-Type: application/octet-stream`, 실제 `Content-Length`, `X-Boi-Chunk-Digest`와 schema/status의 chunk 한도를 지킨다. 파일 내용은 MCP JSON 인자에 넣지 않는다. 중단되면 같은 bundle_ref의 `status`와 받은 offset을 읽어 남은 부분만 이어간다. 미확정 admission은 status로 확인하고 같은 exact admit 요청을 재사용한다. source/manifest/preview/현재 권한이 달라지면 기존 admission을 다른 작업에 재사용하지 않는다.

kit 0.2.21 이상의 공식 HTTP 도구는 `publication --request-file request.json`으로 현재 schema가 제공한 `{phase, payload}`를 전달한다. schema 요청은 `{"phase":"schema","payload":{}}`이며 task_ref는 필요하지 않다. 준비된 묶음의 admission을 확인한 뒤 다음 명령으로 자동 전송한다. API 원점과 기존 PAT는 `BOI_BASE_URL`, `BOI_PAT` 환경에 설정하며 토큰 값을 명령이나 결과에 넣지 않는다.

```sh
python -I scripts/boi_knowledge_work.py publication --request-file request.json --state-dir private-journal
python -I scripts/boi_knowledge_work.py upload --archive prepared.boi-bundle.zip --bundle-ref RETURNED_BUNDLE_REF --state-dir private-journal
```

업로더는 현재 status와 archive의 manifest·전체 바이트·각 chunk를 대조하고 받은 offset을 건너뛴다. 응답이 미확정이면 그 실행은 즉시 멈춘다. 같은 명령을 명시적으로 다시 실행하면 먼저 status를 읽고 남은 offset만 보낸다. 새로운 bundle이나 admission을 자동 생성하지 않는다. 성공한 전송은 prepare/validate/qualify/preflight/publish를 실행하거나 사용 자격을 부여하지 않는다.

SDK2가 필요한 호스트는 `python -m pip install -r runtime/mcp-requirements.txt`로 별도 전송 의존성을 설치한 뒤 `scripts/boi_mcp.py --tool boi_knowledge_work --request-file mcp-request.json --state-dir private-journal`을 사용한다. `BOI_MCP_URL`에는 공식 MCP URL을 둔다. 파일은 정확한 MCP 인자 `{operation:"publication", request:{phase, payload}}`이다. 현재 도구 설명과 입력 스키마는 `--describe-tool boi_knowledge_work --state-dir private-journal`로 조회한다. 수신한 도구 오류는 `tool_error_received`와 오류 코드를, 응답 유실·프로토콜 오류는 `outcome_unknown`을 남기며 자동 재시도하지 않는다. 도구 오류만으로 실행의 롤백을 추정하지 않는다. 이 배포 어댑터는 공식 SDK2와 HTTP 전송 의존성을 사용하고 저장소의 agent/model runner를 가져오지 않는다.

일반 지식의 조건을 교정할 때는 현재 지식·Profile·공간 정책·원천의 정확한 개정을 읽는다. 같은 namespace/logical_id의 record에 `previous_revision`과 `correction: {expected_policy_revision, reason, source_difference, feedback_refs?}`를 함께 지정하면 어셈블러가 기존 서버 계약의 `operation:"revise"`로 결속한다. `record.existing_sources`에는 보존할 기존 원천의 정확한 ArtifactEnvelope를 넣는다. 새 workbook의 인용과 기존 원천 이력을 함께 유지하며, 도구가 이전 개정이나 정책·원천 목록을 추정하지 않는다. 두 개정 필드를 모두 생략한 경우에만 기존 create 동작을 유지한다. 서버는 원천 보존, 편집 권한, 현재 head와 영향, 새 검사와 용도별 결정을 다시 요구한다. 이전 원천과 개정·실패 이력은 보존하며 게시된 새 개정을 다시 읽어 실제 조건과 자격을 확인한다.

변하지 않은 관계 대상은 다시 작성하지 않는다. 현재 공식 읽기에서 확인한 `stable_id`, 정확한 `revision`, `object_type: {revision, pointer}`를 `spec.existing_records`의 명시적 대상 키에 선언한다. 주장 값의 `target_object_id`나 조건 원자의 `subject_object_id`에서 그 키를 사용한다. 도구는 현재 선언된 타입을 비교하고 실제 stable identity와 필수 `relation_target` 의존 개정, manifest 및 검토 입력의 외부 개정을 결속한다. 그 대상을 새 change로 만들지 않는다. 기존 대상의 현재 head·타입·열람 권한은 서버가 다시 확인하며, 로컬 선언만으로 검증됐다고 표시하지 않는다.

에이전트는 같은 bundle_ref로 서버 검사·용도별 판정·게시 단계를 이어가고, 응답이 미확정이면 기존 상태를 조회해 복구한다. 임의로 새 실행을 시작하지 않는다. 현재 권한·충돌·게시 단계의 authority는 서버 계약을 따른다. 게시된 같은 개정으로 [탐색과 typed 질의](typed-knowledge-query.md), 출처 확인, 피드백과 교정까지 이어간다.

기존 상세 참조의 저장소 전용 Python 예시는 과거 호환 경로다. 새 로컬 준비에는 이 배포 경로를 사용한다. 설치와 기계검사만으로 실제 사용자 인수나 지식 활용 완료를 보고하지 않는다.
