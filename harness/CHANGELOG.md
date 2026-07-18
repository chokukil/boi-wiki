# BoI Harness CHANGELOG

## Ratchet 원칙

모든 하네스 규칙 추가/강화는 **실제 실패 사례로 소급 가능해야 한다**.

- 항목마다 "근거(evidence)"를 기록한다: 어떤 실제 실패·사고·위험 때문에 이 규칙이 생겼는가.
- 근거 없는 규칙 추가는 리뷰에서 거부한다. "있으면 좋을 것 같아서"는 근거가 아니다.
- 버전의 SSOT는 `harness/manifest.yaml`이다. 하네스 문서를 개정하면 manifest의 version을 bump하고,
  이 파일에 근거와 함께 항목을 추가한다 (최신 항목이 위로 오는 역순 정렬).
- 규칙 제거도 기록 대상이다: load-bearing 재검증(`harness/README.md`)에서 더 이상 유효하지 않다고
  확인된 규칙은 제거하고, 제거 근거(eval 결과)를 여기 남긴다.

## 2026-07-18

### `overview` 0.4.0 — LLM 골든 태스크 eval(옵트인) 절차 등재

- 변경: `harness/README.md`(및 서빙 사본)에 "LLM 골든 태스크 eval (옵트인)" 절을 추가해 `tests/harness_evals_llm/`의 존재·실행 조건(`BOI_HARNESS_LLM_EVALS=1` + composer 설정)·채점 원칙(생성자/평가자 분리)을 명문화한다.
- 근거(evidence): 결정적 golden task suite(`tests/harness_evals/`)는 LLM을 호출하지 않아 "실제 에이전트가 저작 태스크를 수행했을 때"의 품질(한국어 출력, 길이, 태그 수, 비밀 값 등)을 채점하는 경로가 없었다(계획서 §10 P2-20). 네트워크/LLM 가용성 의존 때문에 결정적 suite에 섞으면 회귀 게이트가 불안정해지므로 별도 디렉터리 + 옵트인으로 분리했다.

### `html-share-harness` 1.3.0 — url go-link 개방 + 버전 이력 + 다중 파일 번들 + quota + MCP parity

- 변경: (1) `POST /api/share/links`가 `target_kind: "url"`(허용 내부 호스트, `BOI_SHARE_URL_ALLOWED_HOSTS`)을 받아 임의 내부 URL도 go-link로 등록할 수 있다(MCP `shortlink_register`도 동일 스키마로 확장 — 신규 tool 없음). (2) `GET /api/share/{name}/history`(git log 기반 이전 버전 목록)와 `GET /api/share/{name}/history/{commit}`(과거 버전 raw HTML, `/r/{name}`과 동일 보안 헤더)을 추가하고 뷰어에 "이력" 링크를 노출한다. (3) 업로드가 `assets`(multipart 반복 필드)를 받아 `{name}/index.html` + 평탄화된 자산 파일로 이루어진 다중 파일 번들을 지원한다(자산당 5MB·최대 20개, 확장자 allowlist, `/r/{name}/{asset_path:path}` 서빙, okf lint의 사이드카 카드 탐색과 자산 확장자 검증이 번들을 인식). (4) 사번당 활성 공유 상한(`BOI_SHARE_MAX_PER_USER`, 기본 200)과 일일 업로드 상한(`BOI_SHARE_MAX_UPLOADS_PER_DAY`, 기본 50)을 추가한다. (5) MCP `html_share_update`(PATCH 프록시)/`html_share_transfer`(transfer 프록시)를 추가해 웹 API와 MCP 도구 표면을 동등하게 맞춘다(tool 수 136→138).
- 근거(evidence): go-link 문화(trot.to류 셀프서비스 단축주소)를 BoI 문서/HTML뿐 아니라 임의 내부 URL까지 완전히 흡수해야 사내 URL 단축 수요를 대체할 수 있었다. 대용량 대시보드/보고서는 자산(이미지·CSS·차트 라이브러리)을 분리해야 하는데 단일 HTML 파일 제약이 이런 수요를 막고 있었다. 재업로드가 옛 버전을 덮어써 "직전 버전이 뭐였는지" 확인할 방법이 없었다(auto-commit 이력은 이미 있는데 열람 경로가 없었다). 업로드 quota/rate limit이 없어 한 사용자가 대량 업로드로 레지스트리·저장소를 소진할 수 있었다. PATCH/transfer 웹 API가 이미 있는데 MCP에는 대응 tool이 없어 Agent가 같은 작업을 하지 못했다(§10 P2-13/14/15/16 + MCP parity).

### `html-share-harness` 1.2.0 — PATCH(메타데이터 수정) + 소유권 이전 계약 추가

- 변경: `PATCH /api/share/{name}`(제목/설명/공개범위 수정, 프로필+카드 재생성, visibility/team 변경 시 파일 이동)과 `POST /api/share/{name}/transfer`(소유권 지명 이전 또는 admin 회수, `transfers` 이력 append, private 스코프 파일의 소유자 폴더 재배치)를 하네스 계약에 추가한다.
- 근거(evidence): 제목/설명/공개범위만 바꾸려 해도 파일 재업로드가 필요했다(§10 P1-6). go-link 설계 원칙(소유자 이전, 퇴사자 orphan 회수) 중 회수만 admin delete로 존재했고 지명 이전·회수 API 자체가 없어 퇴사자 공유를 넘겨받을 경로가 없었다(§10 P1-7).

### `overview` 0.3.0 — Load-bearing 재검증 도구화 (eval wrapper + ablation runner)

- 변경: `harness/README.md`(및 서빙 사본)의 "Load-bearing 재검증" 절에 `scripts/run_harness_evals.sh`(BOI_HARNESS_EVAL_RECORD=1 wrapper)와 `scripts/run_harness_ablation.py`(harness/ablation-flags.yaml 기반 ablation 러너) 사용법을 추가한다.
- 근거(evidence): acceptance의 `harness_eval_status`가 실배포에서 항상 `not_recorded`였다 — 기록 주체(BOI_HARNESS_EVAL_RECORD=1로 실행해주는 도구)가 없었기 때문이다. load-bearing 재검증도 절차만 문서에 있었고 "제거해도 통과하는 규칙"을 찾아주는 도구가 없어 재검증이 실제로 실행되지 않았다(계획서 §10 P1-11/P1-12).

### `html-share-harness` 1.1.0 — `/r/` 헤더 보강 (frame-ancestors + Referrer-Policy)

- 변경: `/r/{name}` 응답 CSP에 `frame-ancestors 'self'`를 병기하고 `Referrer-Policy: no-referrer`를 추가한다. 기존 `sandbox allow-scripts` + `X-Content-Type-Options: nosniff` + `Cross-Origin-Resource-Policy: same-site` 3종 헤더는 그대로 유지한다.
- 근거(evidence): 외부 사이트가 `/r/{name}`을 iframe으로 끼워넣는 것과 referer를 통한 단축주소 유출은 기존 3종 헤더가 막지 못했다. `frame-ancestors 'self'`는 타 origin의 프레이밍을 차단하고, `Referrer-Policy: no-referrer`는 사용자가 공유 HTML 안의 링크를 클릭했을 때 `Referer` 헤더로 단축주소 이름이 외부에 노출되는 경로를 막는다 (계획서 §10 P0-5, 코드 내에서 가능한 심층 방어의 마지막 조각).

## 2026-07-17

### `overview` 0.2.0 — 메타 하네스 체계 도입

- 변경: `harness/README.md`와 서빙 사본 overview에 "하네스 버전과 CHANGELOG", "Load-bearing 재검증" 절 추가.
  `harness/manifest.yaml`(버전 SSOT), 이 CHANGELOG, `tests/harness_evals/` eval suite, acceptance `Meta` 버킷을 등재.
- 근거(evidence): 메타 하네스 체계 도입 — 하네스 문서가 버전·근거 기록 없이 늘어나면서
  어떤 규칙이 어떤 실패에서 왔는지, 여전히 load-bearing인지 추적할 수 없었다 (계획서 §4.5 Phase 4).

### `html-share-harness` 1.0.0 — HTML 공유 하네스 신규 등재

- 변경: self-contained HTML 공유/단축주소 저작 계약 신규 등재 (Phase 1~2 구현과 동시).
- 근거(evidence):
  - HTML 공유/단축주소 기능 도입(Phase 1~2)으로 새 저작·게시 경계가 생겼다.
  - 업로드 HTML의 세션 탈취 위험: `allow-same-origin`이 `allow-scripts`와 결합되면 업로드된 HTML이
    위키 쿠키/세션에 접근할 수 있다 → `allow-same-origin` 금지 규칙 (CSP `sandbox allow-scripts` 고정).
  - 사내망에는 외부 CDN이 없어 외부 참조가 열람 화면에서 깨진다 → 외부 `<script src>`/`<link href>`
    http(s) 참조 warning 규칙.

### 전체 기존 하네스 0.1.0 baseline 등재

- 근거(evidence): 메타 하네스 도입 시점의 초기 버전 고정. 기존 문서들은 버전 없이 운영되어
  이후 개정을 ratchet으로 추적할 기준선이 없었다. 아래 문서를 일괄 0.1.0으로 등재한다.
  - `harness-responsibility-matrix` 0.1.0
  - `web-draft-editing-guide` 0.1.0
  - `sop-authoring-harness` 0.1.0
  - `action-authoring-harness` 0.1.0
  - `agent-api-mcp-search-harness` 0.1.0
  - `data-lake-query-harness` 0.1.0
  - `data-lake-artifact-harness` 0.1.0
  - `dictionary-authoring-harness` 0.1.0
  - `local-private-agent-harness` 0.1.0
  - `inbox-review-report-harness` 0.1.0
  - `simulator-dry-run-harness` 0.1.0
