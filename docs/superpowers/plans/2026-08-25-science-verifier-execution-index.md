# Science Verifier 실행 순서

정본 설계는 `docs/superpowers/specs/2026-08-25-science-verifier-design.md`다. 아래 다섯 계획은 순서대로 실행한다.

> **2026-08-25 최종 방향 보정:** 이 인덱스의 과거 구현 계획은 Qwen 실가용성, 모델명·context 크기, 튜닝 또는 성공 응답을 완료·activation 조건으로 삼았던 부분을 **수정한다**. Qwen은 선택적·실험적 Claim 후보 해석기일 뿐이며, 결정론적 별칭 탐지와 사용자/외부 Agent의 untrusted 후보 제출만으로 검증 경로가 동작해야 한다. 이 보정은 과거 단계가 실행되었다는 기록이 아니다.

1. `2026-08-25-science-verifier-foundation.md`
   - Packet, `sci-profile`, Catalog, 단위·Rule 결정 엔진을 만든다.
2. `2026-08-25-science-verifier-knowledge.md`
   - Source/Evidence/Ontology Binding/Knowledge/Rule/Pack과 공개 회귀 사례를 구축한다.
   - 결과는 `release_candidate`이며 `G0..G4`만 preflight한다. 아직 활성화하지 않는다.
3. `2026-08-25-science-verifier-application.md`
   - 권한, LLM 해석, REST, 보고서, 문서 중심 Web UX를 만든다.
4. `2026-08-25-science-verifier-agent-integration.md`
   - MCP, Skill, Harness를 만든다.
   - Rule 동결 뒤 독립 holdout을 만들고 gate를 분리해 기록한다. 자동 Candidate qualification은 `G0..G4`까지 통과할 수 있지만, 독립 sealed holdout `G5`, 활성 Release의 stored-report parity `G6`, 사람 Science Admin의 원문 검토·activation audit `G7`은 완료 전까지 `PENDING`이다.
   - 실제 화면 캡처와 Web/REST/MCP/Markdown/PDF 계약을 검증한다. Qwen은 비활성/실패 API 경계도 브라우저에서 확인하되, live Qwen 응답은 요구하지 않는다.
5. `2026-08-25-science-verifier-evidence-deck.md`
   - imagegen 인포그래픽, 실제 UI, 실제 최종 보고서로 표지 없는 16:9 PPT 3장을 만들고 PNG로 시각 검수한다.

## 구현 증거와 완료 경계

- 구현 검증 보고서의 정본은 `artifacts/science-verifier/qualification-report.md`와 같은 report digest에 결속된 PDF다. `FINAL / VERIFIED` 표기는 이 구현 증거 묶음의 완결성만 뜻하며, 과학적 진실·안전·공정 승인·Release activation을 뜻하지 않는다.
- 이 묶음은 현재 Git revision에 결속된 tracked pytest suite identity 계약(각 suite의 수량과 testcase identity digest, 최소 한 건의 실제 실행), 정확히 21개의 브라우저 check와 각 캡처 hash, Candidate qualification, exact-commit 독립 리뷰(Critical·Important 0건)를 함께 검증해야 한다.
- 발표 자료 정본은 `artifacts/science-verifier/deck/science-verifier-evidence.pptx`다. Deck은 exact `FINAL` verification manifest, UI capture digest, 검증된 PDF render, tracked clean source를 모두 읽을 수 있을 때만 최종본으로 만들 수 있다. 빌드 scorecard의 사람 육안 검수는 실제 검토 전까지 `PENDING`으로 남긴다.
- Release는 `release_candidate`/inactive로 유지한다. `G0..G4` 자동 Candidate qualification 통과와 `G5..G7`의 `PENDING`을 한 문장으로 상쇄하거나 activation으로 표현하지 않는다.
- 계획별 구현·검토 커밋과 최종 whole-branch review가 모두 끝난 뒤 feature branch만 push한다. branch는 `codex/science-verifier`이며 원격 SHA 일치를 확인한다.
- `main` merge, PR merge, merge commit은 수행하지 않는다. 사용자가 검토 후 merge한다.
