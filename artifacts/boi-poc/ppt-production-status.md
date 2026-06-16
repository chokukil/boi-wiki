# BoI Wiki PoC PPT Production Status

Updated: 2026-06-17 01:29 KST

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

## Still Pending

- Actual Chrome screenshots of localhost PoC screens are not inserted yet because Chrome automation blocks `http://localhost:8000` by enterprise policy.
- The add-in stayed in `Loading` after the polish request; completion or deck mutation has not been verified.
- Final PPT completion requires actual screenshots to replace the slide 11 placeholders and a final PowerPoint save/export check.

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
