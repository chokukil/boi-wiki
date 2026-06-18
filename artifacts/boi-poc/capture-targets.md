# BoI Wiki PoC Capture Targets

- Capture dir: `captures/boi-poc`
- Final deck output: `artifacts/boi-poc/boi-wiki-poc-executive-brief-with-screenshots.pptx`
- Evidence collected at: `2026-06-17T16:24:13+00:00`
- Git commit: `3dd82b8`

| File | URL | Purpose |
|---|---|---|
| `01-boi-wiki-home.png` | `http://localhost:8000/` | 목록, 필터, Event log가 보이는 첫 화면 |
| `02-sop-library.png` | `http://localhost:8000/sops` | 설비 이상 SOP와 Agent Harness SOP |
| `03-event-type-catalog.png` | `http://localhost:8000/event-types` | 업무 이벤트 정의와 추천 Action |
| `04-event-stream.png` | `http://localhost:8000/events` | Alarm에서 Corrective Action까지 이어지는 이벤트 체인 |
| `05-action-catalog-logs.png` | `http://localhost:8000/actions` | materialized, dry_run, approval_required Action 로그 |
| `06-private-boi-corrective-action.png` | `http://localhost:8000/docs/private/100001/boi-private-100001-20260618012251-15654c.md` | 실제 생성된 corrective_action.requested.v1 Private BoI |
| `07-langflow-boi-reference-flow.png` | `http://localhost:7860/flow/3aba3309-89a8-4171-a153-00db6b16dcba` | Gemma OpenAI-compatible Reference Flow |
| `08-kafka-ui-topics.png` | `http://localhost:8081/` | boi.events, boi.audit, boi.dead-letter 토픽 |

After saving all PNG files, run:

```bash
python scripts/insert_poc_screenshots.py
```
