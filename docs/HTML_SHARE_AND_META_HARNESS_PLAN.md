# HTML 공유 + 단축주소 + 메타 하네스 통합 계획 (v1.0)

상태: **확정** — §7의 4개 결정 항목이 2026-07-17 사용자 확인으로 확정됨. 작성일: 2026-07-17.

## 1. 배경과 목표

BoI Wiki는 OKF Markdown 정본 + BoI Profile 메타데이터를 기반으로 SOP → Workflow/Task → Event Broker → Action의 업무 런타임과, 하네스를 통한 에이전트 지식 저작을 이미 갖추고 있다. 이번 확장의 목표는 세 가지다.

1. **HTML 보고서 통합** — 사내에서 유행 중인 self-contained HTML 보고서를 BoI Wiki가 1급으로 수용한다. (a) 우리 파이프라인/에이전트가 만드는 HTML, (b) 우리와 무관하게 사용자가 만든 HTML 둘 다. 웹에서 "아주 자연스럽게" 렌더링되어야 한다.
2. **단축주소** — `http://wiki.skhynix.com/{name}` 형태의 사내 단축주소. 파일명 기반 기본 이름, 수정 가능, 중복 체크, 본인 것만 업데이트 가능. 로컬/테스트 환경에서도 동일하게 동작.
3. **하네스·루프 엔지니어링 강화** — HTML까지 포함한 모든 콘텐츠가 동일 하네스로 저작·검증되고, 저장으로 끝나지 않고 진화하는 루프(지식자산화)를 갖춘다. 메타 하네스(하네스 자체의 진화 체계) 포함.

## 2. 현재 상태 진단 (탐색 결과 요약)

### 2.1 콘텐츠 모델 (OKF + BoI Profile)
- 스키마의 정본은 `boi_api/app/okf.py` (별도 JSON Schema 없음). 필수 필드 12종(`boi_id`, `visibility`, `acl_policy`, `owner`, `status` 등), 경로↔ACL 일치 검증, 링크 그래프, `_media` 이미지 매니페스트(sha256) 검증.
- **HTML은 어디에도 1급 타입이 아님.** 린트는 `*.md`만 순회, 내부 링크는 `.md`만 그래프에 편입, 허용 미디어는 이미지 확장자뿐. Data Lake(MinIO) artifact 업로드에서 `text/html`은 opaque binary로 취급되고 다운로드 강제(`Content-Disposition: attachment`).
- `data/boi/` 아래 `public/ | team/{team_id}/ | private/{사번}/` 스코프. `boi_id`의 콜론이 경로로 매핑됨 (`boi:public:A:B` → `data/boi/public/A/B.md`).

### 2.2 웹 런타임
- `boi_api/app/main.py` 단일 파일 FastAPI 모놀리스(~32k lines, ~250 라우트, 라우터 분리 없음).
- 마크다운 렌더러는 자체 구현이며 **모든 raw HTML을 이스케이프** → HTML 호스팅은 신규 서빙 경로 필요.
- 루트 예약 세그먼트: `/`, `health`, `inbox`, `ops`, `events`, `actions`, `sops`, `source`, `permissions`, `capabilities`, `event-types` + prefix `api/ static/ docs/ auth/ okf-media/ sop-runs/ workflows/ agents/` + FastAPI 기본 `openapi.json`, `redoc`, `docs`(Swagger).
- 재사용 가능 프리미티브: multipart 업로드(`/api/data-lake/artifacts/upload`), 소유권 기록(`owner_employee_id`/`uploaded_by_employee_id`), ACL(`access_policy.doc_access_policy`), 경로 탈출 방지 패턴(`/okf-media`), 이름 정규화(`registration_slug`), 캐시 무효화(`invalidate_doc_caches`), git 자동 커밋(`git_commit_for_path`).
- 리버스 프록시는 저장소 밖(배포 환경)의 몫. `BOI_EXTERNAL_URL`로 외부 도메인 인식. 단축주소 라우팅을 boi-api 안에 넣으면 로컬(`localhost:28000/{name}`)과 운영(`wiki.skhynix.com/{name}`)이 동일하게 동작 → "테스트에서도 실제로 가능" 요건 충족.

### 2.3 하네스
- 4중 구조가 이미 확립됨: repo `harness/*.md` 원본 ↔ `data/boi/public/harness/*.md` 서빙 사본(OKF frontmatter + `source_refs`로 원본 역참조) ↔ thin skill(`skills/boi-wiki-agent/SKILL.md`) ↔ 런타임 검증(`GET /api/harness/acceptance`: Observation/Context/Control/Action/State/Verification 6 버킷 라이브 체크).
- 문서가 구현을 핀(pin)하고 테스트가 문서를 핀함(`tests/test_seed_documents.py`가 MCP tool 수 124 등 하드코딩 검증) — 도구 추가 시 문서+테스트 동시 갱신 강제.
- MCP 124 tools. 쓰기 경계 7종은 `user_confirmed=true` 필수.
- **HTML 콘텐츠용 하네스 계약은 전무.**

### 2.4 진화 루프
- **있는 것**: event→action→BoI Writer 문서 생성→`enrich-from-dispatch` 결과 기록→`work_context_pack`(trace 이벤트/액션/BoI + similar cases + historical patterns + 내러티브)이 다음 담당자/에이전트에게 맥락 제공. promotion(HOTL + git auto-commit), Second Brain 정리(격리→삭제), work-pattern 후보 채굴.
- **없는 것(루프 엔지니어링 공백)**: ① 재사용/조회 텔레메트리(usage_count는 생성 시 1로 고정, 증가 없음) ② 스케줄러(요청 트리거 in-process 타이머뿐; `review_after`를 아무도 소비 안 함) ③ 공개 지식 신선도 감쇠/검색 반영 ④ 의미 기반 통합·중복 제거 ⑤ 패턴→자산(스킬/SOP) 자동 합성 ⑥ 답변/문서 품질 피드백 수집 ⑦ 후속 단계 결과의 SOP 역전파.

### 2.5 외부 리서치 핵심 (근거 링크는 §9)
- **하네스 표준**: AGENTS.md(루트 계약) + Agent Skills/SKILL.md(절차, 3단계 점진 공개)가 Linux Foundation 관할 크로스-벤더 표준으로 수렴. Claude/Codex/native agent가 같은 하네스를 쓰는 것이 현실적 표준 패턴.
- **메타 하네스**: (i) ratchet 원칙 — 하네스의 모든 규칙은 실제 실패 사례로 소급 가능해야 함, (ii) 하네스 acceptance = 골든 태스크 eval 회귀 테스트, (iii) 모델 세대 교체 시 각 하네스 요소가 여전히 load-bearing인지 재검증, (iv) 생성자/평가자 분리(자기평가 편향 회피). 반증 연구도 존재: 과적재된 컨텍스트 파일은 성공률을 낮추고 비용 +20% — 하네스는 얇게, eval로 검증.
- **단일 도메인 HTML 호스팅**: `Content-Security-Policy: sandbox allow-scripts` 응답 헤더 → opaque origin(쿠키/스토리지 접근 불가). `allow-same-origin`+`allow-scripts` 조합 절대 금지. viewer는 `<iframe sandbox="allow-scripts">`. GitHub Pages/CodePen/Claude Artifacts 전부 origin 격리로 수렴 — 전략적으로 별도 내부 호스트네임(`wiki-content.skhynix.com`) 확보가 최선의 이중 방어.
- **go-link 설계**: FCFS 선점 + 예약어 목록 + 이름 재활용 금지(tombstone) + 소유자/퇴사 회수 + 클릭 분석. 마찰 없는 셀프서비스가 문화 확산의 핵심.
- **HTML 메타데이터**: 별도 표준은 없고 `<script type="application/ld+json">`이 사실상의 "HTML용 frontmatter". BoI Profile 스키마를 그대로 JSON-LD로 직렬화하면 "하나의 스키마, 두 가지 직렬화"가 됨.

## 3. 설계 원칙

1. **정본은 지식 그래프, 표현은 자유** — 조직 지식 그래프의 정본은 계속 OKF Markdown. HTML은 1급 *표현/전달* 형식으로 수용하되, 모든 HTML은 자동 생성되는 OKF **지식 카드**(knowledge card)를 통해 그래프에 편입된다. HTML 자체도 내장 BoI Profile(JSON-LD)을 가져 단독으로 식별·검증 가능.
2. **하나의 하네스, 여러 소비자** — Claude/Codex 같은 외부 에이전트, Native BoI Agent, 웹 UI가 전부 같은 하네스 문서·같은 API/MCP 계약을 사용. 웹 사용자는 하네스를 모른 채 UI를 통해 하네스 준수 결과물을 얻는다(현행 구조 유지·확장).
3. **저장이 아니라 순환** — 모든 신규 기능은 이벤트를 발행하고, 그 이벤트가 지식자산화 액션(카드 생성, 인덱싱, 신선도 추적)으로 이어지게 설계한다.
4. **기존 패턴 준수** — 경로↔ACL 규칙, user_confirmed 쓰기 경계, preview→confirm→apply→auto-commit, 문서-구현-테스트 삼중 핀 구조를 HTML에도 동일 적용.

## 4. 아키텍처 설계

### 4.1 HTML 콘텐츠 모델 — "BoI HTML Profile + 지식 카드"

**저장 위치** (제안, §7 Q4): 스코프별 `html/` 폴더로 기존 ACL 경로 규칙 재사용.

```text
data/boi/public/html/{name}.html              # 전사 공유
data/boi/team/{team_id}/html/{name}.html      # 팀 공유
data/boi/private/{사번}/html/{name}.html      # 개인
data/boi/public/html/{name}.md                # 자동 생성 지식 카드(같은 이름, .md)
```

- `boi_id`: `boi:public:html:{name}` (기존 콜론→경로 매핑 그대로).
- MVP는 **단일 self-contained HTML 파일**만 허용(사내 문화와 일치, 사내망엔 외부 CDN이 어차피 없음). 크기 상한(예: 20MB). 다중 파일 번들은 후속.

**BoI HTML Profile**: HTML `<head>`에 단일 `<script type="application/ld+json" id="boi-profile">` 블록. 페이로드는 Markdown frontmatter와 **같은 BoI Profile 필드**(okf_version, boi_profile_version, type: `boi/html-document`, title, description, boi_id, visibility, classification, owner, acl_policy, status, timestamp, source_refs, review_after ...)를 schema.org `Report` 타입 + BoI 확장으로 직렬화.

- 에이전트/파이프라인 생성 HTML(Track B): 하네스가 처음부터 이 블록을 포함해 생성.
- 사용자 임의 업로드 HTML(Track A): 업로드 폼에서 제목/설명/공개범위만 받고 **서버가 head에 블록을 주입**(본문 무수정). 사용자는 메타데이터 개념을 몰라도 됨.

**지식 카드 (자산화의 핵심)**: 업로드/게시 성공 시 `html.share.published.v1` 이벤트 발행 → BoI Writer connector가 지식 카드 `.md` 자동 생성(제목·설명·소유자·단축주소·원본 링크·frontmatter `source_refs`→HTML+sha256). 이어서 Native Agent enrich 단계(비동기)가 본문 텍스트를 추출해 요약·태그·관련 SOP/사전 용어 링크를 카드에 채운다. **검색(`ontology_search`)·링크 그래프·신선도·promotion 루프에는 카드가 들어가고, 카드가 HTML을 대표한다.**

**okf.py 확장** (기존 lint 구조에 HTML 계열 추가):
- `lint_data_root`가 `*.html`도 순회: JSON-LD 블록 존재/파싱 → 기존 `REQUIRED_FIELDS`·enum·경로↔ACL 검증 재사용.
- 지식 카드 ↔ HTML 상호 참조 무결성(sha256 일치) 검증.
- HTML 전용 규칙: `<script src=`, `<link href=` 등 외부 참조 시 warning(사내망에서 깨짐), secret scan(`SECRET_VALUE_RE` 재사용), 크기 상한.
- 링크 그래프: HTML 자체의 `<a href>`는 그래프에 넣지 않음(카드가 대표) — 린트 복잡도 통제.

### 4.2 단축주소 서비스 (`wiki.skhynix.com/{name}`)

**boi-api 내부 구현** (프록시 무관 → 로컬 `localhost:28000/{name}`에서 동일 동작, 운영은 프록시가 그대로 포워딩).

- **Name Registry**: `data/registry/shortlinks.yaml` (git 관리, 콘텐츠와 함께 커밋). 레코드: `name, target_kind(html|doc|url), target(boi_id 또는 URL), owner_employee_id, created_at, updated_at, status(active|tombstone)`.
- **이름 규칙**: `^[a-z0-9][a-z0-9-]{1,63}$`. 업로드 시 파일명에서 `registration_slug()`로 기본값 생성, 사용자가 수정 가능, 실시간 중복 체크 API.
- **정책**: FCFS 선점. 소유자만 이름/대상 변경·재업로드 가능(관리자 break-glass 예외). 타인 이름과 중복 시 등록 거부 + 대안 제시(`-2` 등). 삭제 시 **tombstone**(이름 영구 재사용 금지, "이동/삭제됨" 안내 페이지) — 북마크 하이재킹 방지.
- **라우팅**: 루트 catch-all `GET /{name}`을 **가장 마지막에 등록** + 예약어 denylist를 코드 상수 + 테스트로 이중 방어(§2.2 목록 + 성장 예약분: `go, r, raw, html, s, link, login, logout, admin, search, mcp, files, share, new, me`). 등록 API가 예약어 선점 자체를 차단.
- **일반화**: 단축주소 대상은 HTML만이 아니라 임의 BoI 문서(`/docs/...`로 302)도 허용 — go-link 문화 전체를 흡수. 클릭 카운트는 runtime JSONL에 적재(§4.6 텔레메트리 루프의 입력).

### 4.3 보안 모델 (단일 도메인 전제)

| 경로 | 역할 | 응답 헤더/정책 |
|---|---|---|
| `GET /{name}` | **viewer shell** — 위키 크롬(제목·소유자·갱신일·조회수·지식카드/원본 링크·공유 버튼) + `<iframe sandbox="allow-scripts" src="/r/{name}">` | 일반 인증 페이지, ACL 체크 후 렌더 |
| `GET /r/{name}` | raw HTML inline 서빙 | `Content-Security-Policy: sandbox allow-scripts` + `X-Content-Type-Options: nosniff` + `Cross-Origin-Resource-Policy: same-site`, ACL 체크 |

- CSP `sandbox` 헤더로 문서가 **opaque origin**이 됨 → wiki.skhynix.com의 쿠키/localStorage 접근 불가, 인라인 JS 차트는 정상 동작. **`allow-same-origin`은 어떤 경우에도 추가 금지**(추가 시 XSS로 세션 탈취 가능 — 코드 주석+테스트로 고정).
- 업로드 시: secret scan, content-type 확인, 크기 제한. 렌더 무결성을 위해 sanitize(스크립트 제거)는 하지 않는 것을 기본안으로 함(§7 Q3).
- 운영 배포 시 프록시 권고: `/r/` prefix에서 쿠키 스트리핑(defense-in-depth).
- **전략 과제(별도 트랙)**: 사내 DNS에 `wiki-content.skhynix.com` 신청 → raw 서빙을 별도 origin으로 이전. CSP sandbox는 그 후에도 이중 방어로 유지.

### 4.4 업로드 UX / 소유권 / 중복 정책 (요청 요건 매핑)

| 요건 | 설계 |
|---|---|
| 파일 업로드 시 파일명 기본 | `report_2026-07.html` → 제안 이름 `report-2026-07` (slug 정규화), 폼에서 수정 가능 |
| 중복 체크 | 이름 입력 실시간 `GET /api/share/names/{name}/availability` (available / owned_by_me / taken) |
| 내가 올린 건 업데이트 가능 | 같은 이름 재업로드 = 소유자 검증 후 교체, git 커밋으로 전체 버전 이력 자동 확보(기존 auto-commit 재사용) |
| 남이 올린 건 업데이트 불가 | 409 + 대안 이름 제시 |
| 자연스러운 웹 렌더링 | §4.3 viewer + raw 경로. viewer에서 "전체 화면으로 보기" 제공 |

웹 UI: `/share` 업로드 페이지(드래그&드롭, 이름/설명/공개범위, 미리보기, 내 공유 목록 관리). 에이전트 경로: MCP `html_share_publish`(user_confirmed 필수).

### 4.5 하네스 확장 + 메타 하네스

**HTML 하네스 (기존 4중 구조 패턴 그대로)**
1. repo 원본 `harness/html-share-harness.md`: self-contained 원칙, BoI HTML Profile 계약, 이름/스코프 규칙, 게시 흐름(preview→confirm→publish), 지식 카드 계약, 금지 사항(외부 참조, secret).
2. 서빙 사본 `data/boi/public/harness/html-share-harness.md` (frontmatter + `source_refs`→repo 파일), `index.md`/`overview.md` 등록.
3. `skills/boi-wiki-agent/SKILL.md`에 HTML 저작·게시 절차 추가(thin 유지).
4. MCP tools 추가: `html_share_publish`, `html_share_preview`, `shortlink_check`, `shortlink_register`, `shortlink_list` (쓰기 2종은 user_confirmed 경계). tool 수 pin 테스트(`test_seed_documents.py`) 갱신.
5. `/api/harness/acceptance` Verification 버킷에 추가: HTML lint 통과, shortlink registry 무결성(예약어 침범 0, tombstone 재사용 0), `/r/` 응답 헤더 스모크.

**메타 하네스 (하네스 자체의 진화 체계)**
1. **버전·이력**: 각 하네스 문서 frontmatter에 `harness_version` 추가 + `harness/CHANGELOG.md`. 서빙 사본과 repo 원본의 버전 일치를 lint로 검증.
2. **Ratchet 로그**: 하네스 규칙 추가/변경 시 근거 실패 사례를 CHANGELOG에 필수 기록("모든 규칙은 실제로 잘못됐던 일로 소급 가능해야 한다"). 근거 없는 규칙 추가를 리뷰에서 거부하는 관례를 하네스 문서에 명문화.
3. **하네스 eval suite**: `tests/harness_evals/` — 골든 저작 태스크(예: "이 회의록 텍스트로 SOP 초안 패키지 생성", "이 HTML을 게시하고 지식 카드 확인") + 결과물의 기계 검증(필수 필드, 경계 준수, lint 통과). 하네스 문서 변경 시 회귀 실행. 생성자/평가자 분리: 결과물 검증은 저작 에이전트가 아닌 검증 스크립트/별도 평가 프롬프트가 수행.
4. **Load-bearing 재검증**: 모델 세대 교체 시(예: 새 Claude/Codex 도입) 하네스 항목별로 "제거해도 결과가 유지되는가"를 eval로 확인하고 불필요 규칙을 제거하는 절차를 `harness/README.md`에 명시. 하네스는 얇을수록 좋다(과적재는 성능·비용 역효과 — §9 반증 연구).
5. **acceptance의 자기 참조**: `harness_acceptance`에 meta 버킷 추가 — CHANGELOG 존재, 버전 일치, eval suite 최근 통과 기록.

### 4.6 루프 엔지니어링 — 진화하는 지식 자산

§2.4의 공백을 6개 루프로 메꾼다. 모두 기존 Event Broker/Action Gateway 패턴 위에 구현.

1. **Ingest 루프 (HTML→지식)**: `html.share.published.v1` → BoI Writer가 지식 카드 생성 → Native Agent enrich(요약·태그·SOP/용어 링크) → 카드가 검색/그래프에 편입. *암묵지(개인 보고서)가 올라오는 즉시 조직 지식 그래프에 연결되는 경로.*
2. **텔레메트리 루프**: 단축주소 클릭·문서 조회를 runtime JSONL로 적재(+`usage_count` 실제 증가). 검색 랭킹 보조 신호 + gardening 우선순위 입력.
3. **Gardening 루프 (sleep-time)**: 스케줄 이벤트 `wiki.gardening.requested.v1`(신규 — 외부 cron이나 경량 스케줄러가 주기 발행) → gardening 액션이 stale(`review_after` 경과)·orphan(역링크 0)·broken link·중복 후보(제목/내용 유사)를 검사 → 발견 항목을 remediation task로 Inbox에 발행 → 담당자 또는 에이전트가 처리 → 결과가 다시 BoI로. *현재 아무도 소비하지 않는 `review_after`가 처음으로 살아나는 지점.*
4. **Promotion 추천 루프**: 조회/재사용 상위 private·team 문서를 주기적으로 promotion 후보로 추천(Inbox 카드). HOTL 원칙 유지 — 자동 게시는 하지 않고 사람 확인 후 기존 promotion 경로 사용.
5. **패턴→자산 루프**: 기존 `work_pattern` 후보(candidate_only)를 스킬/SOP 초안 생성 제안으로 연결(draft 생성까지만, publish는 사람 확인).
6. **피드백 루프**: 문서/보고서/에이전트 답변에 "도움됨/수정 필요" + 한 줄 코멘트 수집 → 해당 문서의 BoI Profile 신호로 축적 → gardening·promotion 루프의 입력.

HTML 보고서도 카드·클릭 분석·`review_after`를 통해 동일 루프에 자동 편입된다.

## 5. 구현 로드맵

### Phase 1 — HTML 공유 MVP (즉시 체감 가치)
- [x] Name Registry(`data/registry/shortlinks.yaml`) + 로더/검증 + 예약어 상수·테스트
- [x] `POST /api/share/html` 업로드(멀티파트, slug 제안, 중복/소유권 정책, secret scan, git 커밋)
- [x] `GET /api/share/names/{name}/availability`, `GET /api/share/mine`, `DELETE`(tombstone)
- [x] `GET /r/{name}` raw 서빙(CSP sandbox allow-scripts + nosniff + CORP, ACL)
- [x] `GET /{name}` viewer shell(맨 마지막 등록, denylist 가드) + 404 시 검색/등록 제안
- [x] `/share` 업로드 웹 UI + 내 공유 관리
- [x] `invalidate_doc_caches` 연동, 제목/설명 검색 노출
- [x] `scripts/check_html_share.py` 스모크(업로드→단축주소→헤더→ACL→중복 정책→tombstone)

### Phase 2 — OKF/하네스 통합
- [x] BoI HTML Profile(JSON-LD) 주입/파싱 모듈 + `okf.py` HTML lint 확장
- [x] 지식 카드 자동 생성(업로드 시 동기 생성; 비동기 BoI Writer enrich는 Phase 3) + `html.share.published.v1` 이벤트/액션 카탈로그 등록
- [x] MCP 5 tools + tool pin 테스트 갱신
- [x] `harness/html-share-harness.md` + 서빙 사본 + index/overview/SKILL.md 갱신
- [x] `/api/harness/acceptance` HTML 체크 추가

### Phase 3 — 루프 엔지니어링
- [x] 클릭/조회 텔레메트리 + usage_count 실증가 (`boi_api/app/loops.py` TelemetryStore — runtime JSONL+카운터, frontmatter 무수정; memory recall이 usage_count에 실시간 합산)
- [x] gardening 스케줄 이벤트 + stale/orphan/broken/중복 검사 액션 + Inbox remediation 카드 (`wiki.gardening.requested.v1`/`wiki.remediation.requested.v1` + `wiki.gardening.run` 액션 + `POST /api/gardening/run`; 스케줄러는 외부 cron/이벤트 발행자, REST는 수동/로컬 트리거 겸용; 발견 항목은 `boi.materialize_event`가 Inbox 카드로 자산화)
- [x] promotion 추천 루프, 피드백 수집 UI/API (`GET /api/promotions/recommendations` HOTL 추천만; 도움됨/수정 필요 버튼 + `/api/docs/{boi_id}/feedback`·`/api/share/{name}/feedback`; needs_fix는 gardening feedback finding 입력)
- [x] 카드 enrich — 결정적 자동 분석(제목/목차/발췌/표·스크립트 수/사전 태그, LLM 없음) 업로드 동기 생성 + `POST /api/share/{name}/enrich` 재계산 + `share.html_card.enrich` 액션(이벤트 버스 비동기 재-enrich). LLM 요약 품질 훅은 후속.

### Phase 4 — 메타 하네스
- [x] `harness_version` + CHANGELOG + ratchet 관례 명문화 (`harness/manifest.yaml` SSOT + `boi_api/app/harness_meta.py` 검증)
- [x] `tests/harness_evals/` 골든 태스크 suite (생성자/평가자 분리: `grading.py`가 단일 평가자)
- [x] acceptance meta 버킷 + load-bearing 재검증 절차 문서화 (`harness/README.md`)

의존성: Phase 1은 독립 배포 가능. Phase 2는 1에 의존. 3, 4는 병행 가능.

## 6. 검증 계획
- 단위: registry 정책(FCFS/예약어/tombstone), CSP 헤더, JSON-LD 파싱/주입, okf lint HTML 규칙.
- 통합: `check_html_share.py` 스모크, 기존 `pytest tests -q`, `okf_lint.py --strict-*` 무회귀.
- 보안: sandbox iframe에서 `document.cookie` 접근 실패 확인 테스트, `allow-same-origin` 금지 가드 테스트.
- 하네스: acceptance 신규 체크 green, harness eval suite 통과.
- 실환경: 로컬 `localhost:28000/{name}` = 운영 `wiki.skhynix.com/{name}` 동일 라우팅(프록시는 포워딩만).

## 7. 확정된 결정 사항 (2026-07-17 사용자 확인)
- **Q1 단축주소 스킴 → 루트 `/{name}`**. 예약어 denylist 상수 + "신규 루트 추가 시 denylist 갱신 강제" 테스트로 충돌 방어. catch-all은 맨 마지막 등록.
- **Q2 HTML의 지위 → JSON-LD 내장 BoI HTML Profile + 자동 지식 카드**. HTML은 1급 표현 형식, 지식 그래프 정본은 자동 생성 OKF 카드(§4.1).
- **Q3 스크립트 정책 → 실행 허용 + 격리**. `Content-Security-Policy: sandbox allow-scripts`로 opaque origin 격리. sanitize 없음. `allow-same-origin` 금지를 테스트로 고정.
- **Q4 저장/스코프 → `data/boi/{public|team/{id}|private/{사번}}/html/` + 업로드 기본값 public**. 폼에서 team/private 선택 가능. 기존 경로↔ACL 규칙·git 자동 커밋 재사용.

## 8. 리스크
- 루트 catch-all과 미래 라우트 충돌 → 예약어 상수 + "신규 루트 추가 시 denylist 갱신" 테스트로 강제.
- 단일 도메인 XSS 잔여 위험 → CSP sandbox + nosniff + 쿠키 스트리핑, 중기적으로 별도 호스트네임 확보.
- main.py 비대화 → share/registry 모듈은 별도 파일(`boi_api/app/share.py` 등)로 작성, main.py에는 라우트 등록만.
- 대용량/저품질 HTML 유입 → 크기 상한 + gardening 루프의 정리 대상化.

## 9. 참고 자료 (리서치 출처)
- Anthropic: Effective harnesses for long-running agents / Harness design for long-running apps / Effective context engineering / Demystifying evals — anthropic.com/engineering
- AGENTS.md(agents.md, Linux Foundation AAIF), Agent Skills 스펙(agentskills.io/specification, github.com/anthropics/skills)
- Addy Osmani, Agent Harness Engineering(addyosmani.com/blog/agent-harness-engineering) — ratchet 원칙
- ETH Zurich, Evaluating AGENTS.md(arxiv.org/html/2602.11988v1) — 컨텍스트 과적재 반증
- Google: Securely hosting user data(web.dev/articles/securely-hosting-user-data), SafeContentFrame(bughunters.google.com)
- MDN CSP sandbox, Simon Willison iframe CSP escape tests(2026-04)
- go-links: trot.to, golinks.com/blog/go-links-deep-dive, yiou.me/blog/posts/google-go-link
- Letta sleep-time compute(docs.letta.com), Karpathy LLM-wiki gardening 패턴, Swimm code-coupled docs
- JSON-LD/schema.org 문서 메타데이터, ogp.me, dublincore.org

## 10. 개선 계획 v1.1 (Phase 1~4 완료 후 리뷰, 2026-07-18)

코드 범위 한정(코드 밖 전략 과제 제외). 각 항목은 ratchet 원칙에 따라 구현물 검증에서 확인된 실제 한계를 근거로 한다. 규모: S(반나절), M(1~2일), L(그 이상).

### P0 — 루프를 실제로 닫는 것 + 실사용 필수

1. **Remediation 생명주기** (M) — 근거: `loops.py::claim_new_findings`의 emitted.json은 영구 dedup이라, 한 번 발견된 문제가 고쳐진 뒤 재발해도 다시 발행되지 않는다(루프가 한 바퀴만 돎). 개선: gardening 실행 시 이번 스캔에 없는 fingerprint는 resolved 처리(원장에서 해제·이력 보존), 재발 시 재발행. 리포트에 open/resolved 추이 추가.
2. **피드백 표면화** (S) — 근거: "수정 필요" 코멘트가 텔레메트리 JSONL에만 쌓이고 어떤 API/UI로도 노출되지 않는다 — 수집만 하는 피드백은 루프가 아니다. 개선: 문서 소유자·`boi.promoter`에게 코멘트 목록 API(권한부), gardening 리포트의 feedback finding에 코멘트 포함, 소유자용 `/share` 목록에 피드백 배지.
3. **인코딩 감지·변환** (S) — 근거: 비-UTF-8 업로드는 `errors="replace"`로 깨진 채 저장된다. 사내 legacy HTML 보고서는 EUC-KR일 가능성이 높아 실사용 첫 주에 부딪힐 문제. 개선: charset meta/BOM 감지 → EUC-KR/CP949 등은 UTF-8로 변환 저장, 감지 실패 시에만 replace + 업로드 응답에 경고.
4. **Gardening 비동기 job화** (M) — 근거: `POST /api/gardening/run`이 요청 스레드에서 전체 코퍼스 lint+그래프 스캔을 동기 실행 — 문서 수천 개 규모에서 타임아웃. 개선: 기존 inbox background timer/queue 패턴 재사용(job 시작→`/api/gardening/report` polling), 동기 모드는 소규모/테스트용 플래그로 유지.
5. **`/r/` 헤더 보강** (S) — 근거: 현재 3종 헤더는 문서 자체의 origin 격리만 담당 — 외부 사이트가 `/r/{name}`을 iframe으로 끼워넣는 것과 referer로 단축주소가 새는 것은 막지 않는다. 개선: `frame-ancestors 'self'`(CSP에 병기)와 `Referrer-Policy: no-referrer` 추가. 코드 내에서 가능한 심층 방어의 마지막 조각.

### P1 — 제품 완성도 + 메타 하네스 성숙

6. **메타데이터만 수정** (M) — 근거: 제목/설명/공개범위만 바꾸려 해도 파일 재업로드가 필요. 개선: `PATCH /api/share/{name}` + UI(visibility 변경 시 기존 파일 이동+카드 재생성 로직 재사용, 프로필 재주입).
7. **소유권 이전·회수** (S) — 근거: go-link 설계 원칙(소유자 이전, 퇴사자 orphan 회수) 중 회수만 admin delete로 존재. 개선: 소유자→지명 이전 + admin 회수 API, 레지스트리에 이전 이력.
8. **조회수 의미 정리** (S) — 근거: viewer 방문 1회가 viewer+iframe raw로 2 클릭 집계되어 조회수가 2배로 보인다. 개선: viewer/raw 카운트 분리 저장, 노출은 viewer 기준.
9. **LLM enrich 훅 구현** (M) — 근거: 카드 자동 분석이 결정적 추출뿐(코드 주석에 future hook 명시됨). 개선: composer LLM 가용 시(`BOI_AGENT_COMPOSER_LLM_ENABLED`) 요약·태그 업그레이드, 실패 시 결정적 결과 유지(기존 Agent composer 실패 정책과 동일).
10. **WorkContextPack에 공유 HTML 연계** (M) — 근거: 카드는 검색에는 잡히지만 업무 맥락 팩에는 노출 경로가 없다 — "업무 맥락 제공" 비전과 직결. 개선: trace/SOP/사전 태그 매칭으로 관련 공유 카드를 `work_context_pack` evidence에 포함.
11. **Eval suite 실효화** (S) — 근거: acceptance `harness_eval_status`가 실배포에서 항상 `not_recorded` — 기록 주체가 없다. 개선: `scripts/run_harness_evals.sh`(BOI_HARNESS_EVAL_RECORD=1) + `check_local_full_readiness.py`에 편입.
12. **Ablation runner** (M) — 근거: load-bearing 재검증이 문서 절차뿐, 도구가 없다. 개선: 하네스 규칙 목록별 skip 플래그로 eval을 반복 실행해 "제거해도 통과하는 규칙" 후보를 보고하는 스크립트.

### P2 — 수요 확인 후 확장

13. **url-kind go-link 등록 개방** (M) — 내부 host allowlist(env) 정책과 함께 임의 내부 URL 단축주소 허용 — go-link 문화 완전 흡수.
14. **버전 이력 뷰** (M) — git log 기반 "이 공유의 이전 버전" 읽기 전용 열람(auto-commit 이력 재사용).
15. **다중 파일 번들** (L) — `{name}/` 폴더 + index.html (계획서 §4.1의 후속 항목).
16. **업로드 quota/rate limit** (S) — 사번당 공유 수·일일 업로드 상한 env.
17. **레지스트리 동시성** (S) — 멀티 워커 배포 대비 파일락, 또는 단일 워커 전제를 acceptance 체크로 명시.
18. **텔레메트리 보존 정책** (S) — 일자 JSONL 보존 N일 회전 + counters 스냅샷.
19. **패턴→자산 합성 루프** (L, 탐색적) — work_pattern candidate → SOP/스킬 draft 생성 제안 연결 (§4.6-5).
20. **LLM 골든 태스크 eval** (L, 옵트인) — 실제 에이전트로 저작 태스크를 수행시켜 grading하는 스위트(결정적 스위트와 분리, env-gated).

권장 순서: P0 전체(1~5)를 한 묶음으로 → P1은 6·8·11(S/M 소형)부터 → 9·10(비전 직결) → 12. P2는 사용 데이터(텔레메트리)가 쌓인 뒤 수요 기반으로 선별.
