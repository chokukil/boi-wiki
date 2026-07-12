# BoI Wiki Pilot Readiness Review (2026-07-09)

사내 Pilot 운영 준비 관점에서 프로젝트 전체(아키텍처 문서, boi_api / action_gateway / event_adapter / boi_wiki_mcp 코드, 웹 UI 템플릿, 카탈로그, 테스트)를 리뷰한 결과다. 개발 착수 전 판단 자료로 쓰기 위한 문서이며, 코드 변경은 하지 않았다.

---

## 1. 취지 대비 총평

프로젝트의 취지 — "1인 1 Agent의 업무 맥락을 조직 지식(BoI)으로 자산화하고, 이벤트→액션 파이프라인을 커넥터 무관하게 돌린다" — 는 코드에 실제로 구현되어 있다. Event Router가 커넥터를 전혀 모르고 Action Gateway에만 위임하는 구조, 문서 단위 3중 ACL(경로/owner/acl_policy), 고위험 액션 승인 게이트, trace_id 기반 감사 로그까지 골격은 취지에 충실하다.

다만 현재 상태는 **"데모를 잘 통과하는 PoC"이지 "수십 명이 매일 쓰는 Pilot"은 아니다.** 격차는 세 축이다.

1. **일반 구성원 기준 UI가 아직 개발자 도구다** — Inbox 승인 여정은 훌륭하지만, 나머지 화면에 event type 문자열·trace_id·curl·JSON·Git 커밋이 그대로 노출된다.
2. **인증 기본값이 Pilot에 부적합하다** — dev 모드 신원 위조, 공유 admin 서비스 토큰, 커밋된 기본 비밀.
3. **이벤트 신뢰성·동시성이 실사용을 못 버틴다** — 멱등성 없음, DLQ 소비자 없음, 잠금 없는 파일 쓰기, LLM 동시성 1.

---

## 2. 잘 만들어진 부분 (지킬 것)

- **커넥터 무관 아키텍처가 문서가 아니라 코드로 존재.** 새 실행 채널은 Action Gateway 커넥터 추가만으로 붙는다 (`docs/CONNECTOR_AGNOSTIC_ARCHITECTURE_V0_4.md`, `event_adapter/app/main.py` dispatch 경로).
- **Inbox 승인·조치 여정** (`boi_api/app/templates/inbox.html`): 검증 보고서 확인 → 승인/반려/보류/추가근거 4종 판단 → 필수 사유 → Data Lake 근거 첨부 → 처리 이력의 폐루프. 마이크로카피("사유 남기고 기록")도 업무 친화적. **이 화면이 Pilot UX의 기준점이 되어야 한다.**
- **empty state / 한국어 UX 라이팅 / aria 접근성**이 전반적으로 우수.
- **다층 ACL fail-closed**: private 문서는 경로·owner·acl_policy 삼중 일치 필요 (`boi_api/app/access_policy.py`).
- **승인 게이트가 게이트웨이에서 강제**: `approval_required` 액션은 `approved_by` 없이 실행 차단 (`action_gateway/app/main.py`). MCP 쓰기 도구는 `user_confirmed` 이중 확인.
- **감사성**: 구조화 JSONL + trace_id 상관관계 + Kafka `boi.audit` 미러링, 문서 Git 버전 관리.
- **등록 마법사의 자연어 추상화 시도**("바로 발생 / 조건이 맞으면 / 반복되면…")는 방향이 옳다 — 다만 아직 절반만 됐다(아래 3.1).

---

## 3. 개선점 — 우선순위별

> **2026-07-09 갱신 — 인증 전제 확정**: 사내는 Keycloak을 쓰지 않고, **별도 자체 SSO가 사번만 인증해 넘겨주는** 방식이다. 코드상 `trusted_header` 경로(`X-Hynix-Employee-Id` 등 신뢰)에 해당하며 dev 모드는 비활성으로 배포한다. 이에 따라 인증은 "코드 대공사"가 아니라 **배포 게이트 체크리스트(P0-보안)** 로 축소되고, 실제 개발 P0 무게는 **이벤트 신뢰성·동시성**으로, 그 다음은 **일반 구성원 UI/UX**로 이동한다. 아래 우선순위가 최종본이다.

### P0-보안. 배포 게이트 (대부분 설정·인프라, 코드 변경 최소)

자체 SSO가 신원을 책임지므로 인증 로직 재작성은 불필요하다. 다만 `trusted_header` 모델은 **코드 레벨 안전망이 0**이라, 아래는 앱이 아니라 배포 경계에서 반드시 잠가야 한다.

- **포트 미노출**: boi-api(28000)·action-gateway(8100)·mcp(8200)를 호스트에 직접 노출하지 말 것. 오직 사내 SSO 프록시 뒤에서만 접근. 직접 도달 가능하면 아래 방어가 전부 무력화된다.
- **프록시가 인바운드 헤더 strip**: 클라이언트가 보낸 `X-Hynix-*` / `X-Employee-Id`를 프록시가 제거하고 SSO 검증 결과로만 주입. strip 안 하면 사용자가 자기 사번·역할(admin 포함)을 헤더로 덮어쓸 수 있다.
- **시크릿 3종 교체**: `SERVICE_TOKEN`, `BOI_SESSION_SECRET`, `LANGFLOW_SECRET_KEY`의 `*-change-me` 기본값 교체. 특히 `SERVICE_TOKEN`은 보유 시 **인증 모드와 무관하게 임의 사번을 admin으로 사칭**하는 만능 키다(`boi_api/app/main.py` current_identity의 서비스토큰 분기). 리포지토리에 `.env` 실값이 커밋됐는지 점검.
- **MCP 잠금**: `MCP_REQUIRE_SERVICE_TOKEN=true`. 꺼져 있으면 MCP가 사실상 무인증 임의 사번 admin 프록시가 된다.
- **쿠키·스코프**: HTTPS 배포이므로 `BOI_COOKIE_SECURE=true`, 파일럿 대상만 받도록 `BOI_ALLOWED_EMPLOYEE_IDS` 설정.
- **(작은 코드 수정) H-3 dev 폴백 제거**: `identity_for_employee`가 캐시 미스 시 `dev_identity()`로 폴백해, 멀티워커(`BOI_API_WORKERS>1`) 환경에서 사번 100001이 admin으로 오판될 수 있다. non-dev 모드에서 이 폴백을 막거나 워커 간 신원 캐시를 공유. **자체 SSO를 써도 남는 실제 코드 버그이므로 이 항목만 개발 대상.**
- **actor 신뢰**: 이벤트 본문 `event.actor.employee_id`를 그대로 소유자로 써서 타인 명의 private BoI 물질화가 가능. Kafka를 사내에 붙일 경우 발행 경로 검증(또는 Kafka ACL)이 방어선.

이 블록은 SSO 프록시 설정 + env 값 교체가 대부분이라 **개발 스프린트가 아니라 배포 런북 항목**이다. 아래 P0-신뢰성부터가 실제 개발 착수 지점이다.

### P0-신뢰성. Pilot 오픈 전 필수 (실제 개발 착수점)

**P0-1. 이벤트 멱등성 (중복 문서 방지)**
- Kafka at-least-once인데 event_id 기반 dedup이 없어 재처리 시 같은 이벤트가 새 boi_id로 문서를 계속 만든다. `data/boi/private/100001/`에 유사 문서 수천 개 누적이 이미 그 징후. event_id dedup 저장소 도입이 필요하다. **일반 구성원에게 "같은 보고서가 3개 떠요"는 신뢰를 즉시 무너뜨리는 버그다.**

**P0-2. DLQ 소비·재시도 부재**
- 실패 이벤트가 `boi.dead-letter`로 가면 끝 — 소비자·알림·재시도가 없어 영구 유실. 최소한 DLQ 컨슈머 + 운영자 알림 + 수동 재처리 경로 필요. 재시도(backoff)도 전무해 다운스트림 일시 장애가 곧장 유실로 이어진다.

**P0-3. 파일 저장 동시성**
- 문서 쓰기(`path.write_text`)와 액션 로그 append(줄 수 세고 쓰기)가 잠금 없이 수행. `BOI_API_WORKERS>1`이면 threading.Lock도 무의미. 파일락 또는 쓰기 직렬화, 워커 수와 락 전략 정합 필요.

### P1. Pilot 초기 사용성 좌우 (UI/UX)

**P1-1. 단일 UI 안에서 점진적 노출(progressive disclosure)로 정리 — 가장 큰 지렛대**
모드를 나누지 않고, 하나의 화면이 모든 구성원에게 쉽게 읽히도록 정보 위계를 재설계한다. `Event Broker`, `Action` 같은 도메인 용어는 구성원이 학습할 수 있는 개념이므로 유지한다. 원칙은 "숨기기"가 아니라 **"업무 답이 먼저, 구현 근거는 한 겹 아래"**:
- **화면의 1차 정보는 업무 언어로**: 이벤트는 `name_ko`("회의 종료")를 주 표기로, `meeting.closed.v1`은 보조 표기(작은 코드 배지)로. 지금은 순서가 반대다(`index.html:35`, `events.html:24`).
- **식별자·원시 데이터는 접기**: trace_id, boi_id, boi_uri, request_id, connector_kind, raw_log_ref, "Raw JSON 불러오기"는 기본 접힘(details)으로 내리고, 필요한 사람은 한 클릭으로 편다. doc.html의 lazy-load 토글 패턴이 이미 좋은 선례 — 이를 workflow_status·actions 화면까지 일관 적용.
- **명령어 → 버튼**: doc.html의 curl 명령 블록(Promotion/Workflow 섹션)은 "승격 요청" / "워크플로 시작" 버튼으로 대체하고, API 호출 예시는 접힌 "개발자 참고"로.
- **용어는 배우게 돕기**: 이미 있는 `업무 용어` 사전을 활용해, Event Broker·Action·Connector 등 용어에 hover 툴팁/링크로 한 줄 설명을 붙인다. 용어를 없애는 게 아니라 첫 만남의 문턱을 낮추는 방향.
- **라벨 일관성**: `Visibility`/`Limit`/`Preview` 등 흩어진 영어 UI 라벨은 한국어로 통일하되, 도메인 고유명사(Event Broker, Action, BoI)는 유지.

**P1-2. 편집 모델 재설계**
- 본문 편집이 raw Markdown/YAML textarea + `Apply & Commit`(Git 커밋) + base_sha256 + OKF lint 피드백 — 개발자 워크플로 그대로다. 일반 구성원에게는 위지위그 또는 폼 기반 편집 + "저장" 한 단어로 추상화하고, Git/검증은 뒤에서 돌리기.
- 등록 마법사(`registration_new.html`, 883줄)의 JSONPath·조건 JSON·Cron·webhook path는 "고급 설정"에 있어도 밀도가 과함. 일반 구성원용 경로는 템플릿 선택형으로.

**P1-3. 능동 알림 부재**
- 승인 요청이 와도 본인이 `/inbox`를 열어야 안다. Pilot에서 승인 지연 = 워크플로 전체 정체. 최소: 이메일/사내 메신저 알림 + nav 뱃지 카운트. 승인이 이 시스템의 핵심 인간 개입 지점이므로 우선순위 높음.

**P1-4. 온보딩 부재**
- 투어·튜토리얼·첫 사용 안내 0건. 게다가 `index.html`의 PoC Guide는 직원에게 Python CLI 명령을 안내한다. 첫 방문 투어(3~5스텝) + 역할별 시작 가이드("승인자는 여기부터")로 교체. 플로팅 에이전트(pet_agent)가 이미 있으므로 온보딩 시나리오를 에이전트에 태우는 것도 방법.

**P1-5. 검색 품질**
- 현재는 문자열 필터 수준(자동완성·오타보정·랭킹 없음). "문서 이름을 모르는 직원이 찾는" 경험이 취지의 핵심인데 가장 약하다. BoI Wiki MCP에 검색 도구가 이미 있으니, 플로팅 에이전트 기반 자연어 검색을 1차 검색 UX로 승격하는 것이 빠른 경로.

**P1-6. DEV 잔재 정리**
- 상단 셸의 사번 전환 드롭다운·DEV 칩이 Pilot 빌드에 노출되지 않는지 확인.

### P2. Pilot 중 성능·운영

- **LLM 동시성 1** (`BOI_AGENT_LLM_MAX_CONCURRENCY=1`): 수십 명 동시 사용 시 에이전트 응답이 즉시 병목. 상향 + 대기 UX(스트리밍/진행 표시) 필요.
- **전량 스캔 구조**: accessible_docs가 전체 마크다운을 읽어 캐시, 액션 로그 조회가 파일 풀스캔. 문서·로그 증가에 따라 선형 열화 — Pilot 규모는 버틸 수 있으나 모니터링 지표(응답시간) 걸어두고 인덱스 도입 시점 판단.
- **오류 은폐**: 광범위한 `except Exception` + print, aiokafka 로그 CRITICAL 차단. 실패가 조용히 사라진다. 구조화 로깅 + 운영자 대시보드/알림 최소선 확보.
- **git auto-commit 부하**: 문서 쓰기마다 subprocess git 커밋 — 대량 이벤트 시 경합. `BOI_AUTO_PUSH`는 반드시 false 유지.
- **런타임 생성물과 소스 분리**: `data/boi/private/`의 자동 생성 문서 수천 개가 리포지토리 트리에 섞여 있음. Pilot에서는 콘텐츠 저장소를 코드 리포와 분리.
- **테스트 공백**: 인증 우회 negative 테스트, 멱등성/중복 재처리, 동시성, 부하 테스트가 없다. 현 테스트는 데모 산출물 검증에 편중. P0 항목 수정 시 해당 회귀 테스트를 같이 추가.
- **최상위 README 부재**: 운영 인수인계·장애 대응 관점에서 설치/기동/장애 runbook 1장 필요.

---

## 4. 권장 진행 순서 (자체 SSO 전제, 개발 착수 시)

0. **배포 게이트(P0-보안)** — 개발이 아니라 인프라/설정. SSO 프록시 뒤 배치 + 포트 미노출 + 헤더 strip + 시크릿 3종 교체 + MCP 토큰 on + `BOI_COOKIE_SECURE`. **여기에 개발 리소스를 쓰지 말 것.** 단 H-3 dev 폴백 제거만 작은 코드 수정으로 포함.
1. **이벤트 신뢰성 스프린트** (P0-1,2,3) — 멱등성 + DLQ 소비자 + 파일락. 이것이 실제 개발 P0. "같은 보고서 중복 생성"과 "실패 이벤트 조용한 유실"이 Pilot 신뢰를 직접 깎는다.
2. **일반/전문가 모드 분리 + 알림 + 온보딩** (P1-1,3,4) — Pilot 첫인상 결정. 인증을 SSO가 가져간 만큼 여기에 무게를 더 실을 수 있다.
3. **편집 모델·검색 개선** (P1-2,5) — Pilot 피드백 받으며 반복.
4. P2(LLM 동시성·성능·운영 관측성)는 Pilot 지표 보며 순차 대응.

핵심 판단: 자체 SSO가 신원을 책임지면서 **보안은 배포 체크리스트로 축소**됐다. 아키텍처는 다시 만들 필요가 없으니, 개발 역량은 (a) 이벤트 신뢰성(멱등성·DLQ·동시성), (b) 잘 만든 Inbox 수준의 UX를 나머지 화면으로 확장, 이 둘에 집중하는 것이 옳다.
