# BoI Wiki PoC Screenshot Manifest

Chrome automation currently blocks direct access to `http://localhost:8000` by enterprise policy. Do not bypass that policy. When localhost access is allowed, capture the following screens and save them under `captures/boi-poc/` with the exact filenames below.

| File | URL | PPT Purpose |
|---|---|---|
| `01-boi-wiki-home.png` | `http://localhost:8000/?employee_id=100001` | 목록, 필터, Event log가 보이는 첫 화면 |
| `02-sop-library.png` | `http://localhost:8000/?employee_id=100001&folder=public%2Fsop` | OKF public/sop 폴더와 설비 이상 SOP |
| `03-event-type-catalog.png` | `http://localhost:8000/event-types/equipment.alarm.raised.v1?employee_id=100001` | 설비 Alarm 이벤트 정의, SOP, 추천 Action |
| `04-event-stream.png` | `http://localhost:8000/events?employee_id=100001&trace_id=trace-609660cf137c4946aaa833c891f704b7` | 최신 SSO E2E trace의 이벤트 체인 |
| `05-action-catalog-logs.png` | `http://localhost:8000/workflows/equipment-anomaly/status?employee_id=100001&trace_id=trace-609660cf137c4946aaa833c891f704b7` | Action, Langflow, Manual Handoff, Generated BoI 상태 |
| `06-private-boi-corrective-action.png` | `http://localhost:8000/docs/boi:private:100001:20260619014436:7ff90d?employee_id=100001` | 실제 생성된 `corrective_action.requested.v1` Private BoI |
| `07-langflow-boi-reference-flow.png` | `http://localhost:7860/flow/422fa3e4-d09b-4d51-b323-e652a13f2792` | SOP stage analysis에 실제 호출된 Langflow workflow |
| `08-kafka-ui-topics.png` | `http://localhost:8081/` | `boi.events`, `boi.audit`, `boi.dead-letter` 토픽 |

After the PNG files exist, run:

```bash
python scripts/insert_poc_screenshots.py --check
python scripts/build_boi_e2e_ppt.py
python scripts/check_poc_delivery_readiness.py --out outputs/manual-20260619/e2e-evidence/delivery-readiness.json
```

Artifact-tool final deck:

```text
outputs/manual-20260619/presentations/boi-e2e-evidence/output/boi-wiki-e2e-evidence-brief.pptx
```

Legacy screenshot insertion output:

```text
artifacts/boi-poc/boi-wiki-poc-executive-brief-with-screenshots.pptx
```

The insertion script fails fast if any required screenshot is missing. Use `--allow-missing` only for a working draft, not for the final executive package.
