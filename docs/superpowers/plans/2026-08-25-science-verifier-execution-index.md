# Science Verifier 실행 순서

정본 설계는 `docs/superpowers/specs/2026-08-25-science-verifier-design.md`다. 아래 다섯 계획은 순서대로 실행한다.

1. `2026-08-25-science-verifier-foundation.md`
   - Packet, `sci-profile`, Catalog, 단위·Rule 결정 엔진을 만든다.
2. `2026-08-25-science-verifier-knowledge.md`
   - Source/Evidence/Ontology Binding/Knowledge/Rule/Pack과 공개 회귀 사례를 구축한다.
   - 결과는 `release_candidate`이며 `G0..G4`만 preflight한다. 아직 활성화하지 않는다.
3. `2026-08-25-science-verifier-application.md`
   - 권한, LLM 해석, REST, 보고서, 문서 중심 Web UX를 만든다.
4. `2026-08-25-science-verifier-agent-integration.md`
   - MCP, Skill, Harness를 만든다.
   - Rule 동결 뒤 독립 holdout을 만들고 `G0..G7`을 통과한 다음 Admin으로 Release를 활성화한다.
   - 실제 `qwen/qwen3.8-27b` 해석, Web/REST/MCP/Markdown/PDF parity, 실제 화면 캡처, 최종 검증 보고서를 완료한다.
5. `2026-08-25-science-verifier-evidence-deck.md`
   - imagegen 인포그래픽, 실제 UI, 실제 최종 보고서로 표지 없는 16:9 PPT 3장을 만들고 PNG로 시각 검수한다.

## 완료 경계

- 최종 검증 보고서 정본: `artifacts/science-verifier/qualification-report.md`와 같은 digest의 PDF
- 발표 자료 정본: `artifacts/science-verifier/deck/science-verifier-evidence.pptx`
- 계획별 구현·검토 커밋과 최종 whole-branch review가 모두 끝난 뒤 feature branch만 push한다.
- branch는 `codex/science-verifier`이며 원격 SHA 일치를 확인한다.
- `main` merge, PR merge, merge commit은 수행하지 않는다. 사용자가 검토 후 merge한다.

