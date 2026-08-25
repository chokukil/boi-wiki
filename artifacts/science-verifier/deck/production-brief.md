# Science Verifier Evidence Deck 제작 브리프

- 대상: 사내 Science Verifier Pilot 검토자와 Science Admin
- 목적: 구현된 신뢰 경계와 실제 문서 검토 경험을 보여주되, 지식 Release가 아직 비활성임을 분명히 전달
- 분량: 정확히 3장, 3~5분
- 한 줄 이야기: AI는 해석 후보만 내고, 판정은 사람이 승인한 Release의 결정론적 Rule·조건·Evidence가 수행한다.

## 슬라이드

1. 운영 목표 구조 — AI와 과학적 판정 권한의 분리. 기존 생성 infographic을 사용하되 `현재 Release: 비활성 후보`를 편집 가능한 배지로 명시한다.
2. 실제 문서 검토 — 실행 중인 `/science-verifier` 캡처와 브라우저 21/21, Wiki 로컬 수정 계보 보존, Qwen 실패 격리, red 0건을 함께 보여준다.
3. 검증 결과와 완료 경계 — 최종 PDF 첫 페이지 캡처와 G0–G4 PASS / G5–G7 PENDING을 함께 보여준다.

## 편집 가능 요소

슬라이드 제목, 상태 배지, 수치, Gate, 설명, source note, 페이지 번호는 PowerPoint text/shape로 유지한다. UI·보고서·architecture infographic만 raster evidence다.

## 검수 기준

- 정확히 3장, 표지 단독 슬라이드 없음
- 비활성 Release를 active 또는 운영 검증 완료로 표현하지 않음
- UI와 보고서 캡처는 실제 산출물이며 종횡비를 왜곡하지 않음
- G5·G6·G7 PENDING이 가려지지 않음
- 슬라이드별 PNG와 whole-deck preview 생성
- 겹침·잘림·과도한 작은 글자·허위 source note 없음
