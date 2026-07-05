---
title: Data Lake Artifact Harness
type: boi/harness
status: reviewed
---

# Data Lake Artifact Harness

Use this harness when a workflow run, report, sandbox, Agent, Inbox decision, manual action, or review surface needs file evidence.

## Boundary

MinIO is optional and belongs to the `local-full-datalake` profile. BoI Wiki core remains DB-less OKF Markdown/JSONL. Clients must not connect to MinIO directly; they use BoI API/MCP artifact tools.

## Contract

- Raw files are stored as Data Lake artifacts.
- BoI Markdown stores stable download URL, profile, sample, chart/preview, checksum, validation metadata, and ACL state.
- Large raw content must not be pasted into LLM prompts or BoI bodies.
- Artifact visibility defaults to private. Team/Public sharing requires explicit confirmation.
- Disabled Data Lake must return a clear disabled contract and must not block SOP/Inbox/core flows.
- Human-uploaded files use the same contract as Agent/Sandbox outputs. Attachments must preserve `uploaded_by_employee_id`, `attached_from_surface`, `target_type`, `target_id`, `attachment_role`, `human_note`, and `validation_state`.
- SOP Builder is not a raw file upload surface. It defines evidence requirements and attachment locations; actual raw files are attached later from SOP Run stages, Inbox decisions, Manual Action completion, Report BoI review, Agent conversations, or sandbox/report workflows.
- Users do not need a separate "use as evidence" checkbox. The current workflow stage, Inbox task, report, action result, conversation, or work context determines the default target; users can delete or retarget the attachment.

## Flow

1. Upload: `POST /api/data-lake/artifacts/upload` or MCP `data_lake_artifact_upload`.
2. Inspect: `GET /api/data-lake/artifacts/{artifact_id}` or MCP `data_lake_artifact_get`.
3. Profile: `POST /api/data-lake/artifacts/{artifact_id}/profile` or MCP `data_lake_artifact_profile`.
4. Download: `GET /api/data-lake/artifacts/{artifact_id}/download` or MCP `data_lake_artifact_download_url`.
5. Attach: `POST /api/data-lake/artifacts/{artifact_id}/attach` or MCP `data_lake_artifact_attach`.
6. List by target: `GET /api/data-lake/artifacts?target_type=&target_id=` or MCP `data_lake_artifact_list`.
7. Detach: `DELETE /api/data-lake/artifacts/{artifact_id}/attach` with explicit confirmation.

Attachments can target workflow stages, Inbox tasks/reports, Report BoI, action results, Agent conversations, or sandbox evidence records. The target record should reference `artifact_id`, `download_url`, `profile`, and the business reason it was attached.

## Validation

```bash
python scripts/check_data_lake_artifacts.py --base-url http://localhost:28000 --strict
python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --allow-disabled --artifact-smoke
```

## Example

- `data/boi/public/boi-wiki-manual/sop-workflows/workflow-task-builder-step-by-step.md` shows where SOP authoring stops at evidence requirements and where runtime Data Lake attachment begins.
