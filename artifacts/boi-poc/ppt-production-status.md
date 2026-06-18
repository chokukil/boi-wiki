# BoI Wiki PoC PPT Production Status

Updated: 2026-06-19 02:05 KST

## Created Artifacts

- `artifacts/boi-poc/boi-wiki-poc-executive-brief.pptx`
- `artifacts/boi-poc/boi-wiki-poc-executive-brief-notes.md`
- `artifacts/boi-poc/evidence.json`
- `artifacts/boi-poc/evidence-summary.md`
- `artifacts/boi-poc/capture-manifest.json`
- `artifacts/boi-poc/capture-targets.json`
- `artifacts/boi-poc/capture-targets.md`
- `docs/POC_SCREENSHOT_MANIFEST.md`
- `scripts/insert_poc_screenshots.py`
- `scripts/check_poc_delivery_readiness.py`

Windows copy:

- `C:\Users\choku\Documents\boi-wiki-poc\boi-wiki-poc-executive-brief.pptx`
- `C:\Users\choku\Documents\boi-wiki-poc\evidence.json`
- `C:\Users\choku\Documents\boi-wiki-poc\evidence-summary.md`
- `C:\Users\choku\Documents\boi-wiki-poc\capture-targets.json`
- `C:\Users\choku\Documents\boi-wiki-poc\capture-targets.md`

## Verified

- The BoI Wiki PoC Docker stack is running.
- `boi-api` and `action-gateway` health endpoints return `ok`.
- Kafka topics exist: `boi.events`, `boi.audit`, `boi.dead-letter`.
- Demo workflow publishes `equipment.alarm.raised.v1` and produces downstream workflow/action records.
- Langflow smoke run uses `google/gemma-4-26b-a4b-qat` through the OpenAI-compatible endpoint and returns a Korean response.
- The generated 15-slide PPTX opens in Microsoft PowerPoint.
- The PowerPoint ChatGPT add-in pane opens in the generated deck.
- A polish request was entered and submitted to the add-in.
- Screenshot filenames and URLs are fixed in a manifest.
- Latest capture URLs are resolved in `capture-targets.md`, including the generated corrective action Private BoI and Langflow flow ID.
- A screenshot insertion script is ready to create the final screenshot-enriched PPTX after PNG capture files exist.
- A delivery readiness checker now combines E2E evidence, capture URL preflight, screenshot availability, artifact-tool PPT export, and final deck existence into one report.

## Latest SSO / Langflow E2E Evidence

Latest evidence package:

- `outputs/manual-20260619/e2e-evidence/evidence-ledger.md`
- `outputs/manual-20260619/e2e-evidence/summary.json`
- `outputs/manual-20260619/e2e-evidence/workflow-status.json`
- `outputs/manual-20260619/e2e-evidence/run_equipment_sop_poc.log`

Latest verified trace:

- Trace ID: `trace-609660cf137c4946aaa833c891f704b7`
- Workflow key: `equipment-anomaly`
- Events: `24`
- Actions: `21`
- Generated BoIs: `4`
- Manual handoffs: `5`
- Failed actions: `0`
- Langflow actions: `4 / 4` with status `langflow_invoked`
- Langflow Reference Flow ID: `7f1ce7c7-7b6f-49cf-bbf6-c990fed400f4`
- Langflow Equipment Stage Analysis Flow ID: `422fa3e4-d09b-4d51-b323-e652a13f2792`

SSO smoke command:

```bash
SERVICE_TOKEN=dev-service-token-change-me POC_SMOKE_TIMEOUT_SECONDS=180 python scripts/run_equipment_sop_poc.py
```

Latest PPT source package:

- `artifacts/boi-poc/presentation-source/`
- `outputs/manual-20260619/presentations/boi-e2e-evidence/profile-plan.txt`
- `outputs/manual-20260619/presentations/boi-e2e-evidence/source-notes.txt`
- `outputs/manual-20260619/presentations/boi-e2e-evidence/claim-spine.txt`
- `outputs/manual-20260619/presentations/boi-e2e-evidence/design-system.txt`
- `outputs/manual-20260619/presentations/boi-e2e-evidence/contact-sheet-plan.txt`
- `outputs/manual-20260619/presentations/boi-e2e-evidence/slides/`

The tracked source package under `artifacts/boi-poc/presentation-source/` is copied into the thread-local `outputs/.../presentations/boi-e2e-evidence` workspace by `scripts/build_boi_e2e_ppt.py` before export. The latest deck source uses artifact-tool slide modules and is ready for export once the Codex primary runtime exposes `@oai/artifact-tool` and the required screenshots exist.

## Delivery Readiness Check

Run the consolidated readiness gate with:

```bash
python scripts/check_poc_delivery_readiness.py --out outputs/manual-20260619/e2e-evidence/delivery-readiness.json
```

Current expected status is `ok=false`: E2E evidence and URL preflight pass, but Chrome-captured PNG files, artifact-tool PPTX export, and the final screenshot deck are still missing.

Screenshot readiness is stricter than file existence. `insert_poc_screenshots.py --check` validates that each required file is a PNG and at least `800x600`, so placeholder, corrupt, or tiny images cannot accidentally satisfy the final deck gate.

The delivery readiness gate treats the artifact-tool export as the canonical final PPTX:

```text
outputs/manual-20260619/presentations/boi-e2e-evidence/output/boi-wiki-e2e-evidence-brief.pptx
```

The older screenshot insertion helper remains useful for the legacy executive deck, but final delivery should be evaluated against the artifact-tool output.

## Still Pending

- Actual Chrome screenshots of localhost PoC screens are not inserted yet because Chrome automation blocks `http://localhost:8000` by enterprise policy. This was rechecked through the Chrome extension flow on 2026-06-19 and still fails before navigation.
- The add-in stayed in `Loading` after the polish request; completion or deck mutation has not been verified.
- Final PPT completion requires actual screenshots to replace the slide 11 placeholders and a final PowerPoint save/export check.
- Latest artifact-tool PPTX export is blocked because `/home/chokukil/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/@oai/artifact-tool` is missing `package.json` in this Codex thread.

## Finalization Command After Artifact Runtime Is Restored

```bash
python scripts/build_boi_e2e_ppt.py
```

The script first validates required screenshot evidence with `scripts/insert_poc_screenshots.py --check`, then runs the artifact-tool runtime preflight, builds the 8-slide deck, renders previews, and writes a contact sheet. The delivery readiness checker runs the artifact-tool probe with `--skip-screenshot-check` so screenshot readiness and artifact runtime readiness remain visible as separate blockers.

## Finalization Command After Screenshots Exist

Save the required PNG files under `captures/boi-poc/`, then run:

```bash
python scripts/insert_poc_screenshots.py
```

Expected final deck:

```text
artifacts/boi-poc/boi-wiki-poc-executive-brief-with-screenshots.pptx
```

## Required Screenshots When Chrome Access Is Available

1. BoI Wiki home
2. SOP library
3. Event type catalog
4. Event stream
5. Action catalog/logs
6. Generated Private BoI document
7. Langflow BoI Reference Flow
8. Kafka UI topics/messages
