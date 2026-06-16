# BoI Wiki PoC Capture Targets

- Capture dir: `captures/boi-poc`
- Final deck output: `artifacts/boi-poc/boi-wiki-poc-executive-brief-with-screenshots.pptx`
- Evidence collected at: `2026-06-16T16:29:24+00:00`
- Git commit: `3932232`

| File | URL | Purpose |
|---|---|---|
| `01-boi-wiki-home.png` | `http://localhost:8000/` | 목록, 필터, Event log가 보이는 첫 화면 |
| `02-sop-library.png` | `http://localhost:8000/sops` | 설비 이상 SOP와 Agent Harness SOP |
| `03-event-type-catalog.png` | `http://localhost:8000/event-types` | 업무 이벤트 정의와 추천 Action |
| `04-event-stream.png` | `http://localhost:8000/events` | Alarm에서 Corrective Action까지 이어지는 이벤트 체인 |
| `05-action-catalog-logs.png` | `http://localhost:8000/actions` | materialized, dry_run, approval_required Action 로그 |
| `06-private-boi-corrective-action.png` | `http://localhost:8000/docs/private/100001/boi-private-100001-20260617012924-08c0f9.md` | 실제 생성된 corrective_action.requested.v1 Private BoI |
| `07-langflow-boi-reference-flow.png` | `http://localhost:7860/flow/15b0199d-583a-4b2e-b692-3ec1744a7c75` | Gemma OpenAI-compatible Reference Flow |
| `08-kafka-ui-topics.png` | `http://localhost:8081/` | boi.events, boi.audit, boi.dead-letter 토픽 |

After saving all PNG files, run:

```bash
python scripts/insert_poc_screenshots.py
```
