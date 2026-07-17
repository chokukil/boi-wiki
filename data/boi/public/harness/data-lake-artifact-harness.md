---
okf_version: "0.1"
boi_profile_version: "0.1"
harness_version: "0.1.0"
type: boi/harness
title: Data Lake Artifact Harness
description: 파일 근거를 MinIO Data Lake artifact로 저장하고 BoI에는 bounded reference만 남기는 기준
tags: [BoIWiki, DataLake, Artifact, Harness, MCP]
timestamp: 2026-07-04T00:00:00+09:00
boi_id: boi:public:harness:data-lake-artifact-harness
visibility: public
classification: internal
owner: AIX 확산 TF
author:
  type: agent
  agent_id: codex
acl_policy: acl:public
status: reviewed
source_refs:
  - type: repo
    ref: harness/data-lake-artifact-harness.md
review:
  reviewer: harness-curator
  review_status: reviewed
---

# Data Lake Artifact Harness

파일 근거가 필요한 SOP 실행 단계, Inbox 판단, Manual Action 완료, Report BoI 검토, Sandbox, Report Agent, Agent conversation은 이 하네스를 따른다.

## Boundary

MinIO는 선택형 `local-full-datalake` profile 기능이다. BoI Wiki core는 DB 없이 OKF Markdown/JSONL로 동작한다. UI, Agent, MCP는 MinIO에 직접 접속하지 않고 BoI API/MCP artifact 도구만 사용한다.

## Contract

- 원본 파일은 Data Lake artifact로 저장한다.
- BoI Markdown에는 stable download URL, profile, sample, chart/preview, checksum, validation metadata, ACL 상태만 남긴다.
- 큰 raw content를 LLM prompt나 BoI 본문에 붙여 넣지 않는다.
- artifact visibility 기본값은 private이다. team/public 공유는 명시 confirmation이 필요하다.
- Data Lake가 꺼져 있어도 SOP/Inbox/core flow는 계속 동작하고 artifact API는 disabled contract를 반환한다.
- 사람이 직접 올린 파일도 Agent/Sandbox 산출물과 같은 artifact 계약을 사용한다. 첨부 metadata에는 `uploaded_by_employee_id`, `attached_from_surface`, `target_type`, `target_id`, `attachment_role`, `human_note`, `validation_state`를 남긴다.
- SOP Builder는 원본 파일 업로드 화면이 아니다. SOP 작성 중에는 필요한 근거 종류와 첨부 위치를 설계하고, 실제 Raw Data/PDF/PPT/Excel/로그/캡처는 SOP Run 단계, Inbox 판단, Manual Action 완료, Report BoI 검토, Agent 대화에서 첨부한다.
- 사용자는 별도 "근거로 사용" 체크를 하지 않는다. 현재 workflow stage, Inbox task, report, action result, conversation, work context를 기본 연결 대상으로 삼고 필요 시 삭제하거나 다른 대상으로 다시 붙인다.

## Flow

1. Upload: `POST /api/data-lake/artifacts/upload` 또는 MCP `data_lake_artifact_upload`.
2. Inspect: `GET /api/data-lake/artifacts/{artifact_id}` 또는 MCP `data_lake_artifact_get`.
3. Profile: `POST /api/data-lake/artifacts/{artifact_id}/profile` 또는 MCP `data_lake_artifact_profile`.
4. Download: `GET /api/data-lake/artifacts/{artifact_id}/download` 또는 MCP `data_lake_artifact_download_url`.
5. Attach: `POST /api/data-lake/artifacts/{artifact_id}/attach` 또는 MCP `data_lake_artifact_attach`.
6. List by target: `GET /api/data-lake/artifacts?target_type=&target_id=` 또는 MCP `data_lake_artifact_list`.
7. Detach: `DELETE /api/data-lake/artifacts/{artifact_id}/attach`는 명시 confirmation 후 수행한다.

Attach 대상은 workflow stage, Inbox task/report, Report BoI, action result, Agent conversation, sandbox evidence record가 될 수 있다. 대상 record는 `artifact_id`, `download_url`, `profile`, 연결 이유를 남긴다.

## Validation

```bash
python scripts/check_data_lake_artifacts.py --base-url http://localhost:28000 --strict
python scripts/check_local_full_datalake.py --base-url http://localhost:28000 --allow-disabled --artifact-smoke
```

## Example

- [Workflow/Task Builder Step-by-step](/public/boi-wiki-manual/sop-workflows/workflow-task-builder-step-by-step.md) shows where SOP authoring stops at evidence requirements and where runtime Data Lake attachment begins.
