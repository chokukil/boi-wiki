# BoI Harness CHANGELOG

## Ratchet 원칙

모든 하네스 규칙 추가/강화는 **실제 실패 사례로 소급 가능해야 한다**.

- 항목마다 "근거(evidence)"를 기록한다: 어떤 실제 실패·사고·위험 때문에 이 규칙이 생겼는가.
- 근거 없는 규칙 추가는 리뷰에서 거부한다. "있으면 좋을 것 같아서"는 근거가 아니다.
- 버전의 SSOT는 `harness/manifest.yaml`이다. 하네스 문서를 개정하면 manifest의 version을 bump하고,
  이 파일에 근거와 함께 항목을 추가한다 (최신 항목이 위로 오는 역순 정렬).
- 규칙 제거도 기록 대상이다: load-bearing 재검증(`harness/README.md`)에서 더 이상 유효하지 않다고
  확인된 규칙은 제거하고, 제거 근거(eval 결과)를 여기 남긴다.

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
