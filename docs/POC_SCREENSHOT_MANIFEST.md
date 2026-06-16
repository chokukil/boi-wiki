# BoI Wiki PoC Screenshot Manifest

Chrome automation currently blocks direct access to `http://localhost:8000` by enterprise policy. Do not bypass that policy. When localhost access is allowed, capture the following screens and save them under `captures/boi-poc/` with the exact filenames below.

| File | URL | PPT Purpose |
|---|---|---|
| `01-boi-wiki-home.png` | `http://localhost:8000/` | 목록, 필터, Event log가 보이는 첫 화면 |
| `02-sop-library.png` | `http://localhost:8000/sops` | 설비 이상 SOP와 Agent Harness SOP |
| `03-event-type-catalog.png` | `http://localhost:8000/event-types` | 업무 이벤트 정의와 추천 Action |
| `04-event-stream.png` | `http://localhost:8000/events` | Alarm에서 Corrective Action까지 이어지는 이벤트 체인 |
| `05-action-catalog-logs.png` | `http://localhost:8000/actions` | materialized, dry_run, approval_required Action 로그 |
| `06-private-boi-corrective-action.png` | latest `/docs/private/100001/boi-private-*.md` corrective action document | 실제 생성된 `corrective_action.requested.v1` Private BoI |
| `07-langflow-boi-reference-flow.png` | latest Langflow BoI Reference Flow | Gemma OpenAI-compatible Reference Flow |
| `08-kafka-ui-topics.png` | `http://localhost:8081/` | `boi.events`, `boi.audit`, `boi.dead-letter` 토픽 |

After the PNG files exist, run:

```bash
python scripts/insert_poc_screenshots.py
```

Expected output:

```text
artifacts/boi-poc/boi-wiki-poc-executive-brief-with-screenshots.pptx
```

The insertion script fails fast if any required screenshot is missing. Use `--allow-missing` only for a working draft, not for the final executive package.

